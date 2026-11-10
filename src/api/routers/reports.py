"""
Reports router — Phase 5.

Endpoints:
  POST /{collection}/weekly-report                      → {job_id}
  GET  /weekly-report-progress/{job_id}                 → progress JSON
  GET  /weekly-report-download/{job_id}                 → ZIP bytes
"""
from __future__ import annotations

import time
import uuid as _uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from src.api.deps import get_db

router = APIRouter(tags=["reports"])

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# In-memory job store (process-scoped, same pattern as SCRAPE_JOBS)
REPORT_JOBS: Dict[str, Dict[str, Any]] = {}

# A finished weekly report holds its ZIP in memory until downloaded; drop forgotten ones.
JOB_TTL_S = 15 * 60


def purge_expired_jobs(now: Optional[float] = None) -> None:
    """Remove finished/failed jobs older than ``JOB_TTL_S`` (running jobs are kept)."""
    now = time.time() if now is None else now
    for job_id in [j for j, job in REPORT_JOBS.items()
                   if job.get("status") != "running" and now - job.get("created_at", now) > JOB_TTL_S]:
        REPORT_JOBS.pop(job_id, None)


# ---------------------------------------------------------------------------
# Progress + download endpoints — declared BEFORE /{collection}/... routes
# ---------------------------------------------------------------------------

@router.get("/weekly-report-progress/{job_id}", summary="Progreso del informe semanal")
def weekly_report_progress(job_id: str):
    """Poll the current state of a weekly-report background job.

    Returns ``status`` (``running`` | ``done`` | ``error``),
    ``step``, ``total``, ``message``, ``error``.
    """
    job = REPORT_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return {
        "status":  job["status"],
        "step":    job["step"],
        "total":   job["total"],
        "message": job["message"],
        "error":   job["error"],
    }


@router.get("/weekly-report-download/{job_id}", summary="Descargar ZIP del informe semanal")
def weekly_report_download(job_id: str):
    """Return the ZIP file for a completed weekly-report job.

    The job is removed from memory after this call.

    Raises 409 if the report is not ready yet.
    """
    job = REPORT_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if job["status"] != "done":
        raise HTTPException(status_code=409, detail="Report not ready yet.")
    zip_bytes = job.pop("zip_bytes", b"")
    REPORT_JOBS.pop(job_id, None)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="informe_semanal.zip"'},
    )


# ---------------------------------------------------------------------------
# Individual scouting DOCX and HTML->PDF export (declared before /{collection}/...)
# ---------------------------------------------------------------------------

def _safe_filename_part(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text)


@router.get("/individual-scouting/docx", summary="Descargar el scouting individual del equipo (DOCX)")
def download_individual_scouting_docx(collection: str, team_id: str, db=Depends(get_db)):
    """One page per player: identity, stats, shot profile and radar, plus a blank notes section.

    Args:
        collection: MongoDB collection name.
        team_id: Stable team ID (``HEADER.TEAM.id`` / ``teamIdExtern``).
    """
    from src.utils.collection_utils import is_fbcyl
    from src.utils.team_utils import resolve_team_by_id

    team_info = resolve_team_by_id(db.connection.get_collection(collection), team_id, is_fbcyl(collection))
    team_name = team_info["name"] if team_info else team_id

    try:
        from src.services.individual_scouting_service import IndividualScoutingDocxBuilder

        docx_bytes = IndividualScoutingDocxBuilder(collection=collection, team_name=team_name, db=db).build()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error generando DOCX: {exc}") from exc

    if not docx_bytes:
        raise HTTPException(status_code=404, detail="No se encontraron jugadores para el equipo indicado.")
    return Response(
        content=docx_bytes, media_type=_DOCX_MIME,
        headers={"Content-Disposition": f'attachment; filename="Scouting_{_safe_filename_part(team_name)}.docx"'},
    )


# ---------------------------------------------------------------------------
# Per-collection report endpoints
# ---------------------------------------------------------------------------

class _WeeklyReportRequest(BaseModel):
    team_a: str
    team_b: str


@router.post("/{collection}/weekly-report", summary="Iniciar informe semanal")
def weekly_report_start(
    collection: str,
    body: _WeeklyReportRequest,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
):
    """Queue a background job to generate the full weekly report ZIP.

    Args:
        collection: MongoDB collection name.
        body: JSON body with ``team_a`` (own team) and ``team_b`` (rival).

    Returns:
        ``{job_id}`` — poll ``GET /reports/weekly-report-progress/{job_id}``
        then download via ``GET /reports/weekly-report-download/{job_id}``.
    """
    purge_expired_jobs()
    job_id = str(_uuid.uuid4())
    REPORT_JOBS[job_id] = {
        "created_at": time.time(),
        "status":    "running",
        "step":      0,
        "total":     5,
        "message":   "Iniciando…",
        "zip_bytes": None,
        "error":     None,
    }
    background_tasks.add_task(
        _run_weekly_report, job_id, collection, body.team_a, body.team_b, db
    )
    return {"job_id": job_id}


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

def _run_weekly_report(
    job_id: str, collection: str, team_a: str, team_b: str, db: Any
) -> None:
    """Execute WeeklyReportService in a background thread and store results."""
    job = REPORT_JOBS[job_id]

    def _callback(step: int, total: int, msg: str) -> None:
        job["step"]    = step
        job["total"]   = total
        job["message"] = msg

    try:
        from src.services.weekly_report_service import WeeklyReportService
        svc = WeeklyReportService(db)
        zip_bytes = svc.generate_report_zip(
            collection, team_a, team_b, progress_callback=_callback
        )
        job["zip_bytes"] = zip_bytes
        job["status"]    = "done"
        job["step"]      = job["total"]
        job["message"]   = "Informe completado"
    except Exception as exc:
        job["status"]  = "error"
        job["error"]   = str(exc)
        job["message"] = f"Error: {exc}"
