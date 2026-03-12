"""Teams router — season statistics for all teams in a collection."""

from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_db
from src.services import TeamStatsService

router = APIRouter()


@router.get("/{collection}", summary="Get all team stats for a collection")
def get_team_stats(
    collection: str,
    venue: Optional[str] = Query(None, description="home | away | null for all"),
    result: Optional[str] = Query(None, description="won | lost | null for all"),
    db=Depends(get_db),
) -> Dict[str, List[Dict[str, Any]]]:
    """Return aggregated team statistics for all clubs in *collection*.

    Args:
        collection: MongoDB collection name, e.g. ``FEB_LF2_2025_A``.
        venue: Optional venue filter — ``"home"`` or ``"away"``.
        result: Optional result filter — ``"won"`` or ``"lost"``.

    Returns:
        Object with ``team_stats`` and ``opponent_stats`` lists.
    """
    svc = TeamStatsService(db)
    venue_filter = True if venue == "home" else (False if venue == "away" else None)
    return svc.load_season_data(
        collection,
        venue_filter=venue_filter,
        result_filter=result,
    )


@router.get("/{collection}/quartiles", summary="Get league-wide stat quartiles")
def get_quartiles(collection: str, db=Depends(get_db)) -> Dict[str, Any]:
    """Return Q1/Q2/Q3/Q4 thresholds for the main stats in *collection*.

    Used by the front-end to colour-code cells (green = top quartile, red = bottom).

    Args:
        collection: MongoDB collection name.

    Returns:
        Per-stat quartile dict, e.g. ``{"points_per_game": {"q1": 70, "q2": 78, …}}``.
    """
    svc = TeamStatsService(db)
    return svc.get_quartiles(collection)


@router.get("/{collection}/teams", summary="List team names in a collection")
def list_teams(collection: str, db=Depends(get_db)) -> List[str]:
    """Return a sorted list of all team names present in the collection.

    Args:
        collection: MongoDB collection name.

    Returns:
        Sorted list of name strings.
    """
    svc = TeamStatsService(db)
    return svc.get_all_teams(collection)
