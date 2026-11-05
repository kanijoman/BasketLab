"""What every team, or every player, of a competition shot in each zone: the reference of the rating of a zone (issue #760, ``zone_rating.rate_zones``).

One pass over the shots (``owned_shots``), O(entities x 10) memory. A shot of a player nobody can name counts for his team and for no player.
"""
from __future__ import annotations

from typing import Any, Dict, Literal

from src.shotcharts.feb_zones import ZONE_META
from src.shotcharts.owned_shots import iter_owned_shots
from src.utils.collection_utils import is_fbcyl

ZoneCounts = Dict[str, Dict[str, int]]


def zone_counts_by_owner(collection: Any, name: str, by: Literal["team", "player"]) -> Dict[str, ZoneCounts]:
    """``{team_id or player_id: {zone: {"fga": n, "fgm": n}}}`` over every shot of the competition ``name`` held in ``collection``."""
    tables: Dict[str, ZoneCounts] = {}
    for team_id, player_id, _x, _y, made, zone in iter_owned_shots(collection, is_fbcyl(name)):
        owner = team_id if by == "team" else player_id
        if not owner:
            continue
        counts = tables.setdefault(owner, {z: {"fga": 0, "fgm": 0} for z in ZONE_META}) if zone in ZONE_META else tables.get(owner)
        if counts is None:
            continue
        counts[zone]["fga"] += 1
        counts[zone]["fgm"] += int(made)
    return tables
