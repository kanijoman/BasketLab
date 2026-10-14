"""Rival scouting report (issue #299), as a PDF and as data for the screen.

Prefixed at /api/v1/scouting-rival

POST /                       -> 202 {job_id}   start the report of ANY team of a FEB collection (optionally against our team)
GET  /progress/{job_id}      -> status, games processed, team names, error
GET  /report/{job_id}        -> the report as JSON (the preview on screen)
GET  /pdf/{job_id}           -> the PDF (can be downloaded again until the job expires)

Compute only (nothing is persisted), so it needs no admin key, but only ONE job may run at a time and finished jobs expire: the
report replays every game of the competition and is meant to run locally (see docs/LIVE.md). The team is a parameter.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.api.deps import get_db
from src.services.scouting_rival_service import ScoutingRivalService
from src.services.team_report_service import TeamNotFoundError

router = APIRouter()

JOBS: Dict[str, Dict[str, Any]] = {}
SERVICE = ScoutingRivalService      # tests replace it
JOB_TTL_S = 30 * 60
_PDF_MIME = "application/pdf"


class ScoutingRequest(BaseModel):
    collection: str = Field(min_length=1)
    team_id: str = Field(min_length=1, description="The team to scout (any team of the collection)")
    own_team_id: Optional[str] = Field(default=None, description="Our team, for the matchup comparison")


def purge_expired_jobs(now: Optional[float] = None) -> None:
    now = time.time() if now is None else now
    for job_id in [j for j, job in JOBS.items() if now - job.get("created_at", now) > JOB_TTL_S]:
        JOBS.pop(job_id, None)


def _team_names(db, collection: str) -> Dict[str, str]:
    return {str(t["id"]): t["name"] for t in (db.get_teams_with_ids(collection) or [])}


def _run(job_id: str, req: ScoutingRequest, db) -> None:
    job = JOBS[job_id]

    def progress(done: int, total: int) -> None:
        job["current"], job["total"] = done, total

    try:
        job["report"] = SERVICE(db).build(req.collection, req.team_id, req.own_team_id, progress=progress)
        job["status"] = "done"
    except Exception as exc:  # noqa: BLE001 - reported through the progress endpoint
        job["status"], job["error"] = "error", str(exc)


@router.post("", status_code=202, summary="Start the scouting report of a team")
def start_scouting(req: ScoutingRequest, background_tasks: BackgroundTasks, db=Depends(get_db)) -> Dict[str, str]:
    from src.utils.collection_utils import is_fbcyl

    if is_fbcyl(req.collection):
        raise HTTPException(422, "El scouting del rival solo está disponible para colecciones FEB por ahora")
    if req.own_team_id and req.own_team_id == req.team_id:
        raise HTTPException(422, "El equipo propio y el rival deben ser distintos")
    names = _team_names(db, req.collection)
    for tid in filter(None, (req.team_id, req.own_team_id)):
        if tid not in names:
            raise HTTPException(404, f"Equipo no encontrado en la colección: {tid}")
    purge_expired_jobs()
    if any(j.get("status") == "running" for j in JOBS.values()):
        raise HTTPException(429, "Ya hay un informe en preparación; espera a que termine")
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "running", "current": 0, "total": 0, "created_at": time.time(), "error": None, "report": None,
                    "team": names[req.team_id], "own_team": names[req.own_team_id] if req.own_team_id else None,
                    "collection": req.collection}
    background_tasks.add_task(_run, job_id, req, db)
    return {"job_id": job_id}


def _job(job_id: str) -> Dict[str, Any]:
    purge_expired_jobs()
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "Trabajo no encontrado o caducado")
    return job


def _finished(job_id: str) -> Dict[str, Any]:
    job = _job(job_id)
    if job.get("status") != "done" or job.get("report") is None:
        detail = "El informe aún no está listo" if job.get("status") == "running" else f"La preparación falló: {job.get('error')}"
        raise HTTPException(409, detail)
    return job


@router.get("/progress/{job_id}", summary="Progress of a scouting report")
def scouting_progress(job_id: str) -> Dict[str, Any]:
    job = _job(job_id)
    return {k: job.get(k) for k in ("status", "current", "total", "team", "own_team", "error")}


@router.get("/report/{job_id}", summary="The scouting report as JSON")
def scouting_report(job_id: str) -> Dict[str, Any]:
    return _finished(job_id)["report"]


def _safe(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text).strip("_") or "equipo"


@router.get("/pdf/{job_id}", summary="The scouting report as a PDF")
def scouting_pdf(job_id: str) -> Response:
    from src.services.scouting_pdf import render_scouting_pdf

    job = _finished(job_id)
    own = (job["report"].get("own_team") or {}).get("name") or "Nuestro equipo"
    pdf = render_scouting_pdf(job["report"], subtitle=job["collection"], own_name=own)
    return Response(content=pdf, media_type=_PDF_MIME,
                    headers={"Content-Disposition": f'attachment; filename="Scouting_{_safe(job["team"])}.pdf"'})
