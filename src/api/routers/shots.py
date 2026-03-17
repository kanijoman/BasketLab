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

import math
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_db
from utils.collection_utils import is_fbcyl as _is_fbcyl

router = APIRouter()

# ---------------------------------------------------------------------------
# FIBA half-court geometry constants (metres)
# ---------------------------------------------------------------------------
_BASKET_X = 7.5
_BASKET_Y = 1.575
_THREE_RADIUS = 6.75
_THREE_CORNER_X_LEFT = 0.9     # Left straight side of 3pt line
_THREE_CORNER_X_RIGHT = 14.1   # Right straight side
_RESTRICTED_RADIUS = 1.25
_KEY_HALF_WIDTH = 2.45         # Key is 4.9 m wide
_KEY_DEPTH = 5.8               # Key depth from baseline

# Height at which the 3pt arc meets the straight-side segments
_BREAK_Y = _BASKET_Y + math.sqrt(
    _THREE_RADIUS ** 2 - (_BASKET_X - _THREE_CORNER_X_LEFT) ** 2
)

# Zone metadata: (id, label, is_three_point)
_ZONE_META: Dict[str, Dict[str, Any]] = {
    "restricted_area": {"label": "Zona Restringida",   "points": 2},
    "paint":           {"label": "Pintura",            "points": 2},
    "mid_left":        {"label": "Media Izquierda",    "points": 2},
    "mid_center":      {"label": "Media Centro",       "points": 2},
    "mid_right":       {"label": "Media Derecha",      "points": 2},
    "corner_left":     {"label": "Triple Esquina Izq", "points": 3},
    "wing_left":       {"label": "Triple Ala Izq",     "points": 3},
    "top_three":       {"label": "Triple Centro",      "points": 3},
    "wing_right":      {"label": "Triple Ala Der",     "points": 3},
    "corner_right":    {"label": "Triple Esquina Der", "points": 3},
}

# ---------------------------------------------------------------------------
# Zone classification (pure geometry, no Shapely dependency)
# ---------------------------------------------------------------------------

def _dist(x: float, y: float) -> float:
    return math.sqrt((x - _BASKET_X) ** 2 + (y - _BASKET_Y) ** 2)


def _is_three_pt(x: float, y: float) -> bool:
    """True if FIBA-coordinate shot (x, y) is beyond the 3-point line."""
    if y <= _BREAK_Y:
        # Straight-side zone: 3pt if outside the side lines
        return x < _THREE_CORNER_X_LEFT or x > _THREE_CORNER_X_RIGHT
    return _dist(x, y) >= _THREE_RADIUS


def _classify_zone(x: float, y: float) -> str:
    """Return the zone key for a FIBA-coordinate shot at (x, y)."""
    d = _dist(x, y)

    if d <= _RESTRICTED_RADIUS:
        return "restricted_area"

    three = _is_three_pt(x, y)

    if not three:
        # Two-point shot — determine sub-zone
        in_key_x = (_BASKET_X - _KEY_HALF_WIDTH) <= x <= (_BASKET_X + _KEY_HALF_WIDTH)
        in_key_y = y <= _KEY_DEPTH
        if in_key_x and in_key_y:
            return "paint"
        if x < _BASKET_X - _KEY_HALF_WIDTH:
            return "mid_left"
        if x > _BASKET_X + _KEY_HALF_WIDTH:
            return "mid_right"
        return "mid_center"

    # Three-point shot — determine sub-zone
    if y <= _BREAK_Y:
        return "corner_left" if x < _THREE_CORNER_X_LEFT else "corner_right"
    if x < _BASKET_X - 1.5:
        return "wing_left"
    if x > _BASKET_X + 1.5:
        return "wing_right"
    return "top_three"


# ---------------------------------------------------------------------------
# Coordinate conversion (FEB 0-100 → FIBA metres)
# ---------------------------------------------------------------------------

_COURT_LENGTH = 28.0
_COURT_WIDTH = 15.0


