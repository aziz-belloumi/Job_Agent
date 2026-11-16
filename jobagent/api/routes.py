"""FastAPI route handlers for JobAgent web interface."""

import asyncio
from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from jobagent import db
from jobagent.analysis import parse, score as score_engine
from jobagent.prepare import cover_letter as cl_engine, llm
from jobagent.sources import remotive

router = APIRouter(prefix="/api")
admin_lock = asyncio.Lock()


class LetterUpdatePayload(BaseModel):
    letter: str = Field(..., max_length=10000)


@router.get("/health")
def get_health() -> dict[str, Any]:
    cfg = cl_engine.load_cv_config()
    ollama_ok = llm.health_check(cfg)
    db_ok = False
    try:
        conn = db.get_conn()
        conn.execute("SELECT 1;").fetchone()
        conn.close()
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok", "ollama": ollama_ok, "db": db_ok}


@router.get("/jobs/shortlist")
def get_shortlist(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    verdict: str = Query(default="all"),
) -> dict[str, Any]:
    if verdict not in ("all", "high_priority", "worth_reviewing"):
        raise HTTPException(status_code=400, detail="Invalid verdict filter")
    conn = db.get_conn()
    try:
        jobs, total = db.list_shortlisted(conn, limit=limit, offset=offset, verdict=verdict)
        return {"jobs": jobs, "total": total}
    finally:
        conn.close()


@router.get("/jobs/{job_id}")
def get_job(job_id: int) -> dict[str, Any]:
    if job_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid job ID")
    conn = db.get_conn()
    try:
        job = db.get_job_detail(conn, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job
    finally:
        conn.close()


@router.post("/jobs/{job_id}/prepare")
def prepare_job(job_id: int) -> dict[str, Any]:
    if job_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid job ID")
    cfg = cl_engine.load_cv_config()
    profile = cl_engine.load_profile()
    cv_path = str(Path(cfg.get("cv_path", "~/cv/cv.pdf")).expanduser())
    conn = db.get_conn()
    try:
        job = db.get_job_by_id(conn, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.get("verdict") == "unsuitable":
            raise HTTPException(status_code=400, detail="Job is marked unsuitable")

        desc = str(job.get("description") or "")
        letter: str | None = None
        letter_status = "skipped"
        violations: list[str] = []
        warnings: list[str] = []

        if cl_engine.cover_letter_requested(desc, cfg):
            if not llm.health_check(cfg):
                raise HTTPException(status_code=503, detail="ollama_unavailable")
            try:
                res = cl_engine.generate(job, profile, cfg)
                letter = res.get("letter")
                raw_st = res.get("status", "")
                letter_status = "failed" if raw_st == "validation_failed" else "generated"
                violations = res.get("violations", [])
                warnings = res.get("warnings", [])
            except Exception as exc:
                letter_status = "failed"
                violations = [str(exc)]

        db.save_application(conn, job_id, cv_path, letter or "", letter_status, violations)
        return {"letter_status": letter_status, "letter": letter, "warnings": warnings, "errors": violations}
    finally:
        conn.close()


@router.patch("/applications/{job_id}/letter")
def patch_letter(job_id: int, body: LetterUpdatePayload) -> dict[str, Any]:
    conn = db.get_conn()
    try:
        app = db.get_application(conn, job_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        return db.update_letter(conn, job_id, body.letter) or {}
    finally:
        conn.close()


@router.post("/applications/{job_id}/approve")
def approve_app(job_id: int) -> dict[str, Any]:
    conn = db.get_conn()
    try:
        app = db.get_application(conn, job_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        db.approve_application(conn, job_id, app.get("cover_letter") or "")
        return db.get_application(conn, job_id) or {}
    finally:
        conn.close()


@router.post("/applications/{job_id}/reset")
def reset_app(job_id: int) -> dict[str, Any]:
    conn = db.get_conn()
    try:
        app = db.get_application(conn, job_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        return db.reset_application(conn, job_id) or {}
    finally:
        conn.close()


@router.get("/applications")
def get_applications() -> list[dict[str, Any]]:
    conn = db.get_conn()
    try:
        return db.list_applications(conn)
    finally:
        conn.close()


@router.post("/admin/discover")
async def run_discover() -> dict[str, int]:
    async with admin_lock:
        jobs = remotive.fetch()
        conn = db.get_conn()
        new_cnt = dup_cnt = 0
        try:
            for job in jobs:
                if db.insert_job(conn, job):
                    new_cnt += 1
                else:
                    dup_cnt += 1
            return {"fetched": len(jobs), "new": new_cnt, "duplicates": dup_cnt}
        finally:
            conn.close()


@router.post("/admin/score")
async def run_score() -> dict[str, int]:
    async with admin_lock:
        profile = parse.load_profile()
        conn = db.get_conn()
        try:
            unscored = db.get_unscored_jobs(conn)
            counts = {"scored": len(unscored), "high_priority": 0, "worth_reviewing": 0, "unsuitable": 0}
            for job in unscored:
                parsed = parse.parse_job(job, profile)
                res = score_engine.score_job(job, parsed, profile)
                db.save_match(conn, job["id"], res)
                counts[str(res.get("verdict", "unsuitable"))] = counts.get(str(res.get("verdict", "unsuitable")), 0) + 1
            return counts
        finally:
            conn.close()
