"""Four Factors rule: advise on the main lever when it costs enough points per 100 possessions."""

from __future__ import annotations

from typing import Any, Dict, List

from .advice_types import Advice, RuleContext

_LABELS = {
    "efg": ("Tiro", "eFG%", "Mejorar la selección y la calidad del tiro."),
    "tov": ("Balón", "pérdidas (TOV%)", "Pérdidas: asegurar el balón."),
    "orb": ("Rebote ofensivo", "rebote ofensivo (ORB%)", "Reforzar el rebote ofensivo."),
    "ftr": ("Tiros libres", "tiros libres por tiro de campo", "Atacar el aro y forzar faltas."),
}


def _own_vs_rival(lever: str, result: Dict[str, Any]) -> str:
    own, rival = result["factors_own"][lever], result["factors_rival"][lever]
    if lever == "ftr":
        return f"{own:.2f} vs {rival:.2f}"
    return f"{own:.0%} vs {rival:.0%}"


def four_factors_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    if ctx.model is None:
        return []
    result = ctx.model.evaluate(snap)
    if not result or not result["reliable"] or not result["lever"]:
        return []
    lever = result["lever"]
    pts100 = result["pts100"][lever]
    if pts100 > -ctx.config.ff_lever_min_pts100:
        return []
    title, metric, action = _LABELS[lever]
    return [Advice(
        key=f"lever:{lever}", id="four_factors_lever", severity="warning", category="four_factors",
        message=f"{title}: {metric} {_own_vs_rival(lever, result)} ({pts100:+.1f} pts/100 posesiones). {action}",
        evidence={"lever": lever, "pts100": pts100, "possessions": result["possessions"],
                  "factors_own": result["factors_own"], "factors_rival": result["factors_rival"],
                  "contributions": result["contributions"]},
        rearm_s=ctx.config.ff_lever_rearm_s,
    )]
