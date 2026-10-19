"""The possessions of the live game, kept incrementally (issue #357).

``PossessionCounters`` wraps a ``PossessionTracker``: ``feed(event)`` for every applied event and ``snapshot()`` for the engine's
snapshot (standard library only, it runs on the tablet). Over the possessions already CLOSED (the one in progress is not counted
until the event that ends it arrives): ``counted`` possessions of each team, ``origins`` (per team, by the way the possession started:
``n`` counted possessions and ``pts`` points scored in them; the free throws of technical fouls are the origin ``technical``, so the
points of a team add up to its score once its last possession is closed) and the ``quality`` of the feed (alternation breaks).
A game that does not have two teams has none (``snapshot()`` is ``None``).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from .events import Event
from .possession_types import Possession
from .possessions import PossessionTracker


class PossessionCounters:
    def __init__(self, team_ids: List[str]) -> None:
        self.tracker: Optional[PossessionTracker] = PossessionTracker(team_ids) if len(team_ids) == 2 else None
        self._counted: Dict[str, int] = defaultdict(int)
        self._origins: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"n": 0, "pts": 0}))

    def feed(self, event: Event) -> None:
        if self.tracker is None:
            return
        for possession in self.tracker.feed(event):
            self._add(possession)

    def _add(self, p: Possession) -> None:
        entry = self._origins[p.team_id][p.origin]
        entry["pts"] += p.points
        if p.counted:
            self._counted[p.team_id] += 1
            entry["n"] += 1

    def snapshot(self) -> Optional[Dict[str, Any]]:
        if self.tracker is None:
            return None
        quality = self.tracker.quality()
        origins = {team: {origin: dict(entry) for origin, entry in by_origin.items()} for team, by_origin in self._origins.items()}
        for team, points in self.tracker.technical_points.items():
            origins.setdefault(team, {})["technical"] = {"n": 0, "pts": int(points)}
        return {
            "counted": dict(self._counted),
            "origins": origins,
            "quality": {"level": quality.level, "breaks_raw": quality.breaks_raw, "breaks": quality.breaks,
                        "inferred": quality.inferred, "difference": quality.difference},
        }
