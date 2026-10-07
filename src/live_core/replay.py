"""Replay support: cut a finished FEB game at a clock point so it looks like a live one.

Used by tests, model evaluation and the fake FEB server. The partial document carries a
roster-only box score (no stats), because the engine must not rely on final numbers.
"""

from __future__ import annotations

import copy
import time
from typing import Any, Callable, Dict, Optional

from .clock import elapsed_seconds
from .events import parse_line

LIVE_STATUS = "2"
LIVE_STATUS_TEXT = "EN DIRECTO (REPLAY)"
_ROSTER_FIELDS = ("id", "no", "name", "logo", "captain")
_TEAM_FIELDS = ("id", "name", "logo", "teamCode", "clubCode")


def _clock_text(remaining: int) -> str:
    return f"{remaining // 60:02d}:{remaining % 60:02d}"


def truncate_doc(doc: Dict[str, Any], period: int, remaining: int) -> Dict[str, Any]:
    """Return a deep copy of ``doc`` as it would look at ``period`` / ``remaining`` seconds left."""
    cut = elapsed_seconds(period, remaining)
    out = copy.deepcopy(doc)

    kept = []
    for line in out["PLAYBYPLAY"]["LINES"]:
        event = parse_line(line)
        if event is not None and event.elapsed <= cut:
            kept.append(line)
    out["PLAYBYPLAY"] = {**out["PLAYBYPLAY"], "LINES": kept}

    points: Dict[str, int] = {}
    for line in kept:
        event = parse_line(line)
        if event and event.points and event.team_id and not event.deleted:
            points[event.team_id] = points.get(event.team_id, 0) + event.points

    header = out["HEADER"]
    header.update(status=LIVE_STATUS, statusText=LIVE_STATUS_TEXT, quarter=str(period),
                  time=_clock_text(remaining))
    for team in header.get("TEAM", []):
        team["pts"] = str(points.get(str(team["id"]), 0))

    out["BOXSCORE"] = {
        "TEAM": [
            {**{k: team[k] for k in _TEAM_FIELDS if k in team},
             "PLAYER": [{k: p[k] for k in _ROSTER_FIELDS if k in p} for p in team.get("PLAYER", [])]}
            for team in doc["BOXSCORE"]["TEAM"]
        ]
    }
    out["SHOTCHART"] = []
    for key in ("SCOREBOARD", "TEAMSTATS", "TICKER", "OVERVIEW", "BANNER", "RANKING"):
        out.pop(key, None)
    return out


class ReplayClock:
    """Game time advancing at ``speed`` x real time from ``start_elapsed`` up to ``end_elapsed``."""

    def __init__(self, start_elapsed: int = 0, speed: float = 1.0, end_elapsed: Optional[int] = None,
                 time_fn: Callable[[], float] = time.monotonic) -> None:
        self._start, self._speed, self._end, self._time_fn = start_elapsed, speed, end_elapsed, time_fn
        self._t0 = time_fn()

    def elapsed(self) -> int:
        value = self._start + (self._time_fn() - self._t0) * self._speed
        return int(min(value, self._end) if self._end is not None else value)

    def finished(self) -> bool:
        return self._end is not None and self.elapsed() >= self._end
