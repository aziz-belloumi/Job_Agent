"""Command-line interface for JobAgent."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jobagent.analysis import parse, score as score_engine
from jobagent.db import (
    approve_application, count_jobs, get_application, get_conn,
    get_job_by_id, get_unscored_jobs, insert_job, save_application, save_match,
)
from jobagent.prepare import cover_letter as cl_engine
from jobagent.sources import remotive

console = Console()


def discover() -> None:
    """Fetch jobs from sources, store new jobs in SQLite, and display summary."""
    console.print("[cyan]Discovering jobs from configured sources...[/cyan]")
    jobs: list[dict[str, Any]] = remotive.fetch()
    conn = get_conn()
    new_count = 0
    dup_count = 0
    new_jobs: list[dict[str, Any]] = []

    for job in jobs:
        if insert_job(conn, job):
            new_count += 1
            new_jobs.append(job)
        else:
            dup_count += 1

    total_in_db = count_jobs(conn)
    conn.close()
    console.print(
        f"[green]Fetched {len(jobs)} jobs, {new_count} new, "
        f"{dup_count} duplicates skipped. Total in DB: {total_in_db}.[/green]"
    )
    if new_jobs:
        table = Table(title="Recent New Jobs (Sample of 10)")
        table.add_column("Title", style="cyan")
        table.add_column("Company", style="magenta")
        table.add_column("Location", style="green")
        for job in new_jobs[:10]:
            table.add_row(job.get("title") or "N/A", job.get("company") or "N/A", job.get("location") or "N/A")
        console.print(table)


def stats() -> None:
    """Display total job count and a breakdown by source."""
    conn = get_conn()
    total = count_jobs(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT source, COUNT(*) FROM jobs GROUP BY source ORDER BY COUNT(*) DESC;")
    breakdown = cursor.fetchall()
    conn.close()

    console.print(f"[bold cyan]Total jobs in database:[/bold cyan] {total}")
    if breakdown:
        table = Table(title="Jobs by Source")
        table.add_column("Source", style="cyan")
        table.add_column("Count", style="green", justify="right")
        for source, count in breakdown:
            table.add_row(str(source), str(count))
        console.print(table)


def score() -> None:
    """Score unscored jobs against profile, save matches, and show top candidates."""
    profile = parse.load_profile()
    conn = get_conn()
    unscored = get_unscored_jobs(conn)

    if not unscored:
        console.print("[yellow]No unscored jobs found in database.[/yellow]")
        conn.close()
        return

    counts = {"high_priority": 0, "worth_reviewing": 0, "unsuitable": 0}
    scored_items: list[dict[str, Any]] = []

    for job in unscored:
        parsed = parse.parse_job(job, profile)
        res = score_engine.score_job(job, parsed, profile)
        save_match(conn, job["id"], res)
        counts[res["verdict"]] = counts.get(res["verdict"], 0) + 1
        scored_items.append({
            "score": res["score"], "title": job.get("title") or "N/A",
            "company": job.get("company") or "N/A", "verdict": res["verdict"],
            "top_reason": res["reasons"][0] if res["reasons"] else "N/A",
        })
    conn.close()

    console.print(
        f"[green]Scored {len(unscored)} jobs: {counts['high_priority']} high priority, "
        f"{counts['worth_reviewing']} worth reviewing, {counts['unsuitable']} unsuitable.[/green]"
    )
    eligible = [it for it in scored_items if it["verdict"] in ("high_priority", "worth_reviewing")]
    eligible.sort(key=lambda x: x["score"], reverse=True)
    if eligible:
        table = Table(title="Top High Priority & Worth Reviewing Jobs")
        table.add_column("Score", style="bold green", justify="right")
        table.add_column("Title", style="cyan")
        table.add_column("Company", style="magenta")
        table.add_column("Verdict", style="yellow")
        table.add_column("Top Reason", style="white")
        for it in eligible[:15]:
            table.add_row(str(it["score"]), it["title"], it["company"], it["verdict"], it["top_reason"])
        console.print(table)


def shortlist() -> None:
    """Display all shortlisted jobs from matches table sorted by score."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT m.score, j.title, j.company, j.location, m.verdict, m.missing_json
        FROM matches m JOIN jobs j ON m.job_id = j.id
        WHERE m.verdict IN ('high_priority', 'worth_reviewing')
        ORDER BY m.score DESC;
        """
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        console.print("[yellow]No shortlisted jobs found.[/yellow]")
        return

    table = Table(title="Shortlisted Jobs")
    table.add_column("Score", style="bold green", justify="right")
    table.add_column("Title", style="cyan")
    table.add_column("Company", style="magenta")
    table.add_column("Location", style="blue")
    table.add_column("Verdict", style="yellow")
    table.add_column("Missing Skills", style="red")

    high_count = sum(1 for r in rows if r[4] == "high_priority")
    worth_count = sum(1 for r in rows if r[4] == "worth_reviewing")
    for score_val, title, company, location, verdict, missing_json in rows:
        missing_skills = json.loads(missing_json) if missing_json else []
        table.add_row(str(score_val), title or "N/A", company or "N/A", location or "N/A", verdict, ", ".join(missing_skills[:3]) if missing_skills else "None")

    console.print(table)
    console.print(f"[bold]Total shortlisted:[/bold] {len(rows)} ({high_count} high priority, {worth_count} worth reviewing)")


def prepare(job_id_str: str) -> None:
    """Prepare an application for a shortlisted job: select CV and optionally generate cover letter."""
    try:
        job_id = int(job_id_str)
    except (ValueError, TypeError):
        console.print("[red]Usage: python -m jobagent.cli prepare <job_id>[/red]")
        return

    cfg = cl_engine.load_cv_config()
    profile = cl_engine.load_profile()
    cv_path = str(Path(cfg.get("cv_path", "~/cv/cv.pdf")).expanduser())

    conn = get_conn()
    job = get_job_by_id(conn, job_id)
    if not job:
        console.print(f"[red]Job ID {job_id} not found.[/red]")
        conn.close()
        return

    verdict = job.get("verdict", "")
    if verdict == "unsuitable":
        console.print(f"[yellow]Job {job_id} is marked unsuitable — not preparing.[/yellow]")
        conn.close()
        return

    desc = str(job.get("description") or "")
    letter = ""
    letter_status = "no_letter_needed"
    violations: list[str] = []

    if cl_engine.cover_letter_requested(desc, cfg):
        console.print("[cyan]Cover letter requested — generating via Ollama...[/cyan]")
        try:
            result = cl_engine.generate(job, profile, cfg)
            letter = result["letter"]
            letter_status = result["status"]
            violations = result.get("violations", [])
            if violations:
                console.print(f"[yellow]Validation warnings:[/yellow] {violations}")
            else:
                console.print("[green]Cover letter generated and validated.[/green]")
        except Exception as exc:
            console.print(f"[red]Cover letter generation failed: {exc}[/red]")
            letter_status = "generation_failed"
    else:
        console.print("[dim]No cover letter required by this job posting.[/dim]")

    save_application(conn, job_id, cv_path, letter, letter_status, violations)
    conn.close()

    console.print(Panel(
        f"[bold]Job:[/bold] {job.get('title')} @ {job.get('company')}\n"
        f"[bold]CV:[/bold] {cv_path}\n"
        f"[bold]Letter status:[/bold] {letter_status}",
        title=f"Application Prepared — Job #{job_id}",
        style="green",
    ))
    console.print(f"Run [bold]python -m jobagent.cli review {job_id}[/bold] to review and approve.", markup=True)


def review(job_id_str: str) -> None:
    """Open an application for terminal review: show details, edit letter in $EDITOR, approve or reject."""
    try:
        job_id = int(job_id_str)
    except (ValueError, TypeError):
        console.print("[red]Usage: python -m jobagent.cli review <job_id>[/red]")
        return

    conn = get_conn()
    job = get_job_by_id(conn, job_id)
    app = get_application(conn, job_id)

    if not job:
        console.print(f"[red]Job ID {job_id} not found.[/red]")
        conn.close()
        return
    if not app:
        console.print(f"[yellow]No application found for job {job_id}. Run 'prepare {job_id}' first.[/yellow]")
        conn.close()
        return

    import json as _json
    reasons = _json.loads(job.get("reasons_json") or "[]") if job.get("reasons_json") else []

    # Show job summary panel
    console.print(Panel(
        f"[bold]Title:[/bold]   {job.get('title')}\n"
        f"[bold]Company:[/bold] {job.get('company')}\n"
        f"[bold]Location:[/bold]{job.get('location')}\n"
        f"[bold]Score:[/bold]   {job.get('score')}  [bold]Verdict:[/bold] {job.get('verdict')}\n"
        f"[bold]URL:[/bold]     {job.get('source_url')}\n"
        f"[bold]Reasons:[/bold] {'; '.join(reasons[:3])}",
        title=f"Job #{job_id} — Review",
        style="cyan",
    ))

    letter_status = app.get("letter_status", "no_letter_needed")
    letter = app.get("cover_letter") or ""

    if letter_status == "no_letter_needed" or not letter:
        console.print("[dim]No cover letter required — approving without letter.[/dim]")
        console.print(f"[bold]CV:[/bold] {app.get('cv_path')}")
        answer = console.input("[bold yellow]Approve this application? [y/n]: [/bold yellow]").strip().lower()
        if answer == "y":
            approve_application(conn, job_id, "")
            console.print("[green]✓ Application approved.[/green]")
        else:
            console.print("[dim]Application not approved — status unchanged.[/dim]")
        conn.close()
        return

    # Edit cover letter in $EDITOR
    console.print(Panel(letter, title="Generated Cover Letter", style="white"))
    editor = os.environ.get("EDITOR", "nano")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix="_cover_letter.txt", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(letter)
        tmp_path = tmp.name

    console.print(f"[dim]Opening in {editor}... Save and close to continue.[/dim]")
    subprocess.run([editor, tmp_path], check=False)

    with open(tmp_path, "r", encoding="utf-8") as f:
        final_letter = f.read().strip()
    Path(tmp_path).unlink(missing_ok=True)

    console.print(Panel(final_letter, title="Final Cover Letter", style="green"))
    console.print(f"[bold]CV:[/bold] {app.get('cv_path')}")
    answer = console.input("[bold yellow]Approve this application? [y/n]: [/bold yellow]").strip().lower()

    if answer == "y":
        approve_application(conn, job_id, final_letter)
        console.print("[green]✓ Application approved.[/green]")
    else:
        console.print("[dim]Application not approved — status unchanged.[/dim]")

    conn.close()


def applications() -> None:
    """List all prepared/approved applications in a rich table."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT a.job_id, j.title, j.company, a.letter_status,
               a.status, a.cv_path, a.prepared_at, a.approved_at
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        ORDER BY a.prepared_at DESC;
        """
    )
    rows = cursor.fetchall()
    conn.close()

    table = Table(title="Applications", show_lines=False)
    table.add_column("ID", style="dim", width=4)
    table.add_column("Title", style="bold white")
    table.add_column("Company", style="magenta")
    table.add_column("Letter", style="blue")
    table.add_column("Status", style="yellow")
    table.add_column("Approved", style="green")

    if not rows:
        console.print("[dim]No applications prepared yet.[/dim]")
        return

    for job_id, title, company, letter_status, status, cv_path, prepared_at, approved_at in rows:
        table.add_row(
            str(job_id),
            (title or "N/A")[:35],
            company or "N/A",
            letter_status or "—",
            status or "—",
            "✓" if approved_at else "—",
        )

    console.print(table)
    console.print(f"[bold]Total applications:[/bold] {len(rows)}")



def serve() -> None:
    """Start local web UI via uvicorn on 127.0.0.1:8000."""
    import uvicorn
    console.print("[bold green]Starting JobAgent Web UI on http://127.0.0.1:8000[/bold green]")
    console.print("Open [bold cyan]http://127.0.0.1:8000[/bold cyan] in your browser.")
    uvicorn.run("jobagent.api.app:app", host="127.0.0.1", port=8000, reload=False)


def main() -> None:
    """Entry point for the JobAgent CLI."""
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    arg = sys.argv[2] if len(sys.argv) > 2 else ""
    if cmd == "discover":
        discover()
    elif cmd == "stats":
        stats()
    elif cmd == "score":
        score()
    elif cmd == "shortlist":
        shortlist()
    elif cmd == "prepare":
        prepare(arg)
    elif cmd == "review":
        review(arg)
    elif cmd == "applications":
        applications()
    elif cmd == "serve":
        serve()
    else:
        console.print(
            "Usage: python -m jobagent.cli [discover|stats|score|shortlist|prepare <id>|review <id>|applications|serve]",
            style="yellow", markup=False,
        )


if __name__ == "__main__":
    main()

