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
) -> Optional[FoulAlert]:
    """Return an alert for this player's foul count, or None.

    ``last_alerted_pf`` is the foul count already alerted: the same count never repeats.
    """
    if pf >= FOUL_OUT or pf <= last_alerted_pf:
        return None
    if pf == CRITICAL_PF:
        return FoulAlert(
            player_id, pf, "critical",
            f"{name}: {pf} faltas personales, a una de la eliminación. Gestionar sus minutos.",
        )
    if pf >= warn_threshold(period):
        return FoulAlert(
            player_id, pf, "warning",
            f"{name}: {pf} faltas personales en el periodo {period}. Valorar cambio.",
        )
    return None
