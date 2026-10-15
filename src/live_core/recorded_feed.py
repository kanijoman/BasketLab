"""A recorded FEB feed, replayed with its real timeline (issue #174).

``src/live_prep/recording_pack.py`` packs what the recorder saved into one small file. The play-by-play of a
match is append-only (newest line first), so every line is stored once with the frame it first appeared in
(``f``), the frame it was corrected in (``fix``) and the one it disappeared in (``r``); shots are stored the
same way. ``RecordedFeed.document_at(t)`` rebuilds the document FEB was serving ``t`` seconds after the first
poll, and ``None`` while an endpoint answered 404 (the real feed did so for a minute in the middle of a match).
Standard library only: it can run on the tablet (Pyodide) as well as in the fake FEB server.

Pack layout (``v`` = 1)::

    {"v": 1, "match": "2524470", "started": "<iso utc of the first poll>",
     "base":   {HEADER, BOXSCORE (roster only), PLAYBYPLAY (no LINES), SHOTCHART (no SHOTS)},
     "lines":  [{"f": frame, "l": line, "fix": [[frame, line], ...], "r": frame}],   # feed order
     "shots":  [{"f": frame, "s": shot, "r": frame}],
     "frames": [{"t": seconds, "h": {status, statusText, quarter, time, pts: {team: points}}}],
     "gaps":   {"boxscore": [[from, to], ...], ...}}                                # [from, to): 404
"""

from __future__ import annotations

import bisect
import copy
import gzip
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

FORMAT_VERSION = 1
ENDPOINTS = ("boxscore", "shotchart", "keyfacts")


def _visible(entry: Dict[str, Any], frame: int) -> bool:
    if entry["f"] > frame:
        return False
    removed = entry.get("r")
    return removed is None or frame < removed


class RecordedFeed:
    def __init__(self, data: Dict[str, Any]) -> None:
        if data.get("v") != FORMAT_VERSION:
            raise ValueError(f"Unsupported recording version {data.get('v')!r} (expected {FORMAT_VERSION})")
        self._data = data
        self._times: List[float] = [float(f["t"]) for f in data["frames"]]
        self._cache: Optional[tuple] = None

    # -- loading ------------------------------------------------------------------------

    @classmethod
    def loads(cls, text: Union[str, bytes]) -> "RecordedFeed":
        raw = text if isinstance(text, bytes) else text.encode("utf-8")
        if raw[:2] == b"\x1f\x8b":  # gzip magic
            raw = gzip.decompress(raw)
        return cls(json.loads(raw.decode("utf-8")))

    @classmethod
    def load(cls, path: Union[str, Path]) -> "RecordedFeed":
        return cls.loads(Path(path).read_bytes())

    # -- the timeline -------------------------------------------------------------------

    @property
    def match(self) -> str:
        return str(self._data.get("match", ""))

    @property
    def frames(self) -> List[Dict[str, Any]]:
        return self._data["frames"]

    @property
    def duration(self) -> float:
        ends = [self._times[-1]] if self._times else [0.0]
        for spans in (self._data.get("gaps") or {}).values():
            ends += [float(end) for _, end in spans]
        return max(ends)

    def event_times(self) -> List[float]:
        """The moments (seconds since the first poll) in which a play-by-play line or a shot first appears, sorted and unique: the
        steps of «Saltar al siguiente evento» (issue #345). The minutes in which nothing new shows (the break between periods, a
        404 window) are a single step."""
        entries = list(self._data["lines"]) + list(self._data["shots"])
        return sorted({float(self._times[e["f"]]) for e in entries if _visible(e, e["f"])})

    def first_event_at(self) -> float:
        """Seconds since the first poll of the first moment a play-by-play line is visible (0 when the recording has none): what comes
        before is the match waiting to start (SCHEDULED, no plays), which a replay does not need to sit through (issue #346)."""
        frames = [entry["f"] for entry in self._data["lines"] if _visible(entry, entry["f"])]
        return float(self._times[min(frames)]) if frames else 0.0

    def frame_time_of(self, iso_utc: str) -> float:
        """Seconds since the first poll of an ISO timestamp taken from the recording's ``polls.jsonl``."""
        return round((datetime.fromisoformat(iso_utc) - datetime.fromisoformat(self._data["started"])).total_seconds(), 3)

    def in_gap(self, endpoint: str, t: float) -> bool:
        return any(float(a) <= t < float(b) for a, b in (self._data.get("gaps") or {}).get(endpoint, []))

    def in_any_gap(self, t: float) -> bool:
        """True while at least one of the three endpoints answered nothing (a client would see a failed poll)."""
        return any(self.in_gap(endpoint, t) for endpoint in ENDPOINTS)

    def document_at(self, t: float, endpoint: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """What FEB served ``t`` seconds in (``endpoint`` = boxscore / shotchart / keyfacts); None = not available."""
        if endpoint and self.in_gap(endpoint, t):
            return None
        frame = bisect.bisect_right(self._times, t) - 1
        if frame < 0:
            return None
        if self._cache is None or self._cache[0] != frame:
            self._cache = (frame, self._build(frame))
        return copy.deepcopy(self._cache[1])

    # -- rebuilding a frame ---------------------------------------------------------------

    def _build(self, frame: int) -> Dict[str, Any]:
        doc = copy.deepcopy(self._data["base"])
        header, status = doc["HEADER"], self._data["frames"][frame]["h"]
        header.update({k: status[k] for k in ("status", "statusText", "quarter", "time") if k in status})
        for team in header.get("TEAM", []):
            if str(team.get("id")) in (status.get("pts") or {}):
                team["pts"] = str(status["pts"][str(team["id"])])
        lines = []
        for entry in self._data["lines"]:
            if not _visible(entry, frame):
                continue
            line = entry["l"]
            for fixed_at, version in entry.get("fix", []):
                if fixed_at <= frame:
                    line = version
            lines.append(copy.deepcopy(line))
        doc["PLAYBYPLAY"] = {**doc.get("PLAYBYPLAY", {}), "LINES": lines}
        doc["SHOTCHART"] = {**doc.get("SHOTCHART", {}),
                            "SHOTS": [copy.deepcopy(s["s"]) for s in self._data["shots"] if _visible(s, frame)]}
        return doc
