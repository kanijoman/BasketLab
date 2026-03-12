"""Lineups router — player combination analysis."""

from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_db
from src.services import LineupService

router = APIRouter()


@router.get("/{collection}/{team_id}", summary="Analyse player lineup combinations for a team")
def get_lineup_analysis(
    collection: str,
    team_id: str,
    team_name: str = Query(..., description="Human-readable team name"),
    size: int = Query(5, ge=2, le=5, description="Players per lineup (2-5)"),
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return best and worst player combinations sorted by net rating.

    Args:
        collection: MongoDB collection name, e.g. ``FEB_LF2_2025_A``.
        team_id: Team identifier (FEB numeric string or FBCYL UUID-like).
        team_name: Human-readable team name for display purposes.
        size: Number of players per lineup group (default 5).

    Returns:
        List of lineup dicts, each containing player names, minutes played,
        points for/against, and net rating — sorted descending by net rating.
    """
    svc = LineupService(db)
    return svc.get_lineup_analysis(
        collection,
        team_id,
        team_name,
        combination_size=size,
    )
