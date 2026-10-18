"""Records of the possession tracker: a possession and the quality of the play-by-play it was built from."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Quality of the source data, from the alternation breaks of a game (two counted possessions of the same team in
# a row inside one period). Thresholds agreed on 16/10/2026 after measuring 1,709 historical games (85 % / 11 % / 4 %).
BREAKS_OK_MAX = 4
BREAKS_DOUBTFUL_MAX = 7


def level_for_breaks(breaks: int) -> str:
    """"ok" up to 4 breaks, "doubtful" up to 7, "unreliable" above (fall back to the estimated possessions)."""
    if breaks <= BREAKS_OK_MAX:
        return "ok"
    return "doubtful" if breaks <= BREAKS_DOUBTFUL_MAX else "unreliable"


@dataclass
class Possession:
    """One possession of a team.

    ``origin``: period_start | made_basket | turnover | steal | def_rebound | team_def_rebound | trip | unknown.
    ``outcome``: made_fg | ft_made | missed_shot | turnover | trip | period_end | inferred.
    ``counted`` is True when an event of the feed ended it (the ones that count as possessions); ``repaired`` marks
    a possession rebuilt around a feed error (inferred, or a misattributed rebound reinterpreted as the shooter's own),
    ``gap_before`` that the rival's possession before it is missing from the feed. ``orebs`` are the offensive
    rebounds recorded by the feed; ``repaired_orebs`` the ones reinterpreted here, for the possession only (never for
    the rebound statistics). ``timeouts`` are (team, elapsed) pairs called before or during it.
    """

    team_id: str
    period: int
    start_elapsed: int
    end_elapsed: int
    start_num: int
    end_num: int
    origin: str
    outcome: str = "inferred"
    counted: bool = True
    points: int = 0
    second_chance_points: int = 0
    orebs: int = 0
    repaired_orebs: int = 0
    points_by_player: Dict[str, int] = field(default_factory=dict)
    timeouts: Tuple[Tuple[str, int], ...] = ()
    steal: bool = False
    gap_before: bool = False
    repaired: bool = False
    shot_kind: str = ""      # fg2 | fg3 | dunk | ft: the last shot attempt when it ended with a shot ("" for a turnover)

    @property
    def duration(self) -> int:
        return max(0, self.end_elapsed - self.start_elapsed)


@dataclass
class PossessionQuality:
    """How reliable the possessions of a game are. ``breaks_raw`` is measured before repairing misattributed rebounds."""

    counted: Dict[str, int]
    breaks_raw: int
    breaks: int
    repaired_rebounds: int
    inferred: int
    implicit_offensive: int
    implicit_defensive: int
    technical_ft: int
    level: str
    difference: int       # |possessions of one team - the other|: 0-1 when the feed is complete
    technical_points: Dict[str, int] = field(default_factory=dict)   # free throws of technical fouls: no possession
    technical_by_player: Dict[str, Dict[str, int]] = field(default_factory=dict)   # the same points per team and player


class QualityLog:
    """Counters the tracker updates while it works; ``build`` turns them into a ``PossessionQuality``."""

    def __init__(self) -> None:
        self.counted: Counter = Counter()
        self.breaks = self.breaks_raw = 0
        self.repaired = self.inferred = self.implicit_off = self.implicit_def = self.technical_ft = 0
        self._last: Optional[Tuple[str, int, str]] = None        # (team, period, outcome) of the last counted end
        self._last_raw: Optional[Tuple[str, int, str]] = None    # same, before repairing rebounds

    def note_end(self, team: str, period: int, outcome: str, actual: bool = True, raw: bool = True) -> None:
        """Count a possession end and any alternation break (same team twice in a row inside a period)."""
        end = (team, period, outcome)
        if raw:
            self.breaks_raw += self._is_break(self._last_raw, end)
            self._last_raw = end
        if actual:
            self.counted[team] += 1
            self.breaks += self._is_break(self._last, end)
            self._last = end

    @staticmethod
    def _is_break(prev: Optional[Tuple[str, int, str]], end: Tuple[str, int, str]) -> bool:
        return bool(prev and prev[0] == end[0] and prev[1] == end[1] and prev[2] != "trip")

    def build(self, teams: List[str], technical_points: Dict[str, int],
              technical_by_player: Optional[Dict[str, Dict[str, int]]] = None) -> PossessionQuality:
        counted = dict(self.counted)
        return PossessionQuality(
            counted=counted, breaks_raw=self.breaks_raw, breaks=self.breaks, repaired_rebounds=self.repaired,
            inferred=self.inferred, implicit_offensive=self.implicit_off, implicit_defensive=self.implicit_def,
            technical_ft=self.technical_ft, level=level_for_breaks(self.breaks_raw),
            difference=abs(counted.get(teams[0], 0) - counted.get(teams[1], 0)), technical_points=dict(technical_points),
            technical_by_player={t: dict(p) for t, p in (technical_by_player or {}).items()})
