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
from .engine import LiveEngine, _teams
from .events import parse_line
from .package import PreparationPackage
from .postmatch import build_report
from .replay import truncate_doc
from .version import engine_version
from .config import RuleConfig
from .recorded_feed import RecordedFeed
from .recording_builder import RecordingBuilder
from .vectors import to_jsonable, unwrap_extended_json


class LiveSession:
    def __init__(self, package_text: str, mode: Optional[str] = None) -> None:
        self.package = PreparationPackage.loads(package_text)
        self._engine = LiveEngine()
        self._advice = AdviceEngine.from_package(self.package, mode)
        self._replay_doc: Optional[Dict[str, Any]] = None
        self._feed: Optional[RecordedFeed] = None
        self._recording: Optional[RecordingBuilder] = None
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

    def package_match(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Whether the teams of the package are the teams of the match (issue #417). Ids the package does not carry cannot be compared."""
        expected = [str(t.get("id")) for t in (self.package.team, self.package.rival)]
        found = [tid for tid, _ in _teams(doc)]
        comparable = [e for e in expected if e != "None"]
        return {"ok": all(e in found for e in comparable), "expected": expected, "found": found}

    def begin_recording(self, match: str, started: str) -> None:
        """Keep a recording of the feed that follows (issue #416): ``update`` records the documents it is given a time for."""
        self._recording = RecordingBuilder(match, started)

    def record_gap(self, endpoint: str, at: float) -> None:
        if self._recording is not None:
            self._recording.gap(endpoint, at)

    def recording(self) -> Optional[str]:
        """The recording so far as JSON text (``recorded_feed`` format), or None when there is none."""
        packed = self._recording.pack() if self._recording is not None else None
        return None if packed is None else json.dumps(packed, ensure_ascii=False, separators=(",", ":"))

    def update(self, doc: Dict[str, Any], at: Optional[float] = None) -> Dict[str, Any]:
        """Process the latest FEB document (``at`` = seconds since the first poll of the feed); returns the snapshot, the NEW alerts and the analysis.

        Under a package prepared for another match (#417) the advice is withheld: ``package_match`` says so and the rest is empty."""
        snapshot = self._engine.update(doc)
        if self._recording is not None and at is not None:
            self._recording.add(at, doc)
        match = self.package_match(doc)
        return to_jsonable({
            "snapshot": snapshot,
            "alerts": self._advice.evaluate(snapshot) if match["ok"] else [],
            "analysis": self._advice.analyze(snapshot) if match["ok"] else {},
            "package_match": match,
        })

    def report(self, game_doc: Dict[str, Any], alerts: Optional[Any] = None) -> Dict[str, Any]:
        """The post-match report (issue #409) of a finished game, from the point of view of the package's team."""
        return to_jsonable(build_report(game_doc, str(self.package.team["id"]), alerts, RuleConfig.from_dict(self.package.rule_config)))

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


def update_json(doc_json: str, at: Optional[float] = None) -> str:
    return _dump(_session().update(unwrap_extended_json(json.loads(doc_json)), at))


def begin_recording_json(match: str, started: str) -> str:
    _session().begin_recording(match, started)
    return "{}"


def record_gap_json(endpoint: str, at: float) -> str:
    _session().record_gap(endpoint, at)
    return "{}"


def recording_json() -> str:
    """The recording of the live feed so far (``recorded_feed`` format) or ``null``."""
    text = _session().recording()
    return "null" if text is None else text


def load_recording_json(recording_json: str) -> str:
    return _dump(_session().load_recording(recording_json))


def play_recording_json(t: float) -> str:
    return _dump(_session().play(t))


def _final_document(data: Any) -> Dict[str, Any]:
    """The game of a report: a final FEB document as it is, or the last document of a packed recording (a demo, issue #477)."""
    if isinstance(data, dict) and "frames" in data and "base" in data:
        feed = RecordedFeed(data)
        return feed.document_at(feed.duration)
    return data


def report_json(game_json: str, alerts_json: Optional[str] = None, own_team_id: Optional[str] = None, rule_config_json: Optional[str] = None) -> str:
    """The post-match report. With ``own_team_id`` it needs no session (a finished match kept on the device is reported while another
    session may be running); without it the session's team is the own one. ``game_json`` is a final document or a packed recording; ``rule_config_json``
    (the package's) gives the gender of the competition to the text (#475)."""
    game, alerts = _final_document(unwrap_extended_json(json.loads(game_json))), (json.loads(alerts_json) if alerts_json else None)
    config = RuleConfig.from_dict(json.loads(rule_config_json)) if rule_config_json else None
    if own_team_id is not None:
        return _dump(to_jsonable(build_report(game, str(own_team_id), alerts, config)))
    return _dump(_session().report(game, alerts))
