"""Situations of a game per team (#354): after-timeout possessions, first possession of each period, first and last two minutes.

``ato_own`` / ``ato_rival``: possessions that follow a timeout the team called / one the rival called (count and points; every
timeout counts, the last minute of a period included). ``first_poss``: periods whose first possession was the team's (count and
points). ``edges``: points, possessions (counted where they started) and turnovers of both teams in the first (``start``) and last
(``end``) ``EDGE_WINDOW_S`` seconds of every period; the rest of the period is the period figures minus these two windows.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from src.live_core.clock import period_length, period_start

EDGE_WINDOW_S = 120
_COUNTERS = ("pts", "poss", "tov")


def _window(ev_elapsed: int, period: int) -> str:
    """"start" / "end" for an instant in the first / last EDGE_WINDOW_S of its period, else ""."""
    into = ev_elapsed - period_start(period)
    if into < EDGE_WINDOW_S:
        return "start"
    return "end" if into >= period_length(period) - EDGE_WINDOW_S else ""


def _empty_edges() -> Dict[str, Dict[str, int]]:
    return {w: {**{k: 0 for k in _COUNTERS}, **{f"opp_{k}": 0 for k in _COUNTERS}} for w in ("start", "end")}


def _add_edge(edges: Dict[str, Dict[Any, Any]], team: str, rival: str, window: str, key: str, amount: int) -> None:
    if window:
        edges[team][window][key] += amount
        edges[rival][window][f"opp_{key}"] += amount


def _first_possessions(possessions: Iterable[Any]) -> Dict[int, Any]:
    first: Dict[int, Any] = {}
    for p in possessions:
        if p.period not in first or (p.start_elapsed, p.start_num) < (first[p.period].start_elapsed, first[p.period].start_num):
            first[p.period] = p
    return first


def situation_figures(events: List[Any], possessions: List[Any], team_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Per team id: ``ato_own``, ``ato_rival``, ``first_poss`` and ``edges``."""
    rival = {team_ids[0]: team_ids[1], team_ids[1]: team_ids[0]}
    out = {t: {"ato_own": {"n": 0, "pts": 0}, "ato_rival": {"n": 0, "pts": 0}, "first_poss": {"n": 0, "pts": 0},
               "edges": _empty_edges()} for t in team_ids}
    edges = {t: out[t]["edges"] for t in team_ids}
    for p in possessions:
        if p.team_id not in out:
            continue
        for kind, called in (("ato_own", True), ("ato_rival", False)):
            if any((team == p.team_id) == called for team, _ in p.timeouts):
                out[p.team_id][kind]["n"] += 1
                out[p.team_id][kind]["pts"] += p.points
        if p.counted:
            _add_edge(edges, p.team_id, rival[p.team_id], _window(p.start_elapsed, p.period), "poss", 1)
    for p in _first_possessions(possessions).values():
        if p.team_id in out:
            out[p.team_id]["first_poss"]["n"] += 1
            out[p.team_id]["first_poss"]["pts"] += p.points
    for ev in events:
        if ev.team_id not in out or ev.deleted:
            continue
        window = _window(ev.elapsed, ev.period)
        if ev.kind == "turnover":
            _add_edge(edges, ev.team_id, rival[ev.team_id], window, "tov", 1)
        elif ev.points:
            _add_edge(edges, ev.team_id, rival[ev.team_id], window, "pts", ev.points)
    return out
