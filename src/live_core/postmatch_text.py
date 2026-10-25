"""The Spanish texts of the post-match report (issue #409): why a run happened, and what went well and what could be better.

Rule-based, no model: each sentence comes from a number of the game and says it. Thresholds are provisional.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

from .config import RuleConfig
from .windows import run_causes, scores_after_timeouts

FACTOR_GAP = 0.03          # a Four Factors difference of this size (3 points of the rate) is worth saying
PERIOD_NET = 5             # a quarter won or lost by this much
LINEUP_NET = 4             # a lineup with this plus/minus
FT_COLD = 0.60
FT_MIN_ATT = 8
_FACTOR = {"efg": "Acierto de tiro", "tov": "Pérdidas", "orb": "Rebote ofensivo", "ftr": "Tiros libres"}
_LOWER_IS_BETTER = {"tov"}


def _pct(value: float) -> str:
    return f"{value * 100:.0f} %"


def _join(items: Sequence[str]) -> str:
    return ", ".join(items[:-1]) + (" y " if len(items) > 1 else "") + items[-1] if items else ""


def _own_run_reasons(own: Dict[str, Any], rival: Dict[str, Any]) -> List[str]:
    found = []
    if rival["tov"] >= 2:
        found.append(f"{rival['tov']} pérdidas del rival")
    if own["orb"] >= 2:
        found.append(f"{own['orb']} rebotes ofensivos propios")
    if own["fg3"][0] >= 2:
        found.append(f"{own['fg3'][0]} triples")
    if own["ft"][1] >= 4:
        found.append(f"{own['ft'][1]} tiros libres")
    fga = own["fg2"][1] + own["fg3"][1]
    if fga >= 4 and (own["fg2"][0] + own["fg3"][0]) / fga >= 0.6:
        found.append(f"tiro propio {own['fg2'][0] + own['fg3'][0]}/{fga}")
    return found


def explain_run(own_run: bool, own: Dict[str, Any], rival: Dict[str, Any], names: Dict[str, str], entered: Sequence[str],
                left: Sequence[str], timeout_before: bool, config: RuleConfig) -> str:
    """One paragraph: the numbers of the stretch, the change of players just before it and whether a timeout preceded it."""
    parts = []
    if own_run:
        reasons = _own_run_reasons(own, rival)
        parts.append("Claves: " + _join(reasons) + "." if reasons else "Sin una causa clara en las estadísticas: puntos con acierto.")
    else:
        causes = [c["text"] for c in run_causes(own, rival, names, config)]
        parts.append("Claves: " + _join(causes) + "." if causes else "Sin una causa clara en las estadísticas: acierto del rival.")
    if entered or left:
        parts.append(("Entraron " + _join(entered) if entered else "") + (" y salieron " if entered and left else "")
                     + (("Salieron " if not entered else "") + _join(left) if left else "") + " en los 2 minutos previos.")
    if timeout_before:
        parts.append("Llegó después de un tiempo muerto propio.")
    return " ".join(parts)


def _factor_lines(report: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    well: List[str] = []
    improve: List[str] = []
    own, rival = report["four_factors"]["own"], report["four_factors"]["rival"]
    for key, label in _FACTOR.items():
        diff = own[key] - rival[key]
        better = -diff if key in _LOWER_IS_BETTER else diff
        if abs(better) >= FACTOR_GAP:
            text = f"{label}: {_pct(own[key])} frente a {_pct(rival[key])} del rival."
            (well if better > 0 else improve).append(text)
    return well, improve


def _period_lines(report: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    periods = report["match"]["periods"]
    well = [f"{p['label']} ganado {p['own']}-{p['rival']} ({p['net']:+d})." for p in periods if p["net"] >= PERIOD_NET]
    improve = [f"{p['label']} perdido {p['own']}-{p['rival']} ({p['net']:+d})." for p in periods if p["net"] <= -PERIOD_NET]
    return well, improve


def _run_lines(report: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    mine = [r for r in report["runs"] if r["team"] == "own"]
    theirs = [r for r in report["runs"] if r["team"] == "rival"]
    well, improve = [], []
    if mine and len(mine) >= len(theirs):
        well.append(f"{len(mine)} parciales propios de 8 o más puntos (el mayor, {max(r['pts'] for r in mine)}-0) frente a {len(theirs)} del rival.")
    if theirs and len(theirs) > len(mine):
        improve.append(f"El rival firmó {len(theirs)} parciales de 8 o más puntos (el mayor, 0-{max(r['pts'] for r in theirs)}) y nosotros {len(mine)}.")
    return well, improve


def _lineup_lines(report: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    best, worst = report["lineups"]["best"], report["lineups"]["worst"]
    well = [f"Mejor quinteto: {_join(best[0]['players'])} ({best[0]['net']:+d} en {best[0]['seconds'] // 60} min)."] \
        if best and best[0]["net"] >= LINEUP_NET else []
    improve = [f"Quinteto con peor balance: {_join(worst[0]['players'])} ({worst[0]['net']:+d} en {worst[0]['seconds'] // 60} min)."] \
        if worst and worst[0]["net"] <= -LINEUP_NET else []
    return well, improve


def _shooting_lines(report: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    stats = report["team"]["own"]["stats"]
    improve = []
    if stats["fta"] >= FT_MIN_ATT and stats["ftm"] / stats["fta"] < FT_COLD:
        improve.append(f"Tiros libres: {stats['ftm']}/{stats['fta']}.")
    own_rating, rival_rating = report["team"]["own"]["rating"], report["team"]["rival"]["rating"]
    well = [f"Mejor rating ofensivo que el rival: {own_rating:.0f} frente a {rival_rating:.0f} puntos por 100 posesiones."] \
        if own_rating - rival_rating >= 5 else []
    if rival_rating - own_rating >= 5:
        improve.append(f"Peor rating que el rival: {own_rating:.0f} frente a {rival_rating:.0f} puntos por 100 posesiones.")
    return well, improve


def _timeout_lines(snap: Dict[str, Any], own: str) -> Tuple[List[str], List[str]]:
    counted, followed = scores_after_timeouts(snap["log"], own, 120, snap["elapsed"])
    if counted < 2:
        return [], []
    if followed / counted >= 0.5:
        return [f"{followed} de {counted} tiempos muertos propios se siguieron de canasta en los 2 minutos posteriores."], []
    return [], [f"Solo {followed} de {counted} tiempos muertos propios se siguieron de canasta en los 2 minutos posteriores."]


def strengths_and_weaknesses(report: Dict[str, Any], snap: Dict[str, Any], own: str, rival: str) -> Tuple[List[str], List[str]]:
    """What went well and what could be better, each a sentence with its numbers."""
    well: List[str] = []
    improve: List[str] = []
    for lines in (_factor_lines(report), _period_lines(report), _run_lines(report), _lineup_lines(report),
                  _shooting_lines(report), _timeout_lines(snap, own)):
        well += lines[0]
        improve += lines[1]
    return well or ["Sin aspectos destacados por encima de los umbrales."], improve or ["Sin aspectos a mejorar por encima de los umbrales."]
