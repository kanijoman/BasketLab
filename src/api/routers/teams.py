"""Teams router — season statistics for all teams in a collection."""

from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_db
from src.services import TeamStatsService

router = APIRouter()

# Allowed stat keys for the evolution endpoint
_VALID_EVOLUTION_STATS = frozenset({
    "points", "assists", "rebounds", "steals", "turnovers", "blocks",
})


@router.get("/{collection}", summary="Get all team stats for a collection")
def get_team_stats(
    collection: str,
    venue: Optional[str] = Query(None, description="home | away | null for all"),
    result: Optional[str] = Query(None, description="won | lost | null for all"),
    from_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    to_date:   Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    db=Depends(get_db),
) -> Dict[str, List[Dict[str, Any]]]:
    """Return aggregated team statistics for all clubs in *collection*.

    Args:
        collection: MongoDB collection name, e.g. ``FEB_LF2_2025_A``.
        venue: Optional venue filter — ``"home"`` or ``"away"``.
        result: Optional result filter — ``"won"`` or ``"lost"``.
        from_date: Optional start date (inclusive), format ``YYYY-MM-DD``.
        to_date: Optional end date (inclusive), format ``YYYY-MM-DD``.

    Returns:
        Object with ``team_stats`` and ``opponent_stats`` lists.
    """
    svc = TeamStatsService(db)
    venue_filter = True if venue == "home" else (False if venue == "away" else None)
    date_filter: Optional[Dict] = None
    if from_date or to_date:
        date_filter = {}
        if from_date:
            date_filter["$gte"] = datetime.fromisoformat(from_date)
        if to_date:
            date_filter["$lte"] = datetime.fromisoformat(to_date)
    return svc.load_season_data(
        collection,
        date_filter=date_filter,
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


@router.get("/{collection}/consistency", summary="Get per-team intra-game consistency stats")
def get_consistency(collection: str, db=Depends(get_db)) -> Dict[str, Any]:
    """Return per-team std dev and CV for key stats computed across all games.

    Each value in the response captures how *variable* a team is game-to-game
    for that statistic (not how they compare to the rest of the league).

    Only available for FEB collections; returns an empty dict for FBCYL.

    Args:
        collection: MongoDB collection name.

    Returns:
        ``{team_name: {stat_key: {"mean", "std", "cv", "n"}}}``
    """
    svc = TeamStatsService(db)
    return svc.get_consistency(collection)


@router.get(
    "/{collection}/evolution/{team_name}",
    summary="Get game-by-game stat evolution for a team",
)
def get_team_evolution(
    collection: str,
    team_name: str,
    stat: str = Query("points", description="Stat key: points | assists | rebounds | steals | turnovers | blocks"),
    window: int = Query(5, ge=2, le=15, description="Rolling-average window in games (2–15)"),
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return chronological game-by-game values for a single stat, with rolling average.

    Args:
        collection: MongoDB collection name.
        team_name: Exact team name as stored in the DB.
        stat: Stat key — one of ``points``, ``assists``, ``rebounds``,
            ``steals``, ``turnovers``, ``blocks``.
        window: Rolling-average window size (default 5 games).

    Returns:
        Ordered list of ``{game_number, game_date, opponent, value, rolling_avg, won}``.
    """
    if stat not in _VALID_EVOLUTION_STATS:
        stat = "points"
    svc = TeamStatsService(db)
    return svc.get_team_evolution(collection, team_name, stat=stat, rolling_window=window)
