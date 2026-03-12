"""Players router — per-player statistics and IN/OUT analysis."""

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
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return aggregated per-player statistics for all players in *collection*.

    Args:
        collection: MongoDB collection name, e.g. ``FEB_LF2_2025_A``.
        venue: Optional venue filter — ``"home"`` or ``"away"``.
        result: Optional result filter — ``"won"`` or ``"lost"``.

    Returns:
        List of player stat dicts (one per player).
    """
    svc = PlayerStatsService(db)
    venue_filter = True if venue == "home" else (False if venue == "away" else None)
    return svc.load_season_data(
        collection,
        venue_filter=venue_filter,
        result_filter=result,
    )


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
