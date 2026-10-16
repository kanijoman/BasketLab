"""Points of each team by the origin of its possessions, bench and paint (#352).

``pts_by_origin`` partitions the points of a team by the way its possession started (``Possession.origin``); the free
throws of technical fouls, which are not a possession, go under ``technical`` (their points still count for the bench). Views on top of it: points and possessions
after a turnover (a steal included) or a steal, second chance (points after an offensive rebound of the same possession),
points of the bench (players who did not start: ``inn`` of the box score) and points in the paint (made shots of the
``SHOTCHART`` in the zones "aro" and "zona"). The official fast-break points are not derived: their definition cannot be
reproduced from the play-by-play (evaluated against the official PDF).
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Set

from src.live_core.zones import classify_shot

_AFTER_TURNOVER = ("turnover", "steal")
_PAINT_ZONES = ("restricted_area", "key_area")
_MADE_SHOT_POINTS = 2


def starters(box_team: Dict[str, Any]) -> Set[str]:
    """Ids of the players that started (``inn`` = 1 in the box score)."""
    return {str(p.get("id")) for p in box_team.get("PLAYER") or [] if str(p.get("inn")) == "1"}


def paint_points(shots: Iterable[Dict[str, Any]], team_index: int) -> int:
    """Points of the made two-point shots of a team that fell in the rim or key zones."""
    total = 0
    for shot in shots:
        if int(shot.get("team", -1)) != team_index or str(shot.get("m")) != "1":
            continue
        if classify_shot(shot).get("zone") in _PAINT_ZONES:
            total += _MADE_SHOT_POINTS
    return total


def team_points_by_origin(possessions: List[Any], team_id: str, starting: Set[str], technical_by_player: Dict[str, int],
                          paint: Optional[int]) -> Dict[str, Any]:
    """The figures of one team from its possessions (``counted`` or not: all of them carry their points)."""
    mine = [p for p in possessions if p.team_id == team_id]
    by_origin: Counter = Counter()
    for p in mine:
        if p.points:
            by_origin[p.origin] += p.points
    technical_points = sum(technical_by_player.values())
    if technical_points:
        by_origin["technical"] += technical_points
    after_tov = [p for p in mine if p.origin in _AFTER_TURNOVER and p.counted]
    after_steal = [p for p in after_tov if p.origin == "steal"]
    second = [p for p in mine if p.orebs and p.counted]
    bench = sum(pts for p in mine for player, pts in p.points_by_player.items() if player not in starting)
    bench += sum(pts for player, pts in technical_by_player.items() if player not in starting)
    return {
        "pts_by_origin": dict(by_origin),
        "pts_off_tov": sum(p.points for p in after_tov), "poss_off_tov": len(after_tov),
        "pts_off_steal": sum(p.points for p in after_steal), "poss_off_steal": len(after_steal),
        "pts_second_chance": sum(p.second_chance_points for p in mine), "poss_second_chance": len(second),
        "pts_bench": bench, "pts_paint": paint,
    }
