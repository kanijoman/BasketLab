"""Player foul alerts.

A player is eliminated with 5 fouls, so alerting on the 5th is useless. Warnings fire
early enough to act: ``min(period + 1, 3)`` fouls; 4 fouls (one from elimination) is
critical. Messages are shown to the coaching staff, hence Spanish.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

FOUL_OUT = 5
WARNING_CAP = 3
CRITICAL_PF = FOUL_OUT - 1
SECOND_HALF_FIRST_PERIOD = 3


@dataclass(frozen=True)
class FoulAlert:
    player_id: str
    pf: int
    severity: str  # "warning" | "critical"
    message: str


def warn_threshold(period: int) -> int:
    """Personal fouls from which a warning fires in ``period`` (1-based, OT >= 5)."""
    return min(max(period, 1) + 1, WARNING_CAP)


def evaluate_player_fouls(
    player_id: str,
    name: str,
    pf: int,
    period: int,
    last_alerted_pf: int = 0,
    seconds_left: Optional[int] = None,
    min_left_s: int = 360,
) -> Optional[FoulAlert]:
    """Return an alert for this player's foul count, or None (issue #241, R4: risk of elimination).

    ``last_alerted_pf`` is the foul count already alerted: the same count never repeats. Four fouls (one from elimination)
    is always critical. Three fouls is a risk only while more than ``min_left_s`` of the game is left (with less the player
    will most likely finish): information in the first half, where the coach already changes the player (89 % within two
    minutes), a warning in the second. Two fouls never alert. ``seconds_left=None`` (no clock at hand) counts as plenty.
    """
    if pf >= FOUL_OUT or pf <= last_alerted_pf:
        return None
    if pf == CRITICAL_PF:
        return FoulAlert(
            player_id, pf, "critical",
            f"{name}: {pf} faltas personales, a una de la eliminación. Gestionar sus minutos.",
        )
    if pf >= WARNING_CAP and (seconds_left is None or seconds_left > min_left_s):
        return FoulAlert(
            player_id, pf, "warning" if period >= SECOND_HALF_FIRST_PERIOD else "info",
            f"{name}: {pf} faltas personales en el periodo {period}. Valorar cambio.",
        )
    return None
