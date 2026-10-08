"""Incremental engine: feed it successive FEB documents, get the live snapshot.

Each call processes only the play-by-play lines not seen before. A full rebuild happens
when history changes under our feet (a previously applied line is deleted/corrected, or
a line arrives out of order), so the result always equals a fresh one-shot computation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from .clock import parse_clock
from .events import Event, parse_line
from .state import LiveGame


def _teams(doc: Dict[str, Any]) -> List[Tuple[str, str]]:
    return [(str(t["id"]), (t.get("name") or str(t["id"])).strip())
            for t in (doc.get("HEADER") or {}).get("TEAM", [])]


def _roster(doc: Dict[str, Any]) -> Dict[str, Tuple[str, str]]:
    roster: Dict[str, Tuple[str, str]] = {}
    for team in (doc.get("BOXSCORE") or {}).get("TEAM", []):
        for player in team.get("PLAYER", []):
            if player.get("id"):
                roster[str(player["id"])] = ((player.get("name") or str(player["id"])).strip(), str(team.get("id")))
    return roster


def _events(doc: Dict[str, Any]) -> List[Event]:
    lines = ((doc.get("PLAYBYPLAY") or {}).get("LINES")) or []
    parsed = [e for e in (parse_line(line) for line in lines) if e is not None]
    return sorted(parsed, key=lambda e: e.num)


class LiveEngine:
    def __init__(self) -> None:
        self._reset()

    def _reset(self) -> None:
        self._game: Optional[LiveGame] = None
        self._applied: Set[int] = set()
        self._deleted: Set[int] = set()

    def update(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        events = _events(doc)
        deleted_now = {e.num for e in events if e.deleted}
        live = [e for e in events if not e.deleted]

        last_applied = self._game.last_num if self._game else 0
        history_changed = bool(
            (deleted_now - self._deleted) & self._applied
            or any(e.num < last_applied and e.num not in self._applied for e in live)
        )
        if history_changed:
            self._reset()
        self._deleted = deleted_now

        if self._game is None:
            self._game = LiveGame(_teams(doc), _roster(doc))
        for event in live:
            if event.num not in self._applied:
                self._game.apply(event)
                self._applied.add(event.num)
        self._sync_clock(doc)
        return self._game.snapshot()

    def _sync_clock(self, doc: Dict[str, Any]) -> None:
        """The header is fresher than the last event; "FINAL" and the like are ignored."""
        header = doc.get("HEADER") or {}
        remaining = parse_clock(header.get("time"))
        try:
            period = int(str(header.get("quarter")))
        except (TypeError, ValueError):
            return
        if remaining is not None and self._game is not None:
            self._game.set_clock(period, remaining)
