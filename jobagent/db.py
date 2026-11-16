"""Database management and SQLite operations for JobAgent."""

import json
import os
from pathlib import Path
import sqlite3
from typing import Any

DB_PATH = Path(os.path.expanduser("~/jobagent/data/jobs.db"))


def get_conn() -> sqlite3.Connection:
    """Open or create the SQLite database, apply schema and return connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source          TEXT NOT NULL,
            source_url      TEXT UNIQUE NOT NULL,
            title           TEXT,
            company         TEXT,
            location        TEXT,
            employment_type TEXT,
            description     TEXT,
            posted_at       TEXT,
            fetched_at      TEXT DEFAULT CURRENT_TIMESTAMP,
            content_hash    TEXT
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_company_title ON jobs(company, title);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_fetched_at ON jobs(fetched_at);"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS matches (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id           INTEGER NOT NULL UNIQUE,
            score            INTEGER NOT NULL,
            verdict          TEXT NOT NULL,
            reasons_json     TEXT,
            missing_json     TEXT,
            flags_json       TEXT,
            parsed_json      TEXT,
            scored_at        TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_matches_score ON matches(score DESC);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_matches_verdict ON matches(verdict);"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id          INTEGER NOT NULL UNIQUE,
            cv_path         TEXT,
            cover_letter    TEXT,
            letter_status   TEXT NOT NULL DEFAULT 'no_letter_needed',
            violations_json TEXT,
            status          TEXT NOT NULL DEFAULT 'prepared',
            prepared_at     TEXT DEFAULT CURRENT_TIMESTAMP,
            approved_at     TEXT,
            submitted_at    TEXT,
            notes           TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);"
    )
    conn.commit()
    return conn


def insert_job(conn: sqlite3.Connection, job: dict[str, Any]) -> bool:
    """Insert a normalized job record; return True if inserted, False if duplicate."""
    try:
        conn.execute(
            """
            INSERT INTO jobs (
                source, source_url, title, company, location,
                employment_type, description, posted_at, content_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.get("source"),
                job.get("source_url"),
                job.get("title"),
                job.get("company"),
                job.get("location"),
                job.get("employment_type"),
                job.get("description"),
                job.get("posted_at"),
                job.get("content_hash"),
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def count_jobs(conn: sqlite3.Connection) -> int:
    """Return the total number of jobs currently in the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jobs;")
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def save_match(conn: sqlite3.Connection, job_id: int, result: dict[str, Any]) -> None:
    """Insert or replace a match record for a specific job."""
    conn.execute(
        """
        INSERT OR REPLACE INTO matches (
            job_id, score, verdict, reasons_json, missing_json, flags_json, parsed_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            int(result.get("score", 0)),
            str(result.get("verdict", "unsuitable")),
            json.dumps(result.get("reasons", [])),
            json.dumps(result.get("missing", [])),
            json.dumps(result.get("eligibility_flags", [])),
            json.dumps(result.get("parsed", {})),
        ),
    )
    conn.commit()


