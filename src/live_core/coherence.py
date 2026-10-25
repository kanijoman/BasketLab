"""The alerts do not contradict each other (feedback 0.4.0, #568): «subir el ritmo» and a minute later «bajar el ritmo»; «mantener el quinteto» and «sacar a la jugadora».

Some alerts take a STANCE on a topic of the game: ``stance_of`` reads it from the alert (a table, not code in every rule). The engine remembers the last stance said on each topic
(``Coherence``); a new alert with the OPPOSITE stance within ``conflict_window_s`` waits (it is not recorded as said, so it comes back if it still holds when the window is over) unless it
is more severe than the one it contradicts, and then it goes ahead telling that it changes what was said. Standard library only.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable, Dict, Optional, Tuple

from .advice_types import SEVERITY_RANK, Advice
from .clock import period_and_remaining

# topic -> {direction: what it was, in the staff's words}
LABELS = {
    "pace": {"up": "subir el ritmo", "down": "bajar el ritmo"},
    "rotation": {"keep": "mantener el quinteto", "change": "cambiar jugadores"},
}
_OPPOSITE = {"up": "down", "down": "up", "keep": "change", "change": "keep"}

Stance = Tuple[str, str, str]          # (topic, direction, label)


def _pace_control(a: Advice) -> Optional[Tuple[str, str]]:
    return ("pace", a.evidence["direction"]) if a.evidence.get("direction") in ("up", "down") else None


def _win_flip(a: Advice) -> Optional[Tuple[str, str]]:
    return ("pace", a.evidence["lever_direction"]) if a.evidence.get("lever") == "pace" and a.evidence.get("lever_direction") in ("up", "down") else None


def _keeps_if_worked(a: Advice) -> Optional[Tuple[str, str]]:
    return ("rotation", "keep") if a.evidence.get("worked") is True else None


_STANCES: Dict[str, Callable[[Advice], Optional[Tuple[str, str]]]] = {
    "pace_control": _pace_control,
    "win_flip": _win_flip,
    "own_run": lambda a: ("rotation", "keep"),
    "timeout_followup": _keeps_if_worked,
    "fatigue_high": lambda a: ("rotation", "change"),
    "lineup_net": lambda a: ("rotation", "change"),
    "player_plus_minus": lambda a: ("rotation", "change"),
}


def stance_of(advice: Advice) -> Optional[Stance]:
    """``(topic, direction, label)`` the alert takes, or None when it takes none (most of them)."""
    read = _STANCES.get(advice.id)
    found = read(advice) if read else None
    return (found[0], found[1], LABELS[found[0]][found[1]]) if found else None


def _when(at: int) -> str:
    period, remaining = period_and_remaining(at)
    return f"{'prórroga' if period > 4 else f'{period}.º cuarto'} {remaining // 60}:{remaining % 60:02d}"


class Coherence:
    """The memory of the engine: the last stance said on each topic."""

    def __init__(self) -> None:
        self._said: Dict[str, Dict[str, Any]] = {}

    def check(self, advice: Advice, now: int, window_s: int) -> Optional[Advice]:
        """The alert to say (with a note when it changes what was said), or None when it must wait. Nothing is recorded: ``said`` does that once it is emitted."""
        stance = stance_of(advice)
        before = self._said.get(stance[0]) if stance else None
        if not stance or not before or before["direction"] != _OPPOSITE[stance[1]] or now - before["at"] >= window_s:
            return advice
        if SEVERITY_RANK[advice.severity] >= SEVERITY_RANK[before["severity"]]:
            return None
        note = f" Cambia lo dicho antes ({_when(before['at'])}): entonces se aconsejó {before['label']}."
        return dataclasses.replace(advice, message=advice.message + note)

    def said(self, advice: Advice, now: int) -> None:
        stance = stance_of(advice)
        if stance:
            self._said[stance[0]] = {"direction": stance[1], "label": stance[2], "at": now, "severity": advice.severity}
