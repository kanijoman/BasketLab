"""Shot zones tracked from the SHOTCHART feed (standard library only).

``team`` in SHOTCHART is 0 / 1 = HEADER.TEAM[0] / [1] (verified: the shots are exactly the
field-goal events of the play-by-play). Updates are idempotent: the feed is append-only and
the same shot is never counted twice.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Set, Tuple

from .zones import classify_shot


def _shots(feed: Any) -> list:
    if isinstance(feed, dict):
        return feed.get("SHOTS") or []
    return feed if isinstance(feed, list) else []


class ShotTracker:
    def __init__(self, team_ids: Sequence[str]) -> None:
        self._teams = list(team_ids)
        self._seen: Set[Tuple[Any, ...]] = set()
        self._zones: Dict[str, Dict[str, Dict[str, int]]] = {tid: {} for tid in self._teams}

    def update(self, feed: Optional[Any]) -> None:
        for shot in _shots(feed):
            if not isinstance(shot, dict):
                continue
            try:
                team_index = int(shot["team"])
                float(shot["x"]), float(shot["y"])
            except (KeyError, TypeError, ValueError):
                continue
            if not 0 <= team_index < len(self._teams):
                continue
            key = (shot.get("quarter"), shot.get("t"), shot.get("x"), shot.get("y"),
                   team_index, shot.get("player"), shot.get("m"))
            if key in self._seen:
                continue
            self._seen.add(key)
            zone = classify_shot(shot)
            made = str(shot.get("m")) == "1"
            cell = self._zones[self._teams[team_index]].setdefault(zone["zone"], {"a": 0, "m": 0, "pts": 0})
            cell["a"] += 1
            if made:
                cell["m"] += 1
                cell["pts"] += zone["points"]

    def snapshot(self) -> Dict[str, Dict[str, Dict[str, int]]]:
        return {tid: {z: dict(c) for z, c in sorted(zones.items())} for tid, zones in self._zones.items()}
