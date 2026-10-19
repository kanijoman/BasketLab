"""Per-period figures of each team in a FEB game (#353).

For every period of a team: points, possessions (counted by the period where they started), field goals, threes, free
throws, turnovers, rebounds (offensive when the team that missed rebounds, as everywhere) and fouls, plus the same figures of
the rival (``opp_``). The minutes of the period (10, or 5 in an overtime) let the season service turn possessions into pace.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List

from .game_possessions import rebound_sides

COUNTERS = ("pts", "poss", "fga", "fgm", "fg3m", "fta", "ftm", "tov", "orb", "drb", "fouls")
_SHOTS = ("fg2", "fg3")


def _period_minutes(period: int) -> int:
    return 10 if period <= 4 else 5


def _count_events(events: Iterable[Any], counts: Dict[tuple, Counter]) -> None:
    for ev in events:
        if ev.team_id is None or ev.deleted:
            continue
        c = counts[(ev.team_id, ev.period)]
        if ev.kind in _SHOTS:
            c["fga"] += 1
            if ev.made:
                c["fgm"] += 1
                c["pts"] += ev.points
                c["fg3m"] += ev.kind == "fg3"
        elif ev.kind == "ft":
            c["fta"] += 1
            if ev.made:
                c["ftm"] += 1
                c["pts"] += ev.points
        elif ev.kind == "turnover":
            c["tov"] += 1
        elif ev.kind == "foul":
            c["fouls"] += 1


def team_periods(events: List[Any], possessions: List[Any], team_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Per team id, the list of its periods with its figures and the rival's (``opp_``), ordered by period."""
    counts: Dict[tuple, Counter] = {}
    for tid in team_ids:
        for period in {e.period for e in events}:
            counts[(tid, period)] = Counter()
    _count_events((e for e in events if e.team_id in team_ids), counts)
    for ev, side in rebound_sides([e for e in events if e.team_id in team_ids]):
        counts[(ev.team_id, ev.period)][side] += 1
    for p in possessions:
        if p.counted and (p.team_id, p.period) in counts:
            counts[(p.team_id, p.period)]["poss"] += 1
    rival = {team_ids[0]: team_ids[1], team_ids[1]: team_ids[0]}
    out: Dict[str, List[Dict[str, Any]]] = {}
    for tid in team_ids:
        rows = []
        for period in sorted({p for (t, p) in counts if t == tid}):
            mine, other = counts[(tid, period)], counts[(rival[tid], period)]
            row: Dict[str, Any] = {"p": period, "minutes": _period_minutes(period)}
            row.update({k: mine[k] for k in COUNTERS})
            row.update({f"opp_{k}": other[k] for k in COUNTERS})
            rows.append(row)
        out[tid] = rows
    return out
