"""A finished game replayed "as live" for the rule evaluator.

The app polls FEB every ``poll_s`` seconds and a line is visible ``latency_s`` after FEB logged it (``LogTimeUtc``,
median 39 s in the first real recording). ``finished_game_polls`` rebuilds the documents the tablet would have
received: each poll shows the lines logged at least ``latency_s`` earlier, and a poll without news is not delivered.
Games stored without ``LogTimeUtc`` fall back to the game clock (a line is logged when it happened), which is
conservative. ``Poll.shown_elapsed`` is the game-second the staff was watching when the poll arrived (the last second
logged by then): an alert shown at that moment can only be followed by what happens after it.

Documents share line dictionaries between polls (no deep copies, the engine never modifies its input), so replaying a
whole season is cheap. ``recording_polls`` does the same for a real recording, which already contains its latency.
"""

from __future__ import annotations

import bisect
import math
from calendar import timegm
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Tuple

from src.live_core.clock import elapsed_seconds, parse_clock
from src.live_core.events import parse_line
from src.live_core.recorded_feed import RecordedFeed
from src.live_core.replay import LIVE_STATUS, roster_only_boxscore

LIVE_STATUS_TEXT = "EN DIRECTO (EVALUACION)"
LOG_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_TIME = "log_time"
GAME_CLOCK = "game_clock"


@dataclass(frozen=True)
class Poll:
    t: float                          # when the app polled (epoch seconds, or game-seconds in game_clock mode)
    shown_elapsed: Optional[int]      # game-second on screen at that moment; None: the snapshot's own clock
    doc: Dict[str, Any]


def parse_log_time(text: Any) -> Optional[float]:
    """``LogTimeUtc`` (``2026-10-10 16:38:24``) as epoch seconds; None when missing or unreadable."""
    try:
        return float(timegm(datetime.strptime(str(text), LOG_TIME_FORMAT).timetuple()))
    except (TypeError, ValueError):
        return None


def _parsed_lines(game: Dict[str, Any]) -> List[Tuple[Dict[str, Any], Any]]:
    """(line, event) of the lines that can be read, ordered by line number."""
    out = []
    for line in ((game.get("PLAYBYPLAY") or {}).get("LINES")) or []:
        event = parse_line(line)
        if event is not None:
            out.append((line, event))
    return sorted(out, key=lambda pair: pair[1].num)


def timing_mode(game: Dict[str, Any]) -> str:
    """``log_time`` when every line carries ``LogTimeUtc``; otherwise ``game_clock``."""
    pairs = _parsed_lines(game)
    return LOG_TIME if pairs and all(parse_log_time(l.get("LogTimeUtc")) is not None for l, _ in pairs) else GAME_CLOCK


def _running_max(values: List[float]) -> List[float]:
    out, top = [], float("-inf")
    for v in values:
        top = max(top, v)
        out.append(top)
    return out


def _clock_text(remaining: int) -> str:
    return f"{remaining // 60:02d}:{remaining % 60:02d}"


def _shot_index(game: Dict[str, Any]) -> List[Tuple[int, Dict[str, Any]]]:
    shots = ((game.get("SHOTCHART") or {}).get("SHOTS")) or []
    out = []
    for shot in shots:
        try:
            out.append((elapsed_seconds(int(shot["quarter"]), parse_clock(shot["t"])), shot))
        except (KeyError, TypeError, ValueError):
            continue
    return out


class _Timeline:
    """The lines of a game with the moment each was logged, when it becomes visible and what the clock said."""

    def __init__(self, game: Dict[str, Any], latency_s: float) -> None:
        pairs = _parsed_lines(game)
        self.lines = [l for l, _ in pairs]
        events = [e for _, e in pairs]
        clock_mode = timing_mode(game) == GAME_CLOCK
        raw = [float(e.elapsed) if clock_mode else parse_log_time(l.get("LogTimeUtc")) for l, e in pairs]
        self.logged = _running_max(raw)
        self.visible = [t + latency_s for t in self.logged]
        self.top_elapsed: List[int] = []   # per prefix: the latest event of the game clock (header + shot cut)
        self.top_event: List[Any] = []
        best = events[0] if events else None
        for e in events:
            if e.elapsed >= best.elapsed:
                best = e
            self.top_elapsed.append(best.elapsed)
            self.top_event.append(best)
        self._game, self._roster = game, roster_only_boxscore(game) if events else {}
        self._shots, self._shot_chart = _shot_index(game), game.get("SHOTCHART") or {}

    def shown_elapsed(self, t: float) -> int:
        """The game-second logged by wall time ``t``: what the staff was watching."""
        n = bisect.bisect_right(self.logged, t)
        return self.top_elapsed[n - 1] if n else 0

    def document(self, k: int) -> Dict[str, Any]:
        """The document with the first ``k`` lines, as FEB served it."""
        last, cut = self.top_event[k - 1], self.top_elapsed[k - 1]
        header = {**(self._game.get("HEADER") or {}), "status": LIVE_STATUS, "statusText": LIVE_STATUS_TEXT,
                  "quarter": str(last.period), "time": _clock_text(last.remaining)}
        return {
            "HEADER": header, "BOXSCORE": self._roster,
            "PLAYBYPLAY": {**(self._game.get("PLAYBYPLAY") or {}), "LINES": self.lines[:k]},
            "SHOTCHART": {"quarters": self._shot_chart.get("quarters"), "duration": self._shot_chart.get("duration"),
                          "TEAM": [], "SHOTS": [s for e, s in self._shots if e <= cut]},
        }


def finished_game_polls(game: Dict[str, Any], latency_s: float = 40.0, poll_s: float = 10.0) -> Iterator[Poll]:
    """The documents the app would have received, one per poll that brought something new."""
    timeline = _Timeline(game, latency_s)
    if not timeline.lines:
        return
    first, last, previous = timeline.visible[0], timeline.visible[-1], 0
    for i in range(math.ceil((last - first) / poll_s) + 1):
        t = first + i * poll_s
        k = bisect.bisect_right(timeline.visible, t)
        if k != previous:
            previous = k
            yield Poll(t=t, shown_elapsed=timeline.shown_elapsed(t), doc=timeline.document(k))


def recording_polls(feed: RecordedFeed, poll_s: float = 10.0) -> Iterator[Poll]:
    """What a real recording served, polled every ``poll_s`` seconds; the 404 windows deliver nothing."""
    steps = int(feed.duration // poll_s) + 1
    for i in range(steps + 1):
        t = i * poll_s
        if feed.in_any_gap(t):
            continue
        doc = feed.document_at(t)
        if doc is not None:
            yield Poll(t=t, shown_elapsed=None, doc=doc)
