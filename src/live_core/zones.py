"""Court zones (10-zone FIBA system) in the standard library.

Analytic port of ``src.shotcharts.detailed_zones.DetailedCourtZones`` (which needs shapely):
same geometry (restricted area, key, mid-range rings at 3.5 / 5.0 m, corner threes below the
break, wings and centre above it), verified for parity against that implementation.

FEB shot coordinates are percentages of the full court; ``feb_to_fiba`` reproduces the
existing converter (everything is mirrored onto one half court). Because that mirroring
makes left/right unreliable, user-facing text uses zone FAMILIES (``zone_family``).
"""

from __future__ import annotations

import math
from typing import Any, Dict, Tuple

FEB_COURT_LENGTH = 28.0
FEB_COURT_WIDTH = 15.0

# Half-court geometry in metres (x across 0..15, y from the baseline 0..14).
WIDTH, HEIGHT = 15.0, 14.0
CX, HOOP_Y = WIDTH / 2, 1.575
BACKBOARD_Y = 1.2
KEY_HALF_WIDTH, KEY_HEIGHT = 4.9 / 2, 5.8
RESTRICTED_R = 1.25
THREE_R, THREE_SIDE = 6.75, 0.9
SHORT_MID_MAX, MEDIUM_MID_MAX = 3.5, 5.0
BREAK_Y = HOOP_Y + math.sqrt(THREE_R ** 2 - (CX - THREE_SIDE) ** 2)

ZONES: Dict[str, Dict[str, Any]] = {
    "restricted_area": {"points": 2, "name": "Área Restringida"},
    "key_area": {"points": 2, "name": "Zona"},
    "short_mid_range": {"points": 2, "name": "Tiro Corto"},
    "medium_mid_range": {"points": 2, "name": "Tiro Medio"},
    "long_mid_range": {"points": 2, "name": "Tiro Largo"},
    "left_corner_three": {"points": 3, "name": "Esquina Izq."},
    "left_wing_three": {"points": 3, "name": "45° Izq."},
    "center_three": {"points": 3, "name": "Centro Tres"},
    "right_wing_three": {"points": 3, "name": "45° Der."},
    "right_corner_three": {"points": 3, "name": "Esquina Der."},
}

_FAMILY = {
    "restricted_area": "aro", "key_area": "zona",
    "short_mid_range": "media distancia", "medium_mid_range": "media distancia",
    "long_mid_range": "media distancia",
    "left_corner_three": "esquina", "right_corner_three": "esquina",
    "left_wing_three": "ala", "right_wing_three": "ala", "center_three": "centro del arco",
}


def zone_family(zone: str) -> str:
    return _FAMILY[zone]


def feb_to_fiba(x_feb: float, y_feb: float, team: int) -> Tuple[float, float]:
    """FEB percentages (full court) -> FIBA half-court metres; same mirroring as the existing converter."""
    x_m = x_feb / 100.0 * FEB_COURT_LENGTH
    y_m = y_feb / 100.0 * FEB_COURT_WIDTH
    distance = x_m if team == 0 else FEB_COURT_LENGTH - x_m
    if distance > FEB_COURT_LENGTH / 2:
        return FEB_COURT_WIDTH - y_m, FEB_COURT_LENGTH - distance
    return y_m, distance


def _inside_two_point_area(x: float, y: float, dist: float) -> bool:
    return THREE_SIDE <= x <= WIDTH - THREE_SIDE and (y <= BREAK_Y or dist <= THREE_R)


def _zone_key(x: float, y: float) -> str:
    dist = math.hypot(x - CX, y - HOOP_Y)
    if y >= BACKBOARD_Y and ((y < HOOP_Y and abs(x - CX) <= RESTRICTED_R) or (y >= HOOP_Y and dist <= RESTRICTED_R)):
        return "restricted_area"
    if abs(x - CX) <= KEY_HALF_WIDTH and 0 <= y <= KEY_HEIGHT:
        return "key_area"
    if _inside_two_point_area(x, y, dist):
        if dist <= SHORT_MID_MAX:
            return "short_mid_range"
        return "medium_mid_range" if dist <= MEDIUM_MID_MAX else "long_mid_range"
    if y <= BREAK_Y and x < THREE_SIDE:
        return "left_corner_three"
    if y <= BREAK_Y and x > WIDTH - THREE_SIDE:
        return "right_corner_three"
    if abs(x - CX) <= KEY_HALF_WIDTH and y >= BREAK_Y:
        return "center_three"
    return "left_wing_three" if x <= CX else "right_wing_three"


def classify_fiba(x: float, y: float) -> Dict[str, Any]:
    """Zone of a point in FIBA half-court metres."""
    key = _zone_key(x, y)
    return {"zone": key, "points": ZONES[key]["points"], "name": ZONES[key]["name"]}


def classify_shot(shot: Dict[str, Any]) -> Dict[str, Any]:
    """Zone of a FEB SHOTCHART entry (x, y percentages and ``team``)."""
    x, y = feb_to_fiba(float(shot["x"]), float(shot["y"]), int(shot.get("team", 0)))
    return classify_fiba(x, y)


# --- scouting references and text ------------------------------------------------------

# Typical points per shot by zone and share of shots by family. Placeholders, calibrated on
# 8 games of the 2026-27 LF Challenge (~1,100 shots) and used only until the preparation
# package carries the real league data. Mid-range cells are tiny samples, hence rounded.
DEFAULT_ZONE_PPS: Dict[str, float] = {
    "restricted_area": 1.30, "key_area": 0.75, "short_mid_range": 0.45, "medium_mid_range": 0.50,
    "long_mid_range": 0.45, "left_corner_three": 0.90, "right_corner_three": 0.90,
    "left_wing_three": 0.85, "right_wing_three": 0.85, "center_three": 1.00,
}

DEFAULT_FAMILY_SHARE: Dict[str, float] = {
    "aro": 0.21, "zona": 0.30, "media distancia": 0.14, "esquina": 0.02, "ala": 0.29, "centro del arco": 0.04,
}


def family_totals(cells: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, int]]:
    """Add per-zone cells ({"a", "m", "pts"}) up into zone families."""
    out: Dict[str, Dict[str, int]] = {}
    for zone, cell in (cells or {}).items():
        if zone not in _FAMILY:
            continue
        total = out.setdefault(_FAMILY[zone], {"a": 0, "m": 0, "pts": 0})
        for key in total:
            total[key] += cell.get(key, 0)
    return out


def default_family_pps(family: str) -> float:
    values = [DEFAULT_ZONE_PPS[z] for z, f in _FAMILY.items() if f == family]
    return sum(values) / len(values)
