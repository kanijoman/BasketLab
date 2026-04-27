"""
Reports router — Phase 5.

Endpoints:
  GET  /{collection}/player-scouting/{player_id}       → DOCX bytes
  GET  /{collection}/team-scouting/{team_name}          → PDF bytes
  GET  /{collection}/season-summary                     → PDF bytes
  POST /{collection}/weekly-report                      → {job_id}
  GET  /weekly-report-progress/{job_id}                 → progress JSON
  GET  /weekly-report-download/{job_id}                 → ZIP bytes
"""
from __future__ import annotations

import uuid as _uuid
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from src.api.deps import get_db
from src.services.report_service import (
    build_player_scouting_docx,
    build_team_scouting_pdf,
    build_season_summary_pdf,
)

router = APIRouter(tags=["reports"])

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_PDF_MIME  = "application/pdf"

# In-memory job store (process-scoped, same pattern as SCRAPE_JOBS)
REPORT_JOBS: Dict[str, Dict[str, Any]] = {}


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
# Per-collection report endpoints
# ---------------------------------------------------------------------------

@router.get("/{collection}/player-scouting/{player_id}", summary="Player scouting DOCX")
def player_scouting(collection: str, player_id: str, db=Depends(get_db)):
    """Generate a one-page individual scouting sheet as DOCX."""
    data = build_player_scouting_docx(collection, player_id, db)
    filename = f"scouting_{player_id}.docx"
    return Response(
        content=data,
        media_type=_DOCX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{collection}/team-scouting/{team_name}", summary="Team scouting PDF")
def team_scouting(collection: str, team_name: str, db=Depends(get_db)):
    """Generate an offensive/defensive breakdown scouting PDF for a team."""
    safe_name = team_name.replace(" ", "_")[:40]
    filename  = f"scouting_{safe_name}.pdf"
    data = build_team_scouting_pdf(collection, team_name, db)
    return Response(
        content=data,
        media_type=_PDF_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{collection}/season-summary", summary="Season summary PDF")
def season_summary(collection: str, db=Depends(get_db)):
    """Generate a league-wide season efficiency ranking PDF."""
    data = build_season_summary_pdf(collection, db)
    filename = f"temporada_{collection[:30]}.pdf"
    return Response(
        content=data,
        media_type=_PDF_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
    job_id = str(_uuid.uuid4())
    REPORT_JOBS[job_id] = {
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
