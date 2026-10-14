"""Shot zones tracked from the SHOTCHART feed (standard library only).

``team`` in SHOTCHART is 0 / 1 = HEADER.TEAM[0] / [1] (verified: the shots are exactly the
field-goal events of the play-by-play). Updates are idempotent: the feed is append-only and
the same shot is never counted twice.

A shot has the JERSEY NUMBER of its player (``player``, verified on the sample game: all of its shots match the box score's ``no``);
with the box score's mapping (``dorsals``: team id -> jersey number -> player id) the zones are also kept per player
(``player_snapshot``) for the rules that name a rival player's zone. A shot of an unknown number still counts for its team.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence, Set, Tuple

from .zones import classify_shot


def _shots(feed: Any) -> list:
    if isinstance(feed, dict):
        return feed.get("SHOTS") or []
    return feed if isinstance(feed, list) else []


def _dorsal(value: Any) -> str:
    """A jersey number as the box score writes it ("04") and the shot chart ("4") must compare equal."""
    text = str(value).strip()
    return str(int(text)) if text.isdigit() else text


class ShotTracker:
    def __init__(self, team_ids: Sequence[str], dorsals: Optional[Mapping[str, Mapping[str, str]]] = None) -> None:
        self._teams = list(team_ids)
        self._seen: Set[Tuple[Any, ...]] = set()
        self._zones: Dict[str, Dict[str, Dict[str, int]]] = {tid: {} for tid in self._teams}
        self._players: Dict[str, Dict[str, Dict[str, Dict[str, int]]]] = {tid: {} for tid in self._teams}
        self._dorsals: Dict[str, Dict[str, str]] = {}
        self.set_dorsals(dorsals or {})

    def set_dorsals(self, dorsals: Mapping[str, Mapping[str, str]]) -> None:
        self._dorsals = {tid: {_dorsal(no): pid for no, pid in table.items()} for tid, table in dorsals.items()}

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
            team = self._teams[team_index]
            cells = [self._zones[team].setdefault(zone["zone"], {"a": 0, "m": 0, "pts": 0})]
            pid = self._dorsals.get(team, {}).get(_dorsal(shot.get("player")))
            if pid is not None:
                cells.append(self._players[team].setdefault(pid, {}).setdefault(zone["zone"], {"a": 0, "m": 0, "pts": 0}))
            for cell in cells:
                cell["a"] += 1
                if made:
                    cell["m"] += 1
                    cell["pts"] += zone["points"]

    def player_snapshot(self) -> Dict[str, Dict[str, Dict[str, Dict[str, int]]]]:
        """Team id -> player id -> zone -> {"a", "m", "pts"} for the shots whose jersey number the box score maps to a player."""
        return {tid: {pid: {z: dict(c) for z, c in sorted(zones.items())} for pid, zones in sorted(players.items())}
                for tid, players in self._players.items()}

    def snapshot(self) -> Dict[str, Dict[str, Dict[str, int]]]:
        return {tid: {z: dict(c) for z, c in sorted(zones.items())} for tid, zones in self._zones.items()}
