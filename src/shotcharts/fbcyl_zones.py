"""FBCYL shot zones: same 10 zones as FEB, from the per-player shooting coordinates.

FBCYL stores ``xnormalize``/``ynormalize`` (0-100 % of the court) already folded into a
single half court for every team, so - unlike FEB, where each team attacks its own
basket - the team index must NOT mirror the court: every shot is converted as ``team=0``.
"""
from typing import Any, Dict, Iterator, List, Optional

from src.shotcharts.feb_zones import ZONE_META, classify_zone, feb_to_fiba

_SHOT_KEYS = (
    ("shootingOfTwoSuccessfulPoint", True),
    ("shootingOfTwoFailedPoint", False),
    ("shootingOfThreeSuccessfulPoint", True),
    ("shootingOfThreeFailedPoint", False),
)


def _team_matches(team: Dict[str, Any], team_id: Optional[str]) -> bool:
    return team_id is None or str(team.get("teamIdExtern", "")) == str(team_id)


def _tid_query(team_id: Optional[str]) -> Dict[str, Any]:
    if team_id is None:
        return {}
    tid = int(team_id) if str(team_id).isdigit() else team_id
    return {"stats.teams.teamIdExtern": tid}


def iter_shots_fbcyl(coll, team_id: Optional[str], player_filter: Optional[str]):
    """Yield ``(x_fiba, y_fiba, made)`` for every shot with coordinates."""
    cursor = coll.find(_tid_query(team_id), {"stats.teams": 1, "_id": 0})
    for doc in cursor:
        for team in (doc.get("stats") or {}).get("teams", []):
            if not _team_matches(team, team_id):
                continue
            for player in team.get("players", []):
                if player_filter and str(player.get("uuid", "")) != str(player_filter):
                    continue
                data = player.get("data") or {}
                for key, made in _SHOT_KEYS:
                    for pt in data.get(key) or []:
                        if isinstance(pt, dict) and "xnormalize" in pt and "ynormalize" in pt:
                            x, y = feb_to_fiba(float(pt["xnormalize"]), float(pt["ynormalize"]), 0)
                            yield x, y, made


def iter_shot_dicts_fbcyl(coll, team_id: Optional[str], player_filter: Optional[str]) -> Iterator[Dict[str, Any]]:
    """Lazily yield shots in the shape of ``feb_zones.iter_shots_feb`` (zone, made, FIBA x/y)."""
    for x, y, made in iter_shots_fbcyl(coll, team_id, player_filter):
        yield {"zone": classify_zone(x, y), "made": made, "x": x, "y": y}


def extract_shots_fbcyl(coll, team_id: Optional[str], player_filter: Optional[str]) -> List[Dict[str, Any]]:
    """Shots as a list (use ``iter_shot_dicts_fbcyl`` for league-wide scans)."""
    return list(iter_shot_dicts_fbcyl(coll, team_id, player_filter))


def stream_zone_counts_fbcyl(coll, team_id: Optional[str], player_filter: Optional[str]) -> Dict[str, Dict[str, int]]:
    """Per-zone attempts/makes without keeping the shots (same shape as the FEB counter)."""
    accum = {z: {"fga": 0, "fgm": 0} for z in ZONE_META}
    for x, y, made in iter_shots_fbcyl(coll, team_id, player_filter):
        zone = classify_zone(x, y)
        accum[zone]["fga"] += 1
        accum[zone]["fgm"] += int(made)
    return accum
