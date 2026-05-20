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

def _build_dorsal_to_id_map(shotchart: dict) -> dict:
    """Build a (team_idx, dorsal_str) → player_id lookup from SHOTCHART.TEAM.

    SHOTCHART.SHOTS[].player stores the dorsal number, not the player ID.
    SHOTCHART.TEAM[n].PLAYER[].id holds the actual player identifier that
    matches PlayerStat.player_id from the stats aggregation pipeline.
    """
    mapping: dict = {}
    # SHOTCHART.TEAM is a list ordered by team slot (0 = local, 1 = away)
    for t_idx, team_entry in enumerate(shotchart.get("TEAM", [])):
        for player in team_entry.get("PLAYER", []):
            raw_no = str(player.get("no", ""))
            stripped = raw_no.lstrip("0") or raw_no  # "05" → "5", but "0" → "0"
            pid = str(player.get("id", ""))
            if pid:
                mapping[(t_idx, raw_no)] = pid
                mapping[(t_idx, stripped)] = pid
    return mapping


def _extract_shots_feb(coll, team_id: Optional[str], player_filter: Optional[str]) -> List[Dict]:
    """Retrieve and classify FEB shots from a MongoDB collection.

    Filters by ``HEADER.TEAM.id`` (indexed, sponsor-change safe) when
    ``team_id`` is provided, avoiding a full-collection scan.
    """
    # Include SHOTCHART.TEAM so we can resolve dorsal → player_id per game
    projection = {
        "SHOTCHART.SHOTS": 1,
        "SHOTCHART.TEAM": 1,
        "HEADER.TEAM": 1,
    }
    query: dict = {"SHOTCHART.SHOTS": {"$exists": True}}
    if team_id:
        query["HEADER.TEAM.id"] = team_id
    cursor = coll.find(query, projection)

    all_shots: List[Dict] = []
    for doc in cursor:
        header_teams = doc.get("HEADER", {}).get("TEAM", [])

        # Determine which team slot (0 or 1) belongs to our team_id
        team_idx_filter: Optional[int] = None
        if team_id:
            for idx, t in enumerate(header_teams):
                if str(t.get("id", "")) == str(team_id):
                    team_idx_filter = idx
                    break
            if team_idx_filter is None:
                continue  # doc matched the index but id not found in array — skip

        shotchart = doc.get("SHOTCHART", {})
        # Build dorsal→player_id map for this game (needed for player filter)
        dorsal_map = _build_dorsal_to_id_map(shotchart) if player_filter else {}

        shots_raw = shotchart.get("SHOTS", [])
        for s in shots_raw:
            # FEB scraper stores team as a string ("0" / "1") in MongoDB — cast to int
            try:
                t_idx = int(s.get("team"))
            except (TypeError, ValueError):
                continue
            if t_idx not in (0, 1):
                continue

            # Apply team filter: only include our team's shots
            if team_idx_filter is not None and t_idx != team_idx_filter:
                continue

            # Apply player filter: resolve dorsal to actual player ID before comparing
            if player_filter:
                dorsal = str(s.get("player", ""))
                resolved_id = dorsal_map.get((t_idx, dorsal), "")
                if resolved_id != player_filter:
                    continue

            x_pct = float(s.get("x", 0))
            y_pct = float(s.get("y", 0))
            made   = int(s.get("m", 0)) == 1
            x_fiba, y_fiba = _feb_to_fiba(x_pct, y_pct, t_idx)
            zone = _classify_zone(x_fiba, y_fiba)

            all_shots.append({
                "zone": zone,
                "made": made,
                "x":    x_fiba,
                "y":    y_fiba,
            })
    return all_shots


def _stream_zone_counts_feb(
    coll, team_id: Optional[str], player_filter: Optional[str]
) -> Dict[str, Dict[str, int]]:
    """Count FEB shots per zone using O(1) memory (no ``all_shots`` list).

    Streams the cursor and accumulates zone counters in-place.  The
    zones endpoint uses this instead of building an intermediate list.

    Returns:
        Dict mapping zone key → ``{"fga": int, "fgm": int}``.
    """
    accum: Dict[str, Dict[str, int]] = {z: {"fga": 0, "fgm": 0} for z in _ZONE_META}

    # Projection: skip SHOTCHART.TEAM unless we need the dorsal map
    projection: Dict[str, int] = {"SHOTCHART.SHOTS": 1, "HEADER.TEAM": 1}
    if player_filter:
        projection["SHOTCHART.TEAM"] = 1

    query: dict = {"SHOTCHART.SHOTS": {"$exists": True}}
    if team_id:
        query["HEADER.TEAM.id"] = team_id
    cursor = coll.find(query, projection)

    for doc in cursor:
        header_teams = doc.get("HEADER", {}).get("TEAM", [])

        team_idx_filter: Optional[int] = None
        if team_id:
            for idx, t in enumerate(header_teams):
                if str(t.get("id", "")) == str(team_id):
                    team_idx_filter = idx
                    break
            if team_idx_filter is None:
                continue

        shotchart = doc.get("SHOTCHART", {})
        dorsal_map = _build_dorsal_to_id_map(shotchart) if player_filter else {}

        for s in shotchart.get("SHOTS", []):
            try:
                t_idx = int(s.get("team"))
            except (TypeError, ValueError):
                continue
            if t_idx not in (0, 1):
                continue
            if team_idx_filter is not None and t_idx != team_idx_filter:
                continue
            if player_filter:
                dorsal = str(s.get("player", ""))
                if dorsal_map.get((t_idx, dorsal), "") != player_filter:
                    continue

            x_pct = float(s.get("x", 0))
            y_pct = float(s.get("y", 0))
            made   = int(s.get("m", 0)) == 1
            x_fiba, y_fiba = _feb_to_fiba(x_pct, y_pct, t_idx)
            zone = _classify_zone(x_fiba, y_fiba)
            if zone in accum:
                accum[zone]["fga"] += 1
                if made:
                    accum[zone]["fgm"] += 1

    return accum


def _aggregate_zones(accum: Dict[str, Dict[str, int]]) -> List[Dict[str, Any]]:
    """Build the zone-stats response list from a ``{zone: {fga, fgm}}`` accumulator."""
    result = []
    for zone_key, meta in _ZONE_META.items():
        fga = accum.get(zone_key, {}).get("fga", 0)
        fgm = accum.get(zone_key, {}).get("fgm", 0)
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
    team_id: Optional[str] = Query(None, description="Filter by stable team ID"),
    player: Optional[str] = Query(None, description="Filter by player ID"),
    db=Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return shooting percentages by court zone.

    Only FEB collections contain individual shot coordinates.
    FBCYL collections return an empty list.

    Args:
        collection: MongoDB collection name.
        team_id: Optional stable team ID (``HEADER.TEAM.id``).
        player: Optional player ID filter.

    Returns:
        List of 10 zone objects with ``zone``, ``zone_label``, ``points``,
        ``fga``, ``fgm``, ``fg_pct``.
    """
    if _is_fbcyl(collection):
        return []

    try:
        coll = db.connection.get_collection(collection)
        accum = _stream_zone_counts_feb(coll, team_id=team_id, player_filter=player)
        return _aggregate_zones(accum)
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
