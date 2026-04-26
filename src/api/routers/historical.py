"""Historical router — HISTORICAL collection ingestion and status endpoints.

Provides endpoints to:
- Start a background job that downloads one or more seasons into HISTORICAL.
- Poll job progress.
- Query what is already stored in HISTORICAL (summary).

Job state is held in-process (same pattern as the scrape router).
"""

from __future__ import annotations

import threading
import uuid as _uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.deps import get_db

router = APIRouter()

# ---------------------------------------------------------------------------
# In-process job store
# ---------------------------------------------------------------------------

HISTORICAL_JOBS: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class FEBSeasonParams(BaseModel):
    """Parameters for one FEB season to ingest."""

    competition_url: str
    season_value: str
    group_value: str
    year: str = "2025"
    competition_label: str
    season_label: str
    group_label: str
    normalized_season: str = Field(
        ...,
        description="Human-readable season, e.g. '2024-25'",
        examples=["2024-25"],
    )


class FBCYLSeasonParams(BaseModel):
    """Parameters for one FBCYL season to ingest."""

    competition_id: str
    season: str
    gender: str = ""
    territory: str = "0"
    category: str
    competition_label: str
    normalized_season: str = Field(
        ...,
        description="Human-readable season, e.g. '2024-25'",
        examples=["2024-25"],
    )


class HistoricalIngestRequest(BaseModel):
    """Body for POST /historical/ingest."""

    league: str = Field(..., description="'FEB' or 'FBCYL'")
    feb_seasons: Optional[List[FEBSeasonParams]] = None
    fbcyl_seasons: Optional[List[FBCYLSeasonParams]] = None


class FEBCompetitionSeasonParam(BaseModel):
    """One season to ingest, without group info (groups are auto-discovered)."""

    season_value: str
    season_label: str


