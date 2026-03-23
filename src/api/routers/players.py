"""Players router — per-player statistics and IN/OUT analysis."""

from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_db
from src.services import PlayerStatsService

router = APIRouter()


@router.get("/{collection}", summary="Get all player stats for a collection")
def get_player_stats(
    collection: str,
    venue: Optional[str] = Query(None, description="home | away | null for all"),
    result: Optional[str] = Query(None, description="won | lost | null for all"),
    from_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    to_date:   Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return aggregated per-player statistics for all players in *collection*.

    Args:
        collection: MongoDB collection name, e.g. ``FEB_LF2_2025_A``.
        venue: Optional venue filter — ``"home"`` or ``"away"``.
        result: Optional result filter — ``"won"`` or ``"lost"``.
        from_date: Optional start date (inclusive), format ``YYYY-MM-DD``.
        to_date: Optional end date (inclusive), format ``YYYY-MM-DD``.

    Returns:
        List of player stat dicts (one per player).
    """
    svc = PlayerStatsService(db)
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


@router.get("/{collection}/quartiles", summary="Get league-wide player stat quartiles")
def get_player_quartiles(collection: str, db=Depends(get_db)) -> Dict[str, Any]:
    svc = PlayerStatsService(db)
    return svc.get_quartiles(collection)


@router.get("/{collection}/consistency", summary="Get per-player intra-game consistency stats")
def get_player_consistency(collection: str, db=Depends(get_db)) -> Dict[str, Any]:
    """Return CV (coefficient of variation) per stat for each player.

    Computes how consistent each player is game-to-game across all their
    tracked stats.  Only available for FEB collections.

    Args:
        collection: MongoDB collection name.

    Returns:
        ``{player_id: {stat_key: {mean, std, cv, n}}}``
    """
    svc = PlayerStatsService(db)
    return svc.get_consistency(collection)


@router.get("/{collection}/inout/{player_id}", summary="IN/OUT impact analysis for a player")
def get_inout_analysis(
    collection: str,
    player_id: str,
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Return team performance metrics when a player is on vs off court.

    Runs a play-by-play analysis over all games in the collection to compute
    points-per-possession, efficiency differential, and per-stat splits.

    Args:
        collection: MongoDB collection name.
        player_id: Player identifier (FEB integer string or FBCYL UUID-like).

    Returns:
        Dict with ``in`` and ``out`` stat blocks, each containing shooting,
        rebounding, assists, turnovers and net rating.
    """
    svc = PlayerStatsService(db)
    return svc.get_in_out_analysis(collection, player_id)


@router.get("/{collection}/together/{player1_id}/{player2_id}", summary="Two-player together analysis")
def get_players_together(
    collection: str,
    player1_id: str,
    player2_id: str,
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Return team stats when two specific players are simultaneously on court.

    Args:
        collection: MongoDB collection name.
        player1_id: First player identifier.
        player2_id: Second player identifier.

    Returns:
        Combined stat dict for the shared court time.
    """
    svc = PlayerStatsService(db)
    return svc.get_players_together(collection, player1_id, player2_id)
