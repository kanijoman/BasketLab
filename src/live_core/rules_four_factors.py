"""Four Factors rule: advise on the main lever when it costs enough points per 100 possessions.

It is said when the lever appears and again only if the lever changes or its deficit gets ``lever_step_pts100`` (5) points
per 100 worse than the worst already said, measured on the value without the shrinkage towards the season prior (issue
#241, R6). The rule remembers (``ctx.memory``) the last lever, how many times it has changed and the worst step said, so
nothing repeats by time and getting better and worse again says nothing new.
"""

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


def _stable_lever(result: Dict[str, Any], ctx: RuleContext) -> str:
    """The main lever, but the one already said stays while it still costs points and the new one is not clearly worse.

    Two factors with almost the same deficit swap places all the time; without this every swap would be a "new" lever.
    """
    lever, config = result["lever"], ctx.config
    previous = (ctx.memory.get("lever") or {}).get("name")
    if previous and previous != lever:
        still = result["pts100"][previous] <= -config.ff_lever_min_pts100
        if still and result["pts100"][lever] > result["pts100"][previous] - config.lever_step_pts100:
            return previous
    return lever


def four_factors_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    if ctx.model is None:
        return []
    result = ctx.model.evaluate(snap)
    if not result or not result["reliable"] or not result["lever"]:
        return []
    lever = _stable_lever(result, ctx)
    pts100 = result["pts100"][lever]
    if pts100 > -ctx.config.ff_lever_min_pts100:
        return []
    title, metric, action = _LABELS[lever]
    raw = result["pts100_raw"][lever]
    step = int(max(0.0, -raw) // ctx.config.lever_step_pts100)
    memory = ctx.memory.setdefault("lever", {"name": None, "changes": 0, "step": -1})
    if memory["name"] == lever and step <= memory["step"]:
        return []        # the same lever, not worse than what was already said
    if memory["name"] != lever:
        memory["changes"] += 1
    memory["name"], memory["step"] = lever, max(step, memory["step"] if memory["name"] == lever else -1)
    return [Advice(
        key=f"lever:{lever}:{memory['changes']}:{step}", id="four_factors_lever", severity="info", category="four_factors",
        message=(f"{title}: {metric} {_own_vs_rival(lever, result)} ({pts100:+.1f} pts/100 posesiones; "
                 f"{raw:+.0f} sin ajustar al histórico). {action}"),
        evidence={"lever": lever, "pts100": pts100, "pts100_raw": raw, "possessions": result["possessions"],
                  "factors_own": result["factors_own"], "factors_rival": result["factors_rival"],
                  "contributions": result["contributions"]},
    )]
