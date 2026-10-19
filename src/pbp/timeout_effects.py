"""What happens around the timeouts of a game, per team (#355): the possessions before and after each one.

Both teams get an entry per timeout (``caller``: ``own`` for the team that called it, ``rival`` for the other) with the points,
possessions and turnovers of both teams in the ``window`` counted possessions of each team before it and from it on, inside the
same period. Left out: timeouts in the last ``TM_LAST_MINUTE_S`` of a period (preparation of a play, not a change of momentum; they
still count as after-timeout possessions, ``situation_stats``) and those without a complete window on either side. The window and
the minute are provisional business thresholds.
"""
from __future__ import annotations

from typing import Any, Dict, List

from src.live_core.clock import period_length, period_start

TM_WINDOW_POSSESSIONS = 5     # counted possessions of each team on each side of the timeout
TM_LAST_MINUTE_S = 60         # timeouts with this much or less left in the period are not analysed


def _figures(window: List[Any], team: str, rival: str) -> Dict[str, int]:
    mine = [p for p in window if p.team_id == team]
    theirs = [p for p in window if p.team_id == rival]
    return {
        "pts": sum(p.points for p in mine), "opp_pts": sum(p.points for p in theirs),
        "poss": len(mine), "opp_poss": len(theirs),
        "tov": sum(p.outcome == "turnover" for p in mine), "opp_tov": sum(p.outcome == "turnover" for p in theirs),
    }


def _side(possessions: List[Any], team_ids: List[str], window: int, before: bool) -> List[Any]:
    """The ``window`` possessions of each team nearest to the timeout on one side (empty if either team lacks them)."""
    picked: List[Any] = []
    for tid in team_ids:
        mine = [p for p in possessions if p.team_id == tid]
        mine = mine[-window:] if before else mine[:window]
        if len(mine) < window:
            return []
        picked += mine
    return picked


def timeout_effects(possessions: List[Any], team_ids: List[str], window: int = TM_WINDOW_POSSESSIONS) -> Dict[str, List[Dict[str, Any]]]:
    """Per team id, the entries of the timeouts that can be analysed, in the order they were called."""
    rival = {team_ids[0]: team_ids[1], team_ids[1]: team_ids[0]}
    out: Dict[str, List[Dict[str, Any]]] = {t: [] for t in team_ids}
    counted = [p for p in possessions if p.counted]
    for index, first in enumerate(possessions):
        for caller, elapsed in first.timeouts:
            into = elapsed - period_start(first.period)
            if caller not in rival or period_length(first.period) - into <= TM_LAST_MINUTE_S:
                continue
            same = [p for p in counted if p.period == first.period]
            pre = _side([p for p in same if (p.start_elapsed, p.start_num) < (first.start_elapsed, first.start_num)], team_ids, window, True)
            post = _side([p for p in same if (p.start_elapsed, p.start_num) >= (first.start_elapsed, first.start_num)], team_ids, window, False)
            if not pre or not post:
                continue
            for tid in team_ids:
                out[tid].append({"p": first.period, "t": elapsed, "caller": "own" if tid == caller else "rival",
                                 "pre": _figures(pre, tid, rival[tid]), "post": _figures(post, tid, rival[tid])})
    return out
