"""The shot answers of a collection (issues #760, #685; moved out of the shots router when the API was retired, epic #1199): shooting percentages by court zone, optionally rated against how the
league shoots there, and the individual shot coordinates. FEB (``SHOTCHART``) and FBCYL (per-player coordinates) answer the same shapes. The web computes the same on the device
(``localdata/shots.ts``); these functions are the Python reference of its parity vectors (``tests/local_vectors/generate.py``).
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from src.shotcharts.fbcyl_zones import extract_shots_fbcyl, stream_zone_counts_fbcyl
from src.shotcharts.feb_zones import aggregate_zones, extract_shots_feb, stream_zone_counts_feb
from src.shotcharts.zone_distribution import zone_counts_by_owner
from src.shotcharts.zone_rating import rate_zones
from utils.collection_utils import is_fbcyl as _is_fbcyl


def _readers(collection: str):
    """(zone counter, shot extractor) for the collection's format (FEB or FBCYL)."""
    if _is_fbcyl(collection):
        return stream_zone_counts_fbcyl, extract_shots_fbcyl
    return stream_zone_counts_feb, extract_shots_feb


def shot_zones(db: Any, collection: str, team_id: Optional[str] = None, player: Optional[str] = None,
               compare: Optional[Literal["league"]] = None) -> List[Dict[str, Any]]:
    """The 10 zones with ``zone``, ``zone_label``, ``points``, ``fga``, ``fgm`` and ``fg_pct``; with ``compare="league"`` each zone also has ``rating``, ``league_pct``, ``delta_pp``,
    ``percentile`` and ``low_sample`` (the quartiles of the teams of the competition, or of its players when a player is asked for, weighted by their attempts). ``[]`` if anything fails."""
    try:
        stream, _ = _readers(collection)
        coll = db.connection.get_collection(collection)
        zones = aggregate_zones(stream(coll, team_id=team_id, player_filter=player))
        if compare != "league":
            return zones
        owners = zone_counts_by_owner(coll, collection, "player" if player else "team")
        return rate_zones(zones, list(owners.values()))
    except Exception:
        return []


def shot_raw(db: Any, collection: str, team_id: Optional[str] = None, player: Optional[str] = None, limit: int = 5000) -> List[Dict[str, Any]]:
    """Individual shots in FIBA metres: ``x`` (0-15), ``y`` (0-14), ``made`` and ``zone``; at most ``limit``. ``[]`` if anything fails."""
    try:
        _, extract = _readers(collection)
        coll = db.connection.get_collection(collection)
        return [{"x": s["x"], "y": s["y"], "made": s["made"], "zone": s["zone"]} for s in extract(coll, team_id=team_id, player_filter=player)[:limit]]
    except Exception:
        return []
