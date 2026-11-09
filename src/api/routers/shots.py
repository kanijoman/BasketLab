"""Shot-chart router — aggregated zone stats from FEB SHOTCHART data.

Returns zone-level shooting summaries (FGA, FGM, FG%) for a team or player
across all games in a collection.  Coordinate conversion follows the same
FIBA half-court system used by the desktop shot-chart module.

FBCYL carries its coordinates in the players' stats (``fbcyl_zones``): same zones, same answer.

Zones (10 total, FIBA half-court): those of the engine, ``live_core.zones`` (issue #452), the same ones the app
and the scouting reports say; ``feb_zones`` only classifies through it:
    restricted_area    — the rim, in front of the backboard (≤ 1.25 m from the basket)
    key_area           — the key (and what is behind the backboard)
    short_mid_range    — 2pt within 3.5 m of the basket, outside the key
    medium_mid_range   — 2pt between 3.5 and 5 m
    long_mid_range     — 2pt beyond 5 m
    left_corner_three, right_corner_three — 3pt corners (x < 0.9 m or x > 14.1 m)
    left_wing_three, right_wing_three     — 3pt wings (above the break)
    center_three       — 3pt in front of the key
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_db
from src.shotcharts.zone_distribution import zone_counts_by_owner
from src.shotcharts.zone_rating import rate_zones
from src.shotcharts.feb_zones import (  # noqa: F401  (private aliases kept for existing tests)
    ZONE_META as _ZONE_META,
    aggregate_zones as _aggregate_zones,
    classify_zone as _classify_zone,
    extract_shots_feb as _extract_shots_feb,
    stream_zone_counts_feb as _stream_zone_counts_feb,
)
from src.shotcharts.fbcyl_zones import extract_shots_fbcyl, stream_zone_counts_fbcyl
from utils.collection_utils import is_fbcyl as _is_fbcyl

router = APIRouter()


def _readers(collection: str):
    """(zone counter, shot extractor) for the collection's format (FEB or FBCYL)."""
    if _is_fbcyl(collection):
        return stream_zone_counts_fbcyl, extract_shots_fbcyl
    return _stream_zone_counts_feb, _extract_shots_feb


@router.get("/{collection}", summary="Aggregated shot-zone stats for a collection")
def get_shot_zones(
    collection: str,
    team_id: Optional[str] = Query(None, description="Filter by stable team ID"),
    player: Optional[str] = Query(None, description="Filter by player ID"),
    compare: Optional[Literal["league"]] = Query(
        None, description="'league' adds rating/league_pct/delta_pp/percentile/low_sample per zone"),
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return shooting percentages by court zone.

    Works for FEB (``SHOTCHART``) and FBCYL (per-player shooting coordinates).

    Args:
        collection: MongoDB collection name.
        team_id: Optional stable team ID (FEB ``HEADER.TEAM.id`` / FBCYL ``teamIdExtern``).
        player: Optional player ID filter (FEB id / FBCYL uuid).
        compare: ``league`` rates each zone against how the competition shoots there (#760): the quartiles of its teams, or of its players when a player is asked for,
            weighted by their attempts.

    Returns:
        List of 10 zone objects with ``zone``, ``zone_label``, ``points``,
        ``fga``, ``fgm``, ``fg_pct`` (+ ``rating``, ``league_pct``, ``delta_pp``,
        ``percentile``, ``low_sample`` when ``compare=league``).
    """
    try:
        stream, _ = _readers(collection)
        coll = db.connection.get_collection(collection)
        accum = stream(coll, team_id=team_id, player_filter=player)
        zones = _aggregate_zones(accum)
        if compare != "league":
            return zones
        owners = zone_counts_by_owner(coll, collection, "player" if player else "team")
        return rate_zones(zones, list(owners.values()))
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

    Works for FEB and FBCYL collections.

    Args:
        collection: MongoDB collection name.
        team_id: Optional stable team ID.
        player: Optional player ID filter.
        limit: Maximum shots to return (default 5000, max 10000).

    Returns:
        List of shot dicts each with ``x`` (0-15), ``y`` (0-14),
        ``made`` (bool) and ``zone`` (str).
    """
    try:
        _, extract = _readers(collection)
        coll = db.connection.get_collection(collection)
        shots = extract(coll, team_id=team_id, player_filter=player)
        return [
            {"x": s["x"], "y": s["y"], "made": s["made"], "zone": s["zone"]}
            for s in shots[:limit]
        ]
    except Exception:
        return []
