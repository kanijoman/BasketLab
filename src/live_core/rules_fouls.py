"""Player foul alerts.

A player is eliminated with 5 fouls, so alerting on the 5th is useless. Warnings fire
early enough to act: ``min(period + 1, 3)`` fouls for the rival (``warn_threshold``); for the own players
the 2nd foul is a warning of the first half (#622, #929) and so is the 3rd; 4 fouls (one from elimination) is critical. Messages are shown to the coaching staff, hence Spanish.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .clock import game_seconds_left

FOUL_OUT = 5
WARNING_CAP = 3
CRITICAL_PF = FOUL_OUT - 1
SECOND_HALF_FIRST_PERIOD = 3
EARLY_PF = 2          # the second foul: a warning of the first half for the own players (#622, warning since #929)


@dataclass(frozen=True)
class FoulAlert:
    player_id: str
    pf: int
    severity: str  # "warning" | "critical"
    message: str


def game_end_quiet(snap: Dict[str, Any], quiet_s: int) -> bool:
    """True in the last ``quiet_s`` seconds of the game (overtime counts only its own period): a foul alert has no use any more (#403)."""
    return game_seconds_left(snap["period"], snap["remaining"]) <= quiet_s


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
    early_notice: bool = False,
) -> Optional[FoulAlert]:
    """Return an alert for this player's foul count, or None (issue #241, R4: risk of elimination).

    ``last_alerted_pf`` is the foul count already alerted: the same count never repeats. Four fouls (one from elimination)
    is always critical. Three fouls is a risk only while more than ``min_left_s`` of the game is left (with less the player
    will most likely finish): a warning (#929: the staff of 2536159 wanted two fouls in the first quarter as a warning at least, so the
    third cannot be less). Two fouls alert only with ``early_notice`` and only in the first half, as a warning (#622: the staff
    expected it before the third); the recommender does not ask for it, so a player with two fouls is still a swap. ``seconds_left=None``
    (no clock at hand) counts as plenty.
    """
    if pf >= FOUL_OUT or pf <= last_alerted_pf:
        return None
    if pf == CRITICAL_PF:
        return FoulAlert(
            player_id, pf, "critical",
            f"{name}: {pf} faltas personales, a una de la eliminación. Gestionar sus minutos.",
        )
    if early_notice and pf == EARLY_PF and period < SECOND_HALF_FIRST_PERIOD:
        return FoulAlert(player_id, pf, "warning", f"{name}: {pf} faltas personales en el periodo {period}. Ojo con la siguiente.")
    if pf >= WARNING_CAP and (seconds_left is None or seconds_left > min_left_s):
        return FoulAlert(
            player_id, pf, "warning",
            f"{name}: {pf} faltas personales en el periodo {period}. Valorar cambio.",
        )
    return None
