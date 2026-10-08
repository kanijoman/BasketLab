"""Rival scouting rules: players on court producing far above their season rate."""

from __future__ import annotations

import math
from typing import Any, Dict, List

from .advice_types import Advice, RuleContext
from .profiles import DEFAULT_IMPACT_LEAGUE, IMPACT_METRICS

GAME_SECONDS = 2400

# metric -> (Spanish noun for the message, tactical response)
_TEXT = {
    "pts": ("pts", "Ayudas, doblar o no dejarle tirar cómodo."),
    "orb": ("rebotes ofensivos", "Bloquear el rebote y reforzar el balance defensivo."),
    "stl": ("robos", "Cuidar el pase y el bote: está recuperando balones."),
    "ast": ("asistencias", "Cortar las líneas de pase y presionar al organizador."),
    "fg3m": ("triples", "Salir al tirador y cerrar los bloqueos."),
    "fta": ("tiros libres", "Evitar faltas en su ataque: defender sin saltar ni meter la mano."),
}


def _observed(player: Dict[str, Any], metric: str) -> int:
    return player["pts"] if metric == "pts" else player.get("stats", {}).get(metric, 0)


def rival_player_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    if not ctx.rival_team_id:
        return []
    cfg = ctx.config
    minimum = {"pts": cfg.rival_min_pts, "orb": cfg.rival_min_orb, "stl": cfg.rival_min_stl,
               "ast": cfg.rival_min_ast, "fg3m": cfg.rival_min_fg3m, "fta": cfg.rival_min_fta}
    league = {**DEFAULT_IMPACT_LEAGUE, **ctx.impact_league}
    out = []
    for pid, p in snap["players"].items():
        if p["team_id"] != ctx.rival_team_id or not p["on_court"] or p["minutes"] < cfg.rival_min_seconds:
            continue
        base = (ctx.rival_baselines.get(pid) or {}).get("impact40")
        rates = base or league
        for metric in IMPACT_METRICS:
            observed = _observed(p, metric)
            expected = rates[metric] * p["minutes"] / GAME_SECONDS
            if observed < minimum[metric] or observed - expected < cfg.rival_sigma * math.sqrt(max(expected, 1.0)):
                continue
            noun, response = _TEXT[metric]
            out.append(Advice(
                key=f"rival_hot:{pid}:{metric}", id="rival_hot_player", severity="warning", category="rival",
                message=(f"Rival {p['name'].strip()}: {observed} {noun} en {p['minutes'] // 60} min "
                         f"(esperado {expected:.1f}). {response}"),
                evidence={"player_id": pid, "team_id": p["team_id"], "metric": metric, "observed": observed,
                          "expected": round(expected, 3), "minutes_s": p["minutes"],
                          "has_baseline": bool(base)},
            ))
    return out