def _feb_to_fiba(x_feb: float, y_feb: float, team: int) -> tuple[float, float]:
    """Convert FEB percentage coords to FIBA half-court metres."""
    x_m = (x_feb / 100.0) * _COURT_LENGTH
    y_m = (y_feb / 100.0) * _COURT_WIDTH

    # Distance from attacking basket
    dist = x_m if team == 0 else (_COURT_LENGTH - x_m)

    # Mirror defensive-half shots to offensive half
    if dist > _COURT_LENGTH / 2:
        y_fiba = _COURT_LENGTH - dist
        x_fiba = _COURT_WIDTH - y_m
    else:
        y_fiba = dist
        x_fiba = y_m

    return (x_fiba, y_fiba)


# ---------------------------------------------------------------------------
# MongoDB extraction helpers
# ---------------------------------------------------------------------------

def _extract_shots_feb(coll, team_filter: Optional[str], player_filter: Optional[str]) -> List[Dict]:
    """Retrieve and classify FEB shots from a MongoDB collection."""
    # Pull only the fields we need for performance
    projection = {
        "SHOTCHART.SHOTS": 1,
        "HEADER.TEAM.name": 1,
    }
    cursor = coll.find({"SHOTCHART.SHOTS": {"$exists": True}}, projection)

    all_shots: List[Dict] = []
    for doc in cursor:
        header_teams = doc.get("HEADER", {}).get("TEAM", [])
        local_name = header_teams[0].get("name") if len(header_teams) > 0 else None
        away_name  = header_teams[1].get("name") if len(header_teams) > 1 else None

        shots_raw = doc.get("SHOTCHART", {}).get("SHOTS", [])
        for s in shots_raw:
            team_idx = s.get("team")   # 0 or 1
            if team_idx not in (0, 1):
                continue
            team_name = local_name if team_idx == 0 else away_name

            # Apply team filter
            if team_filter and team_name != team_filter:
                continue
            # Apply player filter
            player_id = str(s.get("player", ""))
            if player_filter and player_id != player_filter:
                continue

            x_pct = float(s.get("x", 0))
            y_pct = float(s.get("y", 0))
            made   = int(s.get("m", 0)) == 1
            x_fiba, y_fiba = _feb_to_fiba(x_pct, y_pct, team_idx)
            zone = _classify_zone(x_fiba, y_fiba)

            all_shots.append({
                "zone": zone,
                "made": made,
            })
    return all_shots


def _aggregate_zones(shots: List[Dict]) -> List[Dict[str, Any]]:
    """Sum shots per zone and compute FG%."""
    accum: Dict[str, Dict[str, int]] = {z: {"fga": 0, "fgm": 0} for z in _ZONE_META}
    for s in shots:
        z = s["zone"]
        if z in accum:
            accum[z]["fga"] += 1
            if s["made"]:
                accum[z]["fgm"] += 1

    result = []
    for zone_key, meta in _ZONE_META.items():
        fga = accum[zone_key]["fga"]
        fgm = accum[zone_key]["fgm"]
        result.append({
            "zone":       zone_key,
            "zone_label": meta["label"],
            "points":     meta["points"],
            "fga":        fga,
            "fgm":        fgm,
            "fg_pct":     round(fgm / fga * 100, 1) if fga > 0 else 0.0,
        })
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{collection}", summary="Aggregated shot-zone stats for a collection")
def get_shot_zones(
    collection: str,
    team: Optional[str] = Query(None, description="Filter by exact team name"),
    player: Optional[str] = Query(None, description="Filter by player ID"),
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return shooting percentages by court zone.

    Only FEB collections contain individual shot coordinates.
    FBCYL collections return an empty list.

    Args:
        collection: MongoDB collection name.
        team: Optional exact team name filter.
        player: Optional player ID filter.

    Returns:
        List of 10 zone objects with ``zone``, ``zone_label``, ``points``,
        ``fga``, ``fgm``, ``fg_pct``.
    """
    if _is_fbcyl(collection):
        # FBCYL has no individual shot coordinates
        return []

    try:
        coll = db.connection.get_collection(collection)
        shots = _extract_shots_feb(coll, team_filter=team, player_filter=player)
        return _aggregate_zones(shots)
    except Exception:
        return []