def get_unscored_jobs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return all jobs that have not been scored yet."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT j.id, j.source, j.source_url, j.title, j.company, j.location,
               j.employment_type, j.description, j.posted_at, j.fetched_at, j.content_hash
        FROM jobs j
        LEFT JOIN matches m ON j.id = m.job_id
        WHERE m.job_id IS NULL
        ORDER BY j.id ASC;
        """
    )
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_job_by_id(conn: sqlite3.Connection, job_id: int) -> dict[str, Any] | None:
    """Return a single job row as a dict, or None if not found."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT j.id, j.source, j.source_url, j.title, j.company, j.location,
               j.employment_type, j.description, j.posted_at, j.fetched_at,
               j.content_hash, m.score, m.verdict, m.reasons_json, m.flags_json
        FROM jobs j
        LEFT JOIN matches m ON j.id = m.job_id
        WHERE j.id = ?;
        """,
        (job_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    cols = [desc[0] for desc in cursor.description]
    return dict(zip(cols, row))


def save_application(
    conn: sqlite3.Connection,
    job_id: int,
    cv_path: str,
    letter: str,
    letter_status: str,
    violations: list[str],
) -> None:
    """Insert or replace an application record for a job."""
    conn.execute(
        """
        INSERT OR REPLACE INTO applications
            (job_id, cv_path, cover_letter, letter_status, violations_json, status)
        VALUES (?, ?, ?, ?, ?, 'prepared')
        """,
        (job_id, cv_path, letter, letter_status, json.dumps(violations)),
    )
    conn.commit()


def get_application(conn: sqlite3.Connection, job_id: int) -> dict[str, Any] | None:
    """Return the application row for a job, or None if not found."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM applications WHERE job_id = ?;",
        (job_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    cols = [desc[0] for desc in cursor.description]
    return dict(zip(cols, row))


def approve_application(conn: sqlite3.Connection, job_id: int, final_letter: str) -> None:
    """Update an application's cover letter and mark it as approved."""
    conn.execute(
        """
        UPDATE applications
        SET cover_letter = ?, status = 'approved',
            approved_at = CURRENT_TIMESTAMP
        WHERE job_id = ?;
        """,
        (final_letter, job_id),
    )
    conn.commit()


def list_shortlisted(
    conn: sqlite3.Connection, limit: int = 50, offset: int = 0, verdict: str = "all"
) -> tuple[list[dict[str, Any]], int]:
    """Return paginated shortlisted jobs and total count."""
    cursor = conn.cursor()
    base_where = "WHERE m.verdict IN ('high_priority', 'worth_reviewing')"
    params: list[Any] = []
    if verdict in ("high_priority", "worth_reviewing"):
        base_where = "WHERE m.verdict = ?"
        params.append(verdict)

    cursor.execute(
        f"""
        SELECT COUNT(*)
        FROM jobs j
        JOIN matches m ON j.id = m.job_id
        {base_where};
        """,
        params,
    )
    row = cursor.fetchone()
    total = int(row[0]) if row else 0

    cursor.execute(
        f"""
        SELECT j.id, j.title, j.company, j.location, j.source, j.source_url,
               m.score, m.verdict, m.reasons_json, m.missing_json,
               j.fetched_at, j.posted_at,
               (a.id IS NOT NULL) AS has_application
        FROM jobs j
        JOIN matches m ON j.id = m.job_id
        LEFT JOIN applications a ON j.id = a.job_id
        {base_where}
        ORDER BY m.score DESC, j.fetched_at DESC
        LIMIT ? OFFSET ?;
        """,
        params + [limit, offset],
    )
    jobs: list[dict[str, Any]] = []
    for r in cursor.fetchall():
        reasons = json.loads(r[8]) if r[8] else []
        missing = json.loads(r[9]) if r[9] else []
        jobs.append({
            "id": r[0],
            "title": r[1] or "",
            "company": r[2] or "",
            "location": r[3] or "",
            "source": r[4] or "",
            "source_url": r[5] or "",
            "score": r[6],
            "verdict": r[7],
            "reasons": reasons,
            "missing": missing,
            "fetched_at": r[10] or "",
            "posted_at": r[11] or "",
            "has_application": bool(r[12]),
        })
    return jobs, total


def get_job_detail(conn: sqlite3.Connection, job_id: int) -> dict[str, Any] | None:
    """Return full job data, match analysis, and application record if present."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT j.id, j.source, j.source_url, j.title, j.company, j.location,
               j.employment_type, j.description, j.posted_at, j.fetched_at,
               m.score, m.verdict, m.reasons_json, m.missing_json,
               m.flags_json, m.parsed_json
        FROM jobs j
        LEFT JOIN matches m ON j.id = m.job_id
        WHERE j.id = ?;
        """,
        (job_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    app_row = get_application(conn, job_id)
    return {
        "id": row[0],
        "source": row[1] or "",
        "source_url": row[2] or "",
        "title": row[3] or "",
        "company": row[4] or "",
        "location": row[5] or "",
        "employment_type": row[6] or "",
        "description": row[7] or "",
        "posted_at": row[8] or "",
        "fetched_at": row[9] or "",
        "score": row[10] if row[10] is not None else 0,
        "verdict": row[11] or "unscored",
        "reasons": json.loads(row[12]) if row[12] else [],
        "missing": json.loads(row[13]) if row[13] else [],
        "eligibility_flags": json.loads(row[14]) if row[14] else [],
        "parsed": json.loads(row[15]) if row[15] else {},
        "application": app_row,
    }


def update_letter(
    conn: sqlite3.Connection, job_id: int, letter: str
) -> dict[str, Any] | None:
    """Update the cover letter for an application and return the updated application."""
    conn.execute(
        "UPDATE applications SET cover_letter = ? WHERE job_id = ?;",
        (letter, job_id),
    )
    conn.commit()
    return get_application(conn, job_id)


def reset_application(
    conn: sqlite3.Connection, job_id: int
) -> dict[str, Any] | None:
    """Reset an application status to 'prepared' and clear approved_at."""
    conn.execute(
        """
        UPDATE applications
        SET status = 'prepared', approved_at = NULL
        WHERE job_id = ?;
        """,
        (job_id,),
    )
    conn.commit()
    return get_application(conn, job_id)


def list_applications(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return all applications joined with jobs and match scores."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT a.job_id, j.title, j.company, j.location, j.source_url,
               a.status, a.letter_status, a.prepared_at, a.approved_at,
               m.score, m.verdict
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        LEFT JOIN matches m ON j.id = m.job_id
        ORDER BY (a.approved_at IS NULL), a.approved_at DESC, a.prepared_at DESC;
        """
    )
    rows = cursor.fetchall()
    results: list[dict[str, Any]] = []
    for r in rows:
        results.append({
            "id": r[0],
            "title": r[1] or "",
            "company": r[2] or "",
            "location": r[3] or "",
            "source_url": r[4] or "",
            "status": r[5] or "prepared",
            "letter_status": r[6] or "no_letter_needed",
            "prepared_at": r[7] or "",
            "approved_at": r[8],
            "score": r[9] if r[9] is not None else 0,
            "verdict": r[10] or "",
        })
    return results

