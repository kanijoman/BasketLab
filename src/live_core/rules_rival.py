"""Rival scouting rules: players on court producing far above their season rate."""

from __future__ import annotations

import math
from typing import Any, Dict, List

from .advice_types import Advice, RuleContext
from .profiles import DEFAULT_IMPACT_LEAGUE, IMPACT_METRICS
from .zones import DEFAULT_FAMILY_SHARE, default_family_pps, family_totals

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


# --- shot zones -------------------------------------------------------------------------

# family -> (label after "desde", tactical response)
_ZONE_TEXT = {
    "aro": ("el aro", "Proteger el aro: cerrar la penetración y el rebote."),
    "zona": ("la zona", "Proteger la pintura: ayudas y cerrar el juego interior."),
    "media distancia": ("la media distancia", "Cerrar el tiro de media distancia: no dejarle tirar tras el bote."),
    "esquina": ("las esquinas", "Cerrar las esquinas: ayuda del lado débil y salir al tirador."),
    "ala": ("las alas", "Salir al tirador en el ala y cerrar la línea de pase."),
    "centro del arco": ("el centro del arco", "Defender el tiro sobre el bloqueo y cambiar rápido."),
}
_MIN_REFERENCE_SHOTS = 20     # season shots in a family before trusting its own rate
_MIN_REFERENCE_TOTAL = 40     # season shots of the rival before trusting its shot distribution


def _expected(family: str, ctx: RuleContext, league_fam: Dict, rival_fam: Dict) -> tuple:
    """Expected (points per shot, share of shots) for the rival in a family."""
    league = league_fam.get(family)
    league_pps = (league["pts"] / league["a"]) if league and league["a"] >= _MIN_REFERENCE_SHOTS \
        else default_family_pps(family)
    rival = rival_fam.get(family)
    if rival and rival["a"]:
        n0 = ctx.config.zone_shrink_n0
        pps = (rival["pts"] + n0 * league_pps) / (rival["a"] + n0)
    else:
        pps = league_pps

    rival_total = sum(f["a"] for f in rival_fam.values())
    league_total = sum(f["a"] for f in league_fam.values())
    if rival and rival_total >= _MIN_REFERENCE_TOTAL:
        share = rival["a"] / rival_total
    elif league and league_total >= 4 * _MIN_REFERENCE_TOTAL:
        share = league["a"] / league_total
    else:
        share = DEFAULT_FAMILY_SHARE[family]
    return pps, share


def rival_zone_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    if not ctx.rival_team_id:
        return []
    live = family_totals((snap.get("zones") or {}).get(ctx.rival_team_id) or {})
    total = sum(f["a"] for f in live.values())
    if not total:
        return []
    cfg = ctx.config
    league_fam = family_totals(ctx.zone_ref.get("league", {}))
    rival_fam = family_totals(ctx.zone_ref.get("rival", {}))
    out = []
    for family, cell in sorted(live.items()):
        attempts, makes = cell["a"], cell["m"]
        pps = cell["pts"] / attempts
        expected_pps, expected_share = _expected(family, ctx, league_fam, rival_fam)
        label, response = _ZONE_TEXT[family]
        base = {"family": family, "attempts": attempts, "makes": makes, "total": total,
                "pps": round(pps, 3), "expected_pps": round(expected_pps, 3),
                "share": round(attempts / total, 3), "expected_share": round(expected_share, 3)}

        if attempts >= cfg.zone_min_attempts and makes >= cfg.zone_min_makes \
                and pps - expected_pps >= cfg.zone_pps_excess:
            out.append(Advice(
                key=f"zone:{family}:eficiencia", id="rival_zone", severity="warning", category="rival",
                message=(f"Rival castiga desde {label}: {makes}/{attempts} ({pps:.2f} pts/tiro, "
                         f"esperado {expected_pps:.2f}). {response}"),
                evidence={**base, "kind": "eficiencia"}))
        share = attempts / total
        if attempts >= cfg.zone_min_share_attempts and share >= cfg.zone_share \
                and share - expected_share >= cfg.zone_share_excess:
            out.append(Advice(
                key=f"zone:{family}:volumen", id="rival_zone", severity="info", category="rival",
                message=(f"Rival: {attempts} de sus {total} tiros ({share:.0%}) salen desde {label} "
                         f"(habitual {expected_share:.0%}). {response}"),
                evidence={**base, "kind": "volumen"}))
    return out
