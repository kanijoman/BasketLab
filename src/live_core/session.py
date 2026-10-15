"""LiveSession: one object tying package + engine + advice together for the app.

The Android app calls it from Pyodide (inside a Web Worker) through the ``*_json`` entry
points: JSON text in, JSON text out, so nothing but strings crosses the boundary. A session
can follow a real FEB feed (``update``) or replay a finished game at any game-clock second
(``replay``, used by the demo mode and by tests).
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .advice import AdviceEngine
from .clock import period_and_remaining, period_length, period_start
from .engine import LiveEngine
from .events import parse_line
from .package import PreparationPackage
from .replay import truncate_doc
from .version import engine_version
from .recorded_feed import RecordedFeed
from .vectors import to_jsonable, unwrap_extended_json


class LiveSession:
    def __init__(self, package_text: str, mode: Optional[str] = None) -> None:
        self.package = PreparationPackage.loads(package_text)
        self._engine = LiveEngine()
        self._advice = AdviceEngine.from_package(self.package, mode)
        self._replay_doc: Optional[Dict[str, Any]] = None
        self._feed: Optional[RecordedFeed] = None
        self.replay_info: Dict[str, Any] = {}

    def set_mode(self, mode: Optional[str]) -> None:
        """Change the alert mode (issue #130). The advice engine is rebuilt, so what it remembered (what it already said) starts again."""
        self._advice = AdviceEngine.from_package(self.package, mode)

    @property
    def meta(self) -> Dict[str, Any]:
        p = self.package
        return {
            "package_id": p.package_id, "schema_version": p.schema_version, "created_at": p.created_at,
            "collection": p.collection, "season": p.season, "team": p.team, "rival": p.rival,
            # who plays at home in the match the package was prepared for (None: the first document will say)
            "home_id": ((p.competition_meta or {}).get("match") or {}).get("home", {}).get("id"),
            "engine_version": engine_version(),   # for the About screen and the diagnostics (#226)
        }

    def update(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Process the latest FEB document; returns the snapshot, the NEW alerts and the analysis."""
        snapshot = self._engine.update(doc)
        return to_jsonable({
            "snapshot": snapshot,
            "alerts": self._advice.evaluate(snapshot),
            "analysis": self._advice.analyze(snapshot),
        })

    def load_replay(self, game_doc: Dict[str, Any]) -> Dict[str, Any]:
        self._replay_doc = game_doc
        last = max((e.elapsed for e in map(parse_line, game_doc["PLAYBYPLAY"]["LINES"]) if e), default=0)
        period, _ = period_and_remaining(last)
        self.replay_info = {
            "duration": period_start(period) + period_length(period),
            "status": (game_doc.get("HEADER") or {}).get("statusText", ""),
        }
        return self.replay_info

    def load_recording(self, recording: Any) -> Dict[str, Any]:
        """Prepare a packed real recording (see ``recorded_feed``); ``play`` then feeds the engine with it."""
        self._feed = RecordedFeed.loads(recording)
        return {"match": self._feed.match, "duration": self._feed.duration, "frames": len(self._feed.frames),
                "status": "GRABACION", "start_at": self._feed.first_event_at(), "events": self._feed.event_times()}

    def play(self, t: float) -> Dict[str, Any]:
        """The recording ``t`` seconds after its first poll, as the live mode will receive it.

        ``{"feed": "ok", "output": <update output>}``; ``"waiting"`` before the first poll and ``"gap"`` while FEB
        answered nothing (a real 404 in the middle of the match): then the engine is NOT updated, like a failed poll.
        """
        if self._feed is None:
            raise RuntimeError("No recording loaded (call load_recording first)")
        if self._feed.document_at(t) is None:
            return {"feed": "waiting", "output": None}
        if self._feed.in_any_gap(t):
            return {"feed": "gap", "output": None}
        return {"feed": "ok", "output": self.update(self._feed.document_at(t))}

    def replay(self, elapsed: int) -> Dict[str, Any]:
        """The loaded game as it was ``elapsed`` game-seconds after tip-off."""
        if self._replay_doc is None:
            raise RuntimeError("No replay game loaded (call load_replay first)")
        period, remaining = period_and_remaining(max(int(elapsed), 0))
        if period > 1 and remaining == period_length(period):
            # exactly at a period boundary FEB still shows the finished period ("00:00")
            period, remaining = period - 1, 0
        return self.update(truncate_doc(self._replay_doc, period, remaining))


# --- Pyodide entry points (JSON text in / JSON text out) --------------------------------

_SESSION: Optional[LiveSession] = None


def _session() -> LiveSession:
    if _SESSION is None:
        raise RuntimeError("Session not started (call start_json first)")
    return _SESSION


def _dump(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def start_json(package_text: str, mode: Optional[str] = None) -> str:
    global _SESSION
    _SESSION = LiveSession(package_text, mode)
    return _dump(_SESSION.meta)


def set_mode_json(mode: Optional[str]) -> str:
    _session().set_mode(mode)
    return "{}"


def load_replay_json(game_json: str) -> str:
    return _dump(_session().load_replay(unwrap_extended_json(json.loads(game_json))))


def replay_json(elapsed: int) -> str:
    return _dump(_session().replay(elapsed))


def update_json(doc_json: str) -> str:
    return _dump(_session().update(unwrap_extended_json(json.loads(doc_json))))


def load_recording_json(recording_json: str) -> str:
    return _dump(_session().load_recording(recording_json))


def play_recording_json(t: float) -> str:
    return _dump(_session().play(t))
