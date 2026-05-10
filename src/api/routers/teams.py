"""Teams router — season statistics for all teams in a collection."""

from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_db
from src.services import TeamStatsService, EvolutionService, EVOLUTION_STAT_KEYS

router = APIRouter()

# All supported stat keys for evolution endpoints (from EvolutionService)
_VALID_EVOLUTION_STATS = EVOLUTION_STAT_KEYS


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
def list_teams(
    collection: str,
    skip: int = Query(0, ge=0, description="Number of teams to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum teams to return"),
    db=Depends(get_db),
) -> List[str]:
    """Return a sorted list of all team names present in the collection.

    Args:
        collection: MongoDB collection name.
        skip: Pagination offset (default 0).
        limit: Max results per page (default 100, max 500).

    Returns:
        Sorted list of name strings.
    """
    svc = TeamStatsService(db)
    teams = svc.get_all_teams(collection)
    return teams[skip: skip + limit]


@router.get(
    "/{collection}/rival-adjusted",
    summary="Estadísticas descriptivas ajustadas por calidad del rival",
)
def get_rival_adjusted(
    collection: str,
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Return per-team advanced stats adjusted for opponent seasonal quality.

    For each game, each stat is weighted by the rival's seasonal defensive
    (or offensive) quality using a proportional formula::

        adj_game = raw_game * (league_avg_context / rival_seasonal_context)

    For ``net_rtg`` (signed), an additive form is used::

        adj_game = raw_game + (rival_net_rtg - league_avg_net_rtg)

    Args:
        collection: MongoDB collection name.

    Returns:
        ``{team_name: {stat_key: {raw_avg, adj_avg, adj, sos, n}}}``
    """
    from src.services.rival_adjusted_service import RivalAdjustedService
    svc = RivalAdjustedService(db)
    return svc.get_rival_adjusted_stats(collection)


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
    stat: str = Query("points", description="Stat key — see EVOLUTION_STAT_KEYS for full list"),
    window: int = Query(5, ge=2, le=15, description="Rolling-average window in games (2–15)"),
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return chronological game-by-game values for a single stat with rolling and cumulative averages.

    Args:
        collection: MongoDB collection name.
        team_name: Exact team name as stored in the DB.
        stat: Any key from ``EVOLUTION_STAT_KEYS`` (30+ stats supported).
        window: Rolling-average window size (default 5 games).

    Returns:
        Ordered list of ``{game_number, game_date, opponent, value, rolling_avg, cumulative_avg, won}``.
    """
    if stat not in _VALID_EVOLUTION_STATS:
        stat = "points"
    svc = EvolutionService(db)
    return svc.get_team_evolution(collection, team_name, stat=stat, rolling_window=window)


@router.get(
    "/{collection}/competition-evolution",
    summary="Get competition-wide rolling and cumulative averages by game index",
)
def get_competition_evolution(
    collection: str,
    stat: str = Query("points", description="Stat key — see EVOLUTION_STAT_KEYS for full list"),
    window: int = Query(5, ge=2, le=15, description="Rolling-average window in games (2–15)"),
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return competition-wide rolling and cumulative averages aligned by game index.

    For each game position P_i, averages all teams' rolling and cumulative averages.
    Teams with fewer games than i do not contribute at that position.

    Args:
        collection: MongoDB collection name.
        stat: Any key from ``EVOLUTION_STAT_KEYS``.
        window: Rolling-average window size (default 5 games).

    Returns:
        List of ``{game_number, competition_rolling, competition_cumulative}``.
    """
    if stat not in _VALID_EVOLUTION_STATS:
        stat = "points"
    svc = EvolutionService(db)
    return svc.get_competition_evolution(collection, stat=stat, rolling_window=window)
