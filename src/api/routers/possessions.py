"""Possessions router — per-team pace and efficiency stats.

Exposes pace (possessions per game), Offensive Efficiency Rating (OER),
Defensive Efficiency Rating (DER) and net rating for all teams in a
collection.  These values are computed by the existing team-stats
aggregation pipeline — no extra DB passes are needed.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from src.api.deps import get_db
from src.services import TeamStatsService

router = APIRouter()


@router.get("/{collection}", summary="Per-team pace and efficiency ratings")
def get_possession_stats(
    collection: str,
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return pace / OER / DER stats for every team in *collection*.

    The scatter quadrants of the PossessionsPage use:

    * **X axis** — ``pace`` (possessions per game)
    * **Y axis** — ``oer`` (offensive efficiency rating = points per 100 poss.)

    Four quadrants are labelled based on league median:
    fast+efficient, fast+inefficient, slow+efficient, slow+inefficient.

    Args:
        collection: MongoDB collection name.

    Returns:
        List of dicts with ``team_name``, ``pace``, ``oer``, ``der``,
        ``net_rating``, ``possessions_per_game``, ``total_games``.
    """
    svc = TeamStatsService(db)
    return svc.get_possession_stats(collection)
