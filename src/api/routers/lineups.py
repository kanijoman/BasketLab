"""Lineups router — player combination analysis."""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_db
from src.services import LineupService

router = APIRouter()

ALLOWED_STATS = {
    'net_rating', 'plus_minus', 'points_for', 'points_against',
    'ortg', 'drtg', 'efg_pct', 'tov_pct', 'orb_pct', 'ftr',
    'ast', 'trb',
}


@router.get("/{collection}/{team_id}", summary="Analyse player lineup combinations for a team")
def get_lineup_analysis(
    collection: str,
    team_id: str,
    team_name: str = Query(..., description="Human-readable team name"),
    size: int = Query(5, ge=2, le=5, description="Players per lineup (2-5)"),
    stat: str = Query("net_rating", description="Stat to sort by"),
    period: int = Query(0, ge=0, description="Days back filter (0 = full season)"),
    include_game_log: bool = Query(False, description="Include per-game breakdown in response"),
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return player combinations sorted by the chosen stat.

    Args:
        collection: MongoDB collection name, e.g. ``FEB_LF2_2025_A``.
        team_id: Team identifier (FEB numeric string or FBCYL UUID-like).
        team_name: Human-readable team name for display purposes.
        size: Number of players per lineup group (default 5).
        stat: Stat key to sort by (default ``net_rating``).
        period: Number of days to look back; 0 means the full season.
        include_game_log: When True, each lineup includes a ``game_log`` list.

    Returns:
        List of lineup dicts sorted by ``stat`` (descending for higher-is-better
        stats, ascending for ``drtg`` and ``tov_pct``).
    """
    if stat not in ALLOWED_STATS:
        raise HTTPException(status_code=400, detail=f"Invalid stat '{stat}'. Allowed: {sorted(ALLOWED_STATS)}")

    date_filter: Optional[Dict] = None
    if period > 0:
        cutoff = datetime.utcnow() - timedelta(days=period)
        date_filter = {"$gte": cutoff.strftime("%Y-%m-%d")}

    svc = LineupService(db)
    return svc.get_lineup_analysis(
        collection,
        team_id,
        team_name,
        combination_size=size,
        stat=stat,
        date_filter=date_filter,
        include_game_log=include_game_log,
    )
