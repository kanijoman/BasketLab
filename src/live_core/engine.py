"""Incremental engine: feed it successive FEB documents, get the live snapshot.

Each call processes only the play-by-play lines not seen before. A full rebuild happens
when history changes under our feet (a previously applied line is deleted or its content is
corrected, a line arrives out of order, or a line vanishes from the middle of the document
with no mark), so the result equals a fresh one-shot computation of the document. FEB does
correct lines while a match is on (a 3-pointer turned into a 2-pointer, a substitution "Entra"
into "Sale"; seen in the first real recording).

Two things are not a fresh computation of the document, on purpose: a document that is OLDER
than what was applied (every line it lacks comes after the last one it has: a stale copy of
the feed, an empty answer) is ignored (#1120), and of two lines with the same number in one
document the last wins (#1121).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from .clock import parse_clock
from .events import Event, parse_line
from .jerseys import infer_numbers
from .shots import ShotTracker
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


def _numbers(doc: Dict[str, Any]) -> Dict[str, str]:
    """Player id -> jersey number as text («04» keeps its zero), from the box score of the document when it numbers its players (the FEB feed of a live match does not, the
    FBCYL adapter does; the package's roster says it otherwise, ``boxscore.build``)."""
    return {str(p["id"]): str(p["no"]).strip() for team in (doc.get("BOXSCORE") or {}).get("TEAM", []) for p in team.get("PLAYER", [])
            if p.get("id") and p.get("no") is not None and str(p["no"]).strip() != ""}


def _dorsals(doc: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """Team id -> jersey number -> player id, from the box score (the shot chart only has jersey numbers)."""
    return {str(team.get("id")): {str(p["no"]): str(p["id"]) for p in team.get("PLAYER", []) if p.get("id") and p.get("no") is not None}
            for team in (doc.get("BOXSCORE") or {}).get("TEAM", [])}


def _events(doc: Dict[str, Any]) -> List[Event]:
    """The lines of the document in order, one per number: when a number shows up twice the last one of the document wins (#1121), so the result is the same at every poll."""
    lines = ((doc.get("PLAYBYPLAY") or {}).get("LINES")) or []
    by_num: Dict[int, Event] = {}
    for line in lines:
        event = parse_line(line)
        if event is not None:
            by_num[event.num] = event
    return [by_num[num] for num in sorted(by_num)]


class LiveEngine:
    def __init__(self) -> None:
        self._reset()

    def _reset(self) -> None:
        self._game: Optional[LiveGame] = None
        self._shots: Optional[ShotTracker] = None
        self._team_ids: List[str] = []
        self._applied: Dict[int, int] = {}  # line number -> fingerprint of the content that was applied
        self._deleted: Set[int] = set()
        self._box_dorsals: Dict[str, Dict[str, str]] = {}  # the jersey numbers of the box score of the last document that was followed

    def _is_stale(self, events: List[Event]) -> bool:
        """A document that is older than what was applied (a stale copy of the feed, an empty answer): every line applied that it lacks comes AFTER its last line, and what it has is what
        was applied (a shorter document of another match is not stale: it rebuilds). It is ignored, like the FBCYL stream that goes backwards (#1120)."""
        vanished = self._applied.keys() - {e.num for e in events}
        if self._game is None or not vanished or min(vanished) < max((e.num for e in events), default=0):
            return False
        deleted_now = {e.num for e in events if e.deleted}
        return not (deleted_now - self._deleted) & self._applied.keys() and all(self._applied.get(e.num) == hash(e) for e in events if not e.deleted)

    def update(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        events = _events(doc)
        if self._is_stale(events):
            return self._output()
        deleted_now = {e.num for e in events if e.deleted}
        live = [e for e in events if not e.deleted]

        last_applied = self._game.last_num if self._game else 0
        history_changed = bool(
            (deleted_now - self._deleted) & self._applied.keys()
            or self._applied.keys() - {e.num for e in events}  # a line vanished from the middle with no mark: FEB took it back (#1120)
            or any(e.num < last_applied and e.num not in self._applied for e in live)
            or any(self._applied.get(e.num, hash(e)) != hash(e) for e in live)  # an applied line was corrected
        )
        if history_changed:
            self._reset()
        self._deleted = deleted_now

        if self._game is None:
            teams = _teams(doc)
            self._team_ids = [tid for tid, _ in teams]
            self._game = LiveGame(teams, _roster(doc), _numbers(doc))
            self._shots = ShotTracker([tid for tid, _ in teams], _dorsals(doc))
        for event in live:
            if event.num not in self._applied:
                self._game.apply(event)
                self._applied[event.num] = hash(event)
        self._box_dorsals = _dorsals(doc)
        self._sync_clock(doc)
        self._shots.update(doc.get("SHOTCHART"))
        return self._output()

    def _output(self) -> Dict[str, Any]:
        """The snapshot of the state now (the same for an update and for a stale document, which changes nothing)."""
        # the jersey numbers the box score does not say are read from the shot chart (jerseys.py); the box score wins where it speaks
        inferred = infer_numbers(self._game.log, self._shots.raw_shots(), self._team_ids)
        self._shots.set_dorsals(self._merge_dorsals(self._box_dorsals, inferred))
        snapshot = self._game.snapshot()
        for pid, number in inferred.items():
            if pid in snapshot["players"] and snapshot["players"][pid]["no"] is None:
                snapshot["players"][pid]["no"] = number
        return {**snapshot, "zones": self._shots.snapshot(), "zone_players": self._shots.player_snapshot()}

    def _merge_dorsals(self, from_box: Dict[str, Dict[str, str]], inferred: Dict[str, str]) -> Dict[str, Dict[str, str]]:
        """Team id -> jersey number -> player id: the box score's, completed with the inferred numbers it does not have (a number of the box score is never taken over)."""
        merged = {tid: dict(table) for tid, table in from_box.items()}
        for pid, number in inferred.items():
            player = self._game.players.get(pid) if self._game else None
            if player is not None and player.team_id is not None:
                table = merged.setdefault(str(player.team_id), {})
                if str(number) not in {str(int(n)) if n.isdigit() else n for n in table} and number not in table and pid not in table.values():
                    table[number] = pid
        return merged

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
