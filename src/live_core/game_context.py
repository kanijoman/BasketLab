"""Game context: the phase of the match changes how urgent each alert is.

``decided``: |margin| >= ``decided_margin`` with less than ``decided_remaining_s`` left of the 4th period. Only fatigue and rotation
alerts are worth showing (issue #320: ``kept_when_decided``; the rest is silenced, not recorded, so it comes back if the game
reopens) and fatigue is kept at full urgency (it even alerts earlier, see ``rules_rotation``).
``close_late``: |margin| <= ``close_margin`` with ``close_remaining_s`` or less left of the 4th period, or an overtime
within reach: fouls and rhythm (timeouts) go up one level and fatigue goes down (the best players stay on court).
An alert whose severity changes carries the phase in its key (``key~phase``), so a lowered alert never blocks the
normal one when the game opens up again. The shifts are provisional business thresholds, to confirm with the staff.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict

from .advice_types import Advice
from .config import RuleConfig

PHASES = ("normal", "close_late", "decided")
_LEVELS = ("critical", "warning", "info")   # most to least urgent

# phase -> category -> shift: +1 raises the urgency one level, -1 lowers it
PHASE_SHIFT: Dict[str, Dict[str, int]] = {
    "decided": {"four_factors": -1, "rival": -1, "gestion": -1},
    "close_late": {"faltas": 1, "gestion": 1, "rotacion": -1},
}

_REGULATION_LAST_PERIOD = 4


# What still says something in a decided game (issue #320): fatigue and rotation, plus what is a rule of the game, not a tactic
# (an illegal lineup, a player about to be disqualified).
_DECIDED_CATEGORIES = ("rotacion", "descanso")
_DECIDED_IDS = ("disqualification_risk", "formation_lineup")


def kept_when_decided(advice: Advice) -> bool:
    return advice.category in _DECIDED_CATEGORIES or advice.id in _DECIDED_IDS


def game_phase(snap: Dict[str, Any], own_id: Any, rival_id: Any, config: RuleConfig) -> Dict[str, Any]:
    """``{phase, margin, remaining_s}``: the margin is from the own team's side; without both teams the game is normal."""
    period, remaining, score = snap["period"], snap["remaining"], snap.get("score") or {}
    if own_id not in score or rival_id not in score:
        return {"phase": "normal", "margin": 0, "remaining_s": remaining}
    margin = score[own_id] - score[rival_id]
    last_period = period == _REGULATION_LAST_PERIOD
    if last_period and remaining < config.decided_remaining_s and abs(margin) >= config.decided_margin:
        phase = "decided"
    elif abs(margin) <= config.close_margin and ((last_period and remaining <= config.close_remaining_s)
                                                   or period > _REGULATION_LAST_PERIOD):
        phase = "close_late"
    else:
        phase = "normal"
    return {"phase": phase, "margin": margin, "remaining_s": remaining}


def adjust_for_phase(advice: Advice, context: Dict[str, Any]) -> Advice:
    """The alert at the urgency the phase gives it; the very same object when the phase leaves it alone."""
    shift = PHASE_SHIFT.get(context["phase"], {}).get(advice.category, 0)
    level = _LEVELS.index(advice.severity)
    adjusted = min(len(_LEVELS) - 1, max(0, level - shift))
    if not shift or adjusted == level:
        return advice
    return dataclasses.replace(
        advice, severity=_LEVELS[adjusted], key=f"{advice.key}~{context['phase']}",
        evidence={**advice.evidence, "phase": context["phase"], "base_severity": advice.severity},
    )
