"""Jersey numbers read from the shot chart (issue #599), standard library only.

The play-by-play lines name a player by his ids, never by his jersey number; the SHOTCHART gives the number of each field goal (``player``), with its ``team`` (0/1), ``quarter``,
clock ``t`` and ``m`` (1 made, 0 missed). Joining every field goal of the play-by-play with its shot by (period, clock, team, made) says which number a player wears. It is what the
box score of a live match of 2ª and 3ª FEB does not say (its ``PLAYER`` entries are ``{id, name}``), so without it neither the number in the box score tab nor the shot zones of a
player could be known there. Checked on 60 matches of 2026/27: 1,174 pairs, all of them the number of the official box score, for 94 % of the players who play (the rest never shot).

A key is only trusted when it is unambiguous: as many lines as shots and a single player and number among them (two players scoring in the same second for the same team cannot be
told apart). A player's number is the one most voted; a tie says nothing.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .clock import parse_clock, period_and_remaining

Key = Tuple[int, int, int, int]       # period, seconds remaining, team index, made (1) or missed (0)


def _shot_key(shot: Any, teams: int) -> Optional[Tuple[Key, str]]:
    """The key and the jersey number of a shot of the chart, None if it is not usable."""
    try:
        team, period, number = int(shot["team"]), int(str(shot["quarter"])), str(shot["player"]).strip()
    except (KeyError, TypeError, ValueError):
        return None
    remaining = parse_clock(shot.get("t"))
    if remaining is None or not number or not 0 <= team < teams:
        return None
    return (period, remaining, team, 1 if str(shot.get("m")) == "1" else 0), number


def infer_numbers(log: Iterable[Sequence[Any]], shots: Iterable[Any], team_ids: Sequence[str]) -> Dict[str, str]:
    """Player id -> jersey number (as the shot chart writes it) for the field goals that can be told apart.

    ``log``: the chronological ``[elapsed, team_id, kind, value, player_id]`` of ``LiveGame`` (``fg2``/``fg3``: 1 made, 0 missed); ``shots``: the shots of the chart;
    ``team_ids``: HEADER order (the chart's ``team`` 0/1 are indexes into it)."""
    teams = {tid: i for i, tid in enumerate(team_ids)}
    lines: Dict[Key, List[Optional[str]]] = defaultdict(list)
    for entry in log:
        elapsed, team, kind, value, pid = entry[0], entry[1], entry[2], entry[3], entry[4]
        if kind not in ("fg2", "fg3") or team not in teams:
            continue
        period, remaining = period_and_remaining(int(elapsed))
        lines[(period, remaining, teams[team], 1 if value else 0)].append(pid)
    numbers: Dict[Key, List[str]] = defaultdict(list)
    for shot in shots:
        parsed = _shot_key(shot, len(team_ids)) if isinstance(shot, dict) else None
        if parsed:
            numbers[parsed[0]].append(parsed[1])
    votes: Dict[str, Counter] = defaultdict(Counter)
    for key, pids in lines.items():
        seen = numbers.get(key, [])
        if len(pids) != len(seen) or len(set(pids)) != 1 or len(set(seen)) != 1 or pids[0] is None:
            continue
        votes[pids[0]][seen[0]] += 1
    out: Dict[str, str] = {}
    for pid, counter in votes.items():
        ranked = counter.most_common(2)
        if len(ranked) == 1 or ranked[0][1] > ranked[1][1]:
            out[pid] = ranked[0][0]
    return dict(sorted(out.items()))