class FEBCompetitionIngestRequest(BaseModel):
    """Body for POST /historical/ingest_competition.

    Simpler than :class:`HistoricalIngestRequest` — the caller only selects
    which seasons to download; the backend discovers all available groups for
    each season automatically.
    """

    competition_url: str = Field(..., description="FEB competition calendar URL.")
    competition_label: str = Field(..., description="Human-readable label, e.g. 'LF2'.")
    year: str = Field("2025", description="Year hint for the FEB scraper session init.")
    seasons: List[FEBCompetitionSeasonParam] = Field(
        ..., description="Seasons to ingest (season_value + season_label)."
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/ingest", summary="Start a background historical ingestion job")
def start_ingest(
    req: HistoricalIngestRequest,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
) -> Dict[str, str]:
    """Queue a background job to download multiple seasons into HISTORICAL.

    Args:
        req: League selection and list of seasons to ingest.

    Returns:
        ``{job_id}`` — poll ``GET /historical/progress/{job_id}``.
    """
    league = req.league.upper()
    if league not in ("FEB", "FBCYL"):
        raise HTTPException(status_code=400, detail="league must be 'FEB' or 'FBCYL'.")

    if league == "FEB" and not req.feb_seasons:
        raise HTTPException(status_code=422, detail="feb_seasons required for FEB.")
    if league == "FBCYL" and not req.fbcyl_seasons:
        raise HTTPException(status_code=422, detail="fbcyl_seasons required for FBCYL.")

    job_id = str(_uuid.uuid4())
    HISTORICAL_JOBS[job_id] = {
        "status": "starting",
        "total": 0,
        "done": 0,
        "errors": [],
        "current_season": None,
        "current_match": None,
    }

    if league == "FEB":
        background_tasks.add_task(_run_feb_ingest, job_id, req.feb_seasons, db)
    else:
        background_tasks.add_task(_run_fbcyl_ingest, job_id, req.fbcyl_seasons, db)

    return {"job_id": job_id}


@router.get("/progress/{job_id}", summary="Poll historical ingestion job progress")
def ingest_progress(job_id: str) -> Dict[str, Any]:
    """Return current state of an ingestion job.

    Raises:
        404 if the job ID is unknown.
    """
    job = HISTORICAL_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job


@router.get("/summary", summary="Summary of what is stored in HISTORICAL")
def historical_summary(db=Depends(get_db)) -> List[Dict[str, Any]]:
    """Return grouped counts of team-match documents in HISTORICAL.

    Returns:
        List of ``{league, competition, season, group, match_count}`` dicts,
        sorted by league → competition → season (desc).
    """
    from src.database.historical_repository import HistoricalRepository

    repo = HistoricalRepository(db.connection)
    return repo.get_summary()


@router.get("/seasons", summary="List distinct seasons in HISTORICAL")
def list_historical_seasons(db=Depends(get_db)) -> List[str]:
    """Return distinct season labels stored in HISTORICAL, newest first.

    Returns:
        List of season strings, e.g. ``["2024-25", "2023-24"]``.
    """
    from src.database.historical_repository import HistoricalRepository

    repo = HistoricalRepository(db.connection)
    return repo.list_seasons()


@router.get("/teams", summary="List teams with data in HISTORICAL")
def list_historical_teams(
    season: Optional[str] = Query(None, description="Filter by season, e.g. '2024-25'"),
    db=Depends(get_db),
) -> List[Dict[str, str]]:
    """Return distinct teams (team_id + team_name) from HISTORICAL.

    Args:
        season: Optional season filter.

    Returns:
        List of ``{team_id, team_name}`` dicts, sorted alphabetically by name.
    """
    from src.database.historical_repository import HistoricalRepository

    repo = HistoricalRepository(db.connection)
    return repo.list_teams(season)


# ---------------------------------------------------------------------------
# Background task implementations
# ---------------------------------------------------------------------------

def _run_feb_ingest(
    job_id: str,
    seasons: List[FEBSeasonParams],
    db: Any,
) -> None:
    """Background task: ingest a list of FEB seasons sequentially."""
    from src.database.historical_repository import HistoricalRepository
    from src.services.historical_ingestion_service import HistoricalIngestionService

    job = HISTORICAL_JOBS[job_id]
    repo = HistoricalRepository(db.connection)
    svc = HistoricalIngestionService(repo)

    try:
        for season_params in seasons:
            job["current_season"] = season_params.normalized_season
            svc.ingest_feb_season(
                job=job,
                competition_url=season_params.competition_url,
                season_value=season_params.season_value,
                group_value=season_params.group_value,
                year=season_params.year,
                competition_label=season_params.competition_label,
                season_label=season_params.season_label,
                group_label=season_params.group_label,
                normalized_season=season_params.normalized_season,
            )
        job["status"] = "done"
        job["current_match"] = None
    except Exception as exc:
        job["status"] = "error"
        job["errors"].append(f"Fatal: {exc}")


def _run_fbcyl_ingest(
    job_id: str,
    seasons: List[FBCYLSeasonParams],
    db: Any,
) -> None:
    """Background task: ingest a list of FBCYL seasons sequentially."""
    from src.database.historical_repository import HistoricalRepository
    from src.services.historical_ingestion_service import HistoricalIngestionService

    job = HISTORICAL_JOBS[job_id]
    repo = HistoricalRepository(db.connection)
    svc = HistoricalIngestionService(repo)

    try:
        for season_params in seasons:
            job["current_season"] = season_params.normalized_season
            svc.ingest_fbcyl_season(
                job=job,
                competition_id=season_params.competition_id,
                season=season_params.season,
                gender=season_params.gender,
                territory=season_params.territory,
                category=season_params.category,
                competition_label=season_params.competition_label,
                normalized_season=season_params.normalized_season,
            )
        job["status"] = "done"
        job["current_match"] = None
    except Exception as exc:
        job["status"] = "error"
        job["errors"].append(f"Fatal: {exc}")


# ---------------------------------------------------------------------------
# New simplified competition ingestion (auto-discovers groups)
# ---------------------------------------------------------------------------

@router.post(
    "/ingest_competition",
    summary="Ingestar temporadas FEB descubriendo grupos automáticamente",
)
def start_competition_ingest(
    req: FEBCompetitionIngestRequest,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
) -> Dict[str, str]:
    """Queue a background job that auto-discovers all groups for each selected season.

    Unlike ``POST /historical/ingest``, the caller does **not** need to specify
    groups — the backend queries the FEB calendar page for each season and
    ingests every group it finds.

    Args:
        req: Competition URL, label, year hint, and the list of seasons to ingest.

    Returns:
        ``{job_id}`` — poll ``GET /historical/progress/{job_id}``.
    """
    if not req.seasons:
        raise HTTPException(status_code=422, detail="seasons list cannot be empty.")

    job_id = str(_uuid.uuid4())
    HISTORICAL_JOBS[job_id] = {
        "status": "starting",
        "total": 0,
        "done": 0,
        "errors": [],
        "current_season": None,
        "current_match": None,
    }

    background_tasks.add_task(_run_feb_competition_ingest, job_id, req, db)
    return {"job_id": job_id}


def _run_feb_competition_ingest(
    job_id: str,
    req: FEBCompetitionIngestRequest,
    db: Any,
) -> None:
    """Background task: discover groups then ingest all seasons."""
    from src.database.historical_repository import HistoricalRepository
    from src.services.historical_ingestion_service import HistoricalIngestionService

    job = HISTORICAL_JOBS[job_id]
    repo = HistoricalRepository(db.connection)
    svc = HistoricalIngestionService(repo)

    try:
        svc.ingest_feb_competition(
            job=job,
            competition_url=req.competition_url,
            competition_label=req.competition_label,
            year=req.year,
            seasons=[s.model_dump() for s in req.seasons],
        )
        job["status"] = "done"
        job["current_match"] = None
    except Exception as exc:
        job["status"] = "error"
        job["errors"].append(f"Fatal: {exc}")
