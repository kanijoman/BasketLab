"""Builds a recording (``recorded_feed`` format) incrementally from the documents of a feed (issue #416).

Used by the app to keep its own recording of the match it follows live, and by ``live_prep.recording_pack`` to pack what the CI
recorder saved: the same code makes both, so a recording made on the tablet replays exactly like one of CI. The play-by-play of a
match is append-only, so each line is stored once with the frame it first appeared in (``f``), the frames it was corrected in
(``fix``) and the frame it disappeared in (``r``); shots are stored the same way. Memory stays small: no document per poll is kept.
Standard library only.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .recorded_feed import FORMAT_VERSION
from .replay import _ROSTER_FIELDS, _TEAM_FIELDS


def slim_base(doc: Dict[str, Any]) -> Dict[str, Any]:
    """The part of a document that does not change over the match, without box-score statistics."""
    return {
        "HEADER": json.loads(json.dumps(doc["HEADER"])),
        "BOXSCORE": {"TEAM": [
            {**{k: team[k] for k in _TEAM_FIELDS if k in team},
             "PLAYER": [{k: p[k] for k in _ROSTER_FIELDS if k in p} for p in team.get("PLAYER", [])]}
            for team in doc["BOXSCORE"]["TEAM"]]},
        "PLAYBYPLAY": {k: v for k, v in (doc.get("PLAYBYPLAY") or {}).items() if k != "LINES"},
        "SHOTCHART": {**{k: v for k, v in (doc.get("SHOTCHART") or {}).items() if k not in ("SHOTS", "TEAM")}, "TEAM": []},
    }


def _frame_header(doc: Dict[str, Any]) -> Dict[str, Any]:
    header = doc["HEADER"]
    return {"status": str(header.get("status")), "statusText": header.get("statusText"), "quarter": header.get("quarter"),
            "time": header.get("time"), "pts": {str(t["id"]): int(t.get("pts") or 0) for t in header.get("TEAM", [])}}


class RecordingBuilder:
    def __init__(self, match: str, started: str) -> None:
        self.match, self.started = str(match), started
        self._lines: Dict[str, Dict[str, Any]] = {}      # line number -> entry (``_cur`` is the content now)
        self._shots: Dict[str, Dict[str, Any]] = {}      # canonical shot -> entry
        self._frames: List[Dict[str, Any]] = []
        self._last: Optional[Dict[str, Any]] = None
        self._open: Dict[str, List[float]] = {}          # endpoint -> [first failing time, last failing time]
        self._gaps: Dict[str, List[List[float]]] = {}

    @property
    def frames(self) -> int:
        return len(self._frames)

    def add(self, t: float, doc: Dict[str, Any]) -> None:
        """A complete document served ``t`` seconds after the first poll."""
        frame = len(self._frames)
        self._frames.append({"t": t, "h": _frame_header(doc)})
        self._add_lines(frame, doc["PLAYBYPLAY"]["LINES"])
        self._add_shots(frame, (doc.get("SHOTCHART") or {}).get("SHOTS") or [])
        for endpoint, (first, _last) in self._open.items():
            self._gaps.setdefault(endpoint, []).append([first, t])
        self._open = {}
        self._last = doc

    def gap(self, endpoint: str, t: float) -> None:
        """``endpoint`` failed at ``t``. Before the first document it is just a match that has not started: no gap."""
        if not self._frames:
            return
        first = self._open.get(endpoint, [t, t])[0]
        self._open[endpoint] = [first, t]

    def _add_lines(self, frame: int, lines: List[Dict[str, Any]]) -> None:
        seen = set()
        for line in lines:
            num = str(line["num"])
            seen.add(num)
            entry = self._lines.get(num)
            if entry is None:
                self._lines[num] = {"f": frame, "l": line, "_cur": line}
                continue
            entry.pop("r", None)
            if line != entry["_cur"]:
                entry.setdefault("fix", []).append([frame, line])
                entry["_cur"] = line
        for num, entry in self._lines.items():
            if num not in seen and "r" not in entry:
                entry["r"] = frame

    def _add_shots(self, frame: int, shots: List[Dict[str, Any]]) -> None:
        now = {json.dumps(s, sort_keys=True): s for s in shots}
        for key, shot in now.items():
            self._shots.setdefault(key, {"f": frame, "s": shot}).pop("r", None)
        for key, entry in self._shots.items():
            if key not in now and "r" not in entry:
                entry["r"] = frame

    def _ordered_lines(self) -> List[Dict[str, Any]]:
        final_order = [str(line["num"]) for line in self._last["PLAYBYPLAY"]["LINES"]]
        ordered = [self._lines[n] for n in final_order]
        for num, entry in self._lines.items():  # lines removed before the end: keep them where their number belongs
            if num not in final_order:
                position = next((i for i, e in enumerate(ordered) if int(e["l"]["num"]) < int(num)), len(ordered))
                ordered.insert(position, entry)
        return [{k: v for k, v in entry.items() if k != "_cur"} for entry in ordered]

    def _ordered_shots(self) -> List[Dict[str, Any]]:
        final = [json.dumps(s, sort_keys=True) for s in (self._last.get("SHOTCHART") or {}).get("SHOTS") or []]
        return [self._shots[k] for k in final] + [e for k, e in self._shots.items() if k not in final]

    def pack(self) -> Optional[Dict[str, Any]]:
        """The recording so far (``None`` while no document has arrived). Gaps still open end at their last failure."""
        if self._last is None:
            return None
        gaps = {endpoint: [list(g) for g in windows] for endpoint, windows in self._gaps.items()}
        for endpoint, (first, last) in self._open.items():
            gaps.setdefault(endpoint, []).append([first, last])
        return {"v": FORMAT_VERSION, "match": self.match, "started": self.started, "base": slim_base(self._last),
                "lines": self._ordered_lines(), "shots": self._ordered_shots(), "frames": list(self._frames), "gaps": gaps}
