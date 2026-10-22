"""Teams of different divisions in one package (issue #464): the prior of the matchup is not the plain gap of their ratings.

A team's net rating and Four Factors are measured against the teams of ITS division (Cultural Leonesa in 2ª FEB, Alimerka Oviedo in 1ª FEB), so the
gap between two such ratings says nothing about the tie. The package says it (``baselines.cross_division``) and corrects the prior:

* ``LEVEL_GAP_NET_RTG``: points of net rating per 100 possessions that separate two consecutive divisions. ``None`` = not calibrated yet (it needs real
  games between divisions: the Copa); ``python -m src.live_prep.level_gap`` estimates it. Calibrated, the net rating prior moves by it.
* Until then (and for the Four Factors, which have no units to move) the prior is shrunk by ``CROSS_DIVISION_SHRINK``. Provisional.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple

LEVEL_GAP_NET_RTG: Optional[float] = None
CROSS_DIVISION_SHRINK = 0.5


def team_level(counts: Mapping[int, int]) -> Optional[int]:
    """The division a team belongs to: the one of most of its games with a known division (a tie: the higher one, the lower number)."""
    return min(counts, key=lambda level: (-counts[level], level)) if counts else None


def adjust(four_factors: Dict[str, float], net: float, own_level: Optional[int], rival_level: Optional[int]) -> Tuple[Dict[str, float], float, Optional[Dict[str, Any]]]:
    """``(four_factors_prior, net_rtg_prior, marker)`` corrected for the divisions; unchanged (marker ``None``) when they are the same or unknown."""
    if own_level is None or rival_level is None or own_level == rival_level:
        return four_factors, net, None
    shrunk = {factor: round(value * CROSS_DIVISION_SHRINK, 4) for factor, value in four_factors.items()}
    if LEVEL_GAP_NET_RTG is None:
        adjusted, mode = round(net * CROSS_DIVISION_SHRINK, 3), "shrink"
    else:
        adjusted, mode = round(net + LEVEL_GAP_NET_RTG * (rival_level - own_level), 3), "gap"
    return shrunk, adjusted, {"own_level": own_level, "rival_level": rival_level, "adjusted": mode}
