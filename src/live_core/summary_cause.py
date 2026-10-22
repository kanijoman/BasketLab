"""Two keys of the summary of a quarter that EXPLAIN instead of describing (issues #485, #487).

* ``cause_key``: the lead (or the deficit) of the period is explained by the Four Factors that are out of range, those of both teams measured in the
  period against what is usual for the matchup (``four_factors_prior`` of the package) with the spread of a single game scaled to the length of the
  window. Only the factors that go the same way as the result count. With a lead (or a deficit) and nothing out of range it says so.
* ``fouls_key``: «Faltas de equipo» says whose they are, the free throws they gave and the players in foul trouble.

Standard library only; thresholds provisional, in ``RuleConfig``.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from .four_factors import DEFAULT_SD, FT_POSSESSION_COST, GAME_SECONDS

Key = Optional[Tuple[str, str]]

# factor -> (label with a lead, label with a deficit, adjustment with a lead, adjustment with a deficit)
_TEXT = {
    "efg": ("Ventaja por el tiro", "Desventaja por el tiro", "Seguir buscando tiros de calidad", "Mejorar la selección de tiro"),
    "tov": ("Ventaja por las pérdidas", "Desventaja por las pérdidas", "Seguir presionando la salida de balón", "Asegurar el balón en la salida de pista"),
    "ftr": ("Ventaja desde la línea", "Desventaja desde la línea", "Seguir atacando el aro para ir a la línea", "Atacar el aro: ir a la línea de tiros libres"),
}


def _rates(own: Dict[str, Any], rival: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """eFG%, turnover rate and free-throw rate of both teams in the window (the rival's rates are its own)."""
    out = {}
    for name, s in (("own", own), ("rival", rival)):
        fga = s["fg2"][1] + s["fg3"][1]
        out[name] = {"efg": (s["fg2"][0] + 1.5 * s["fg3"][0]) / fga if fga else 0.0, "fga": fga,
                     "tov": s["tov"] / (fga + FT_POSSESSION_COST * s["ft"][1] + s["tov"]) if fga + s["ft"][1] + s["tov"] else 0.0,
                     "ftr": s["ft"][1] / fga if fga else 0.0, "tov_n": s["tov"], "fta": s["ft"][1]}
    return out


def _gaps(rates: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    """Own minus rival per factor, positive = good for us (turnovers inverted, as ``four_factors.differentials``)."""
    own, rival = rates["own"], rates["rival"]
    return {"efg": own["efg"] - rival["efg"], "tov": rival["tov"] - own["tov"], "ftr": own["ftr"] - rival["ftr"]}


def _describe(factor: str, rates: Dict[str, Dict[str, float]]) -> str:
    own, rival = rates["own"], rates["rival"]
    if factor == "efg":
        return f"{own['efg'] * 100:.0f} % de campo vs {rival['efg'] * 100:.0f} % del rival"
    if factor == "tov":
        return f"pérdidas del rival: {rival['tov_n']} vs {own['tov_n']}" if rival["tov_n"] >= own["tov_n"] else f"pérdidas propias: {own['tov_n']} vs {rival['tov_n']}"
    return f"tiros libres intentados: {own['fta']} vs {rival['fta']}"


def cause_key(f: Dict[str, Any], clear: bool = True) -> Key:
    """The factor that explains the result (``clear``), or, with ``clear=False``, the statement that nothing out of range explains it."""
    cfg, net = f["cfg"], f["own"]["pts"] - f["rival"]["pts"]
    if abs(net) < cfg.summary_cause_net:
        return None
    rates = _rates(f["own"], f["rival"])
    if min(rates["own"]["fga"], rates["rival"]["fga"]) < cfg.summary_cause_min_fga:
        return None
    base = f.get("baselines") or {}
    prior, sd = base.get("four_factors_prior") or {}, {**DEFAULT_SD, **(base.get("four_factors_sd") or {})}
    scale = math.sqrt(GAME_SECONDS / max(f["window_s"], 1))        # a quarter says less than a game: its spread is wider
    sign = 1 if net > 0 else -1
    zs = {k: (gap - prior.get(k, 0.0)) / (sd[k] * scale) for k, gap in _gaps(rates).items()}
    best = max(zs, key=lambda k: sign * zs[k])
    if sign * zs[best] < cfg.summary_cause_z:
        if clear:
            return None
        return f"{'Ventaja' if net > 0 else 'Desventaja'} sin causa clara en los Four Factors ({net:+d})", (
            "No relajarse: la ventaja no tiene una causa clara en el juego" if net > 0 else "Buscar qué falla: nada explica la desventaja en los números")
    if not clear:
        return None
    lead, deficit, keep, fix = _TEXT[best]
    return f"{lead if net > 0 else deficit}: {_describe(best, rates)}", keep if net > 0 else fix


def fouls_key(f: Dict[str, Any]) -> Key:
    cfg = f["cfg"]
    if f["fouls"] < cfg.summary_fouls:
        return None
    text = f"Faltas propias: {f['fouls']} (el rival lanzó {f['rival']['ft'][1]} tiros libres) frente a {f['rival_fouls']} del rival"
    trouble: List[Dict[str, Any]] = f["trouble"]
    if trouble:
        text += "; con problemas: " + ", ".join(f"{t['name']} ({t['pf']})" for t in trouble)
        return text, f"Rotar a {trouble[0]['name']} y defender sin falta"
    return text, "Defender sin falta"
