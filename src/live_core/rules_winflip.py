"""Flip of the win probability (issue #258), W1 ``win_flip``.

The probability of winning falls ``wp_flip_drop`` (20 points) or more within ``wp_flip_window_s`` (5 minutes): a warning with the
main lever of the win probability (#256) and, for a Four Factors lever, the recommender's proposal (``AdviceEngine._with_proposal``).
The rule remembers the probability of every evaluation in ``ctx.memory`` and compares the current one with the highest of the
window, so a fall spread over more than the window says nothing, and the same fall is said once (``rearm_s`` is the window: it
cannot repeat while the high point is still inside it). The probability is experimental (#257): the threshold is provisional.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .advice_types import Advice, RuleContext
from .rules_four_factors import _LABELS

_PACE_TEXT = {"up": "subir el ritmo", "down": "bajar el ritmo"}


def _remember(ctx: RuleContext, now: int, p: float) -> List[List[float]]:
    """The probability history of this game, without what is older than the window or later than ``now`` (a replay that went back)."""
    history: List[List[float]] = ctx.memory.setdefault("win_history", [])
    while history and history[-1][0] >= now:
        history.pop()
    history.append([now, p])
    window = ctx.config.wp_flip_window_s
    while history and now - history[0][0] > window:
        history.pop(0)
    return history


def pace_reason_text(lever: Dict[str, Any]) -> str:
    """Why the pace is advised when the recent pace decided it (#488): «el ritmo subió (+9) y nos perjudicó (-8 en los últimos minutos)»."""
    reason = lever.get("reason")
    if not reason:
        return ""
    moved = "subió" if reason["faster"] else "bajó"
    effect = "nos favoreció" if reason["kind"] == "benefit" else "nos perjudicó"
    return f"el ritmo {moved} ({reason['change']:+.0f}) y {effect} ({reason['net']:+d} en los últimos minutos)"


def _lever_text(lever: Optional[Dict[str, Any]]) -> str:
    if lever is None:
        return ""
    gain = f"+{lever['gain'] * 100:.0f} %"
    if lever["id"] == "pace":
        why = pace_reason_text(lever)
        return f" Palanca principal: {_PACE_TEXT.get(lever.get('direction'), 'cambiar el ritmo')} ({gain}{'; ' + why if why else ''})."
    title, _metric, action = _LABELS[lever["id"]]
    return f" Palanca principal: {title.lower()} ({gain} si vuelve a su nivel habitual). {action}"


def win_flip_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    model = ctx.win_prob
    if model is None:
        return []
    four_factors = ctx.model.evaluate(snap) if ctx.model is not None else None
    current = model.evaluate(snap, four_factors)
    if current is None:
        return []
    window = ctx.config.wp_flip_window_s
    history = _remember(ctx, snap["elapsed"], current["p"])
    before = max(p for _, p in history)
    drop = before - current["p"]
    if drop < ctx.config.wp_flip_drop:
        return []
    levers = model.levers(snap, four_factors)
    lever = levers[0] if levers else None
    return [Advice(
        key="win_flip", id="win_flip", severity="warning", category="probabilidad",
        message=(f"La probabilidad de victoria ha caído de {before:.0%} a {current['p']:.0%} en los últimos {window // 60} min "
                 f"(estimación).{_lever_text(lever)}"),
        evidence={"p_before": round(before, 4), "p_now": current["p"], "drop": round(drop, 4), "window_s": window,
                  "projected_margin": current["projected_margin"],
                  "lever": lever["id"] if lever else None, "lever_gain": lever["gain"] if lever else None,
                  **({"lever_direction": lever["direction"]} if lever and lever.get("direction") else {})},
        rearm_s=window,
    )]
