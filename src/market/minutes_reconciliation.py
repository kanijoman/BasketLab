"""The minutes of the official box counted from the play-by-play (#963): the starting five of the box (``sta``) and the substitution lines give the seconds each player is on court.

A minute that does not agree within ``MINUTES_TOLERANCE`` is reported but never discards a game (it is an information statistic, not a core one). A game whose lineup cannot be known (a team without five starters in
the box) has no minute check at all, and the report says so. The clock of the lines is the time REMAINING in the period (the one FIBA writes); the regulation periods last what the scheme of the game says (``HEADER.PERIODS``, #1131: NCAA men play two halves of 20; else four quarters of 10) and every overtime ``OVERTIME_SECONDS``.
Pure functions, no I/O, the same answer whatever the order of the lines.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple

from src.live_core.clock import FEB_SCHEME, Scheme
from src.pbp.period_scheme import scheme_of

OVERTIME_SECONDS = 300
MINUTES_TOLERANCE = 2                    # seconds: the box rounds (the real FIBA games agree within one)
_STARTERS = 5


@dataclass(frozen=True)
class MinuteCheck:
    """One player-game: the seconds the lines give and the ones of the official box."""
    team_id: str
    player_id: str
    pbp: int
    official: int

    @property
    def ok(self) -> bool:
        return abs(self.pbp - self.official) <= MINUTES_TOLERANCE


def _seconds(value: Any) -> int:
    text = str(value or "0")
    if ":" in text:
        minutes, _, seconds = text.partition(":")
        return int(minutes or 0) * 60 + int(seconds or 0)
    try:
        return int(float(text.replace(",", ".")))
    except ValueError:
        return 0


def _period_length(period: int, scheme: Scheme = FEB_SCHEME) -> int:
    return scheme.minutes * 60 if period <= scheme.periods else OVERTIME_SECONDS


def _moves(lines: List[Dict[str, Any]], team_id: str) -> Dict[int, List[Tuple[int, int, str, bool]]]:
    """The substitutions of a team by period: ``(clock remaining, order, player, comes in)``, in the order they happened (the clock runs down; the number of the line breaks the ties)."""
    out: Dict[int, List[Tuple[int, int, str, bool]]] = {}
    for line in lines:
        text = str(line.get("text") or "").upper()
        if line.get("action") != "subst" or line.get("deleted") or str(line.get("idTeam")) != team_id or not line.get("idPlayer"):
            continue
        if not (text.endswith("ENTRA A PISTA") or text.endswith("SALE DE PISTA")):
            continue
        out.setdefault(int(line.get("quarter") or 0), []).append((_seconds(line.get("time")), int(line.get("num") or 0), str(line["idPlayer"]), text.endswith("ENTRA A PISTA")))
    for moves in out.values():
        moves.sort(key=lambda m: (-m[0], m[1]))
    return out


def _team_seconds(lines: List[Dict[str, Any]], team: Dict[str, Any], periods: List[int], scheme: Scheme = FEB_SCHEME) -> Dict[str, int]:
    on: Set[str] = {str(p["id"]) for p in team["PLAYER"] if p.get("sta")}
    total: Dict[str, int] = {}
    moves = _moves(lines, str(team["id"]))
    for period in periods:
        remaining = _period_length(period, scheme)
        for clock, _num, player, comes_in in moves.get(period, []):
            clock = min(clock, remaining)
            for person in on:
                total[person] = total.get(person, 0) + remaining - clock
            remaining = clock
            (on.add if comes_in else on.discard)(player)
        for person in on:
            total[person] = total.get(person, 0) + remaining
    return total


def minutes_checks(doc: Dict[str, Any]) -> Tuple[MinuteCheck, ...]:
    """One check per player who is on court by the lines or has minutes in the box. Empty when the game has no lineup to start from (a team without five starters) or no play-by-play."""
    teams = (doc.get("BOXSCORE") or {}).get("TEAM") or []
    lines = ((doc.get("PLAYBYPLAY") or {}).get("LINES")) or []
    if len(teams) < 2 or not lines:
        return ()
    if any(sum(1 for p in team["PLAYER"] if p.get("sta")) != _STARTERS for team in teams[:2]):
        return ()
    periods = sorted({int(l.get("quarter") or 0) for l in lines if int(l.get("quarter") or 0) > 0})
    checks: List[MinuteCheck] = []
    for team in teams[:2]:
        worked = _team_seconds(lines, team, periods, scheme_of(doc))
        for player in team["PLAYER"]:
            pid = str(player["id"])
            official = _seconds(player.get("min"))
            if worked.get(pid, 0) or official:
                checks.append(MinuteCheck(str(team["id"]), pid, worked.get(pid, 0), official))
    return tuple(checks)
