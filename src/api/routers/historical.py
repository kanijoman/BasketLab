"""Historical router — what is stored in the HISTORICAL collection (read only).

The ingestion endpoints (a background job that downloaded seasons into HISTORICAL, and its progress) are gone (issue #724, towards switching Render off): the server takes no
writes from the web any more. HISTORICAL feeds the predictive analysis, which is out of the web while it is reworked; its reads stay for the kept code. The ingestion service
(``historical_ingestion_service``) and the repository are kept too.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_db

router = APIRouter()


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
