"""Live preparation package generation (issue #133, part a).

Prefixed at /api/v1/live

GET  /matches/{collection}        -> upcoming / live matches of a team (FEB calendar)
POST /package                     -> 202 {job_id}   start the (CPU heavy) build in the background
GET  /package/progress/{job_id}   -> status, games processed
GET  /package/download/{job_id}   -> the encrypted .bpkg file (one-shot)

Compute only (nothing is persisted), so it needs no admin key, but only ONE build may run at a
time and finished jobs expire: the build replays every game of the competition and must not
starve the 512 MB instance. The passphrase is used for encryption and never stored or echoed.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.api.deps import get_db
from src.services.match_schedule_service import MatchScheduleService

router = APIRouter()

JOBS: Dict[str, Dict[str, Any]] = {}
JOB_TTL_S = 15 * 60
MIN_PASSPHRASE = 8


class PackageRequest(BaseModel):
    collection: str = Field(min_length=1)
    team_id: str = Field(min_length=1)
    rival_id: str = Field(min_length=1)
    passphrase: str = Field(min_length=MIN_PASSPHRASE, description="Encrypts the package; not recoverable")
    season: Optional[str] = None
    # FEB match the package is prepared for (digits); its details are looked up in the calendar
    match_code: Optional[str] = Field(default=None, pattern=r"^\d+$")


def purge_expired_jobs(now: Optional[float] = None) -> None:
    now = time.time() if now is None else now
    for job_id in [j for j, job in JOBS.items() if now - job.get("created_at", now) > JOB_TTL_S]:
        JOBS.pop(job_id, None)


def _team_names(db, collection: str) -> Dict[str, str]:
    return {str(t["id"]): t["name"] for t in (db.get_teams_with_ids(collection) or [])}


def _match_meta(db, req: PackageRequest) -> Optional[Dict[str, Any]]:
    """``{"match": {...}}`` for the chosen match: details from the calendar, else just the code."""
    if not req.match_code:
        return None
    match: Dict[str, Any] = {"code": req.match_code}
    try:
        found = MatchScheduleService(db).upcoming(req.collection, req.team_id, limit=50)["matches"]
        info = next((m for m in found if m["code"] == req.match_code), None)
        if info:
            match.update(start=info["start"], round=info["round"], home=info["home"], away=info["away"])
    except Exception:  # noqa: BLE001 - the calendar is optional for building the package
        pass
    return {"match": match}


def _run(job_id: str, req: PackageRequest, db) -> None:
    job = JOBS[job_id]

    def progress(done: int, total: int) -> None:
        job["current"], job["total"] = done, total

    try:
        from src.live_prep.db_source import build_package_from_db
        from src.live_prep.package_crypto import encrypt_package

        package = build_package_from_db(db, req.collection, req.team_id, req.rival_id, req.season,
                                        competition_meta=_match_meta(db, req), progress=progress)
        envelope = encrypt_package(package.dumps(), req.passphrase)
        job["envelope"] = json.dumps(envelope, separators=(",", ":"))
        job["status"] = "done"
    except Exception as exc:  # noqa: BLE001 - reported through the progress endpoint
        job["status"], job["error"] = "error", str(exc)


@router.get("/matches/{collection}", summary="Upcoming and live matches of a team (FEB calendar)")
def team_matches(
    collection: str,
    team_id: str = Query(..., description="Stable team id"),
    limit: int = Query(5, ge=1, le=20),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """``{matches, calendar_url, warning}``: dated matches not yet played plus those being played."""
    return MatchScheduleService(db).upcoming(collection, team_id, limit=limit)


@router.post("/package", status_code=202, summary="Start building an encrypted live preparation package")
def start_package(req: PackageRequest, background_tasks: BackgroundTasks, db=Depends(get_db)) -> Dict[str, str]:
    from src.utils.collection_utils import is_fbcyl

    if req.team_id == req.rival_id:
        raise HTTPException(422, "El equipo propio y el rival deben ser distintos")
    if is_fbcyl(req.collection):
        raise HTTPException(422, "Los paquetes live solo están disponibles para colecciones FEB por ahora")
    names = _team_names(db, req.collection)
    for tid in (req.team_id, req.rival_id):
        if tid not in names:
            raise HTTPException(404, f"Equipo no encontrado en la colección: {tid}")
    purge_expired_jobs()
    if any(j.get("status") == "running" for j in JOBS.values()):
        raise HTTPException(429, "Ya hay un paquete en preparación; espera a que termine")
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "status": "running", "current": 0, "total": 0, "created_at": time.time(), "error": None,
        "team": names[req.team_id], "rival": names[req.rival_id], "envelope": None,
    }
    background_tasks.add_task(_run, job_id, req, db)
    return {"job_id": job_id}


def _job(job_id: str) -> Dict[str, Any]:
    purge_expired_jobs()
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "Trabajo no encontrado o caducado")
    return job


@router.get("/package/progress/{job_id}", summary="Progress of a package build")
def package_progress(job_id: str) -> Dict[str, Any]:
    job = _job(job_id)
    return {k: job.get(k) for k in ("status", "current", "total", "team", "rival", "error")}


def _safe(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text).strip("_") or "equipo"


@router.get("/package/download/{job_id}", summary="Download the encrypted package (one-shot)")
def package_download(job_id: str) -> Response:
    job = _job(job_id)
    if job.get("status") != "done" or not job.get("envelope"):
        detail = "El paquete aún no está listo" if job.get("status") == "running" else f"La preparación falló: {job.get('error')}"
        raise HTTPException(409, detail)
    JOBS.pop(job_id, None)
    name = f"live_{_safe(job['team'])}_vs_{_safe(job['rival'])}.bpkg"
    return Response(content=job["envelope"], media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
