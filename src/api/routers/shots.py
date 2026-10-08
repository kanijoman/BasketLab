"""Shot-chart router — aggregated zone stats from FEB SHOTCHART data.

Returns zone-level shooting summaries (FGA, FGM, FG%) for a team or player
across all games in a collection.  Coordinate conversion follows the same
FIBA half-court system used by the desktop shot-chart module.

FBCYL collections do not carry individual shot coordinates, so an empty
list is returned for those collections.

Zones (10 total, FIBA half-court):
    1  restricted_area   — distance ≤ 1.25 m from basket
    2  paint             — key area (non-restricted)
    3  mid_left          — 2pt, left of the key
    4  mid_center        — 2pt, above the key
    5  mid_right         — 2pt, right of the key
    6  corner_left       — 3pt corner, left side (x < 0.9 m)
    7  wing_left         — 3pt left wing (above break)
    8  top_three         — 3pt near the top of the arc
    9  wing_right        — 3pt right wing (above break)
    10 corner_right      — 3pt corner, right side (x > 14.1 m)
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_db
from src.shotcharts.zone_rating import rate_zones
from src.shotcharts.feb_zones import (  # noqa: F401  (private aliases kept for existing tests)
    ZONE_META as _ZONE_META,
    aggregate_zones as _aggregate_zones,
    classify_zone as _classify_zone,
    extract_shots_feb as _extract_shots_feb,
    stream_zone_counts_feb as _stream_zone_counts_feb,
)
from utils.collection_utils import is_fbcyl as _is_fbcyl

router = APIRouter()

@router.get("/{collection}", summary="Aggregated shot-zone stats for a collection")
def get_shot_zones(
    collection: str,
    team_id: Optional[str] = Query(None, description="Filter by stable team ID"),
    player: Optional[str] = Query(None, description="Filter by player ID"),
    compare: Optional[Literal["league"]] = Query(
        None, description="'league' adds rating/league_pct/delta_pp/low_sample per zone"),
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return shooting percentages by court zone.

    Only FEB collections contain individual shot coordinates.
    FBCYL collections return an empty list.

    Args:
        collection: MongoDB collection name.
        team_id: Optional stable team ID (``HEADER.TEAM.id``).
        player: Optional player ID filter.
        compare: ``league`` rates each zone against the league average for that zone.

    Returns:
        List of 10 zone objects with ``zone``, ``zone_label``, ``points``,
        ``fga``, ``fgm``, ``fg_pct`` (+ ``rating``, ``league_pct``, ``delta_pp``,
        ``low_sample`` when ``compare=league``).
    """
    if _is_fbcyl(collection):
        return []

    try:
        coll = db.connection.get_collection(collection)
        accum = _stream_zone_counts_feb(coll, team_id=team_id, player_filter=player)
        zones = _aggregate_zones(accum)
        if compare != "league":
            return zones
        if team_id or player:
            accum = _stream_zone_counts_feb(coll, team_id=None, player_filter=None)
        return rate_zones(zones, _aggregate_zones(accum))
    except Exception:
        return []


@router.get("/{collection}/raw", summary="Individual shot coordinates for scatter/heatmap")
def get_shot_raw(
    collection: str,
    team_id: Optional[str] = Query(None, description="Filter by stable team ID"),
    player: Optional[str] = Query(None, description="Filter by player ID"),
    limit: int = Query(5000, ge=1, le=10000),
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return individual shot coordinates in FIBA metres.

    Only FEB collections contain individual shot coordinates.
    FBCYL collections return an empty list.

    Args:
        collection: MongoDB collection name.
        team_id: Optional stable team ID (``HEADER.TEAM.id``).
        player: Optional player ID filter.
        limit: Maximum shots to return (default 5000, max 10000).

    Returns:
        List of shot dicts each with ``x`` (0-15), ``y`` (0-14),
        ``made`` (bool) and ``zone`` (str).
    """
    if _is_fbcyl(collection):
        return []

    try:
        coll = db.connection.get_collection(collection)
        shots = _extract_shots_feb(coll, team_id=team_id, player_filter=player)
        return [
            {"x": s["x"], "y": s["y"], "made": s["made"], "zone": s["zone"]}
            for s in shots[:limit]
        ]
    except Exception:
        return []
