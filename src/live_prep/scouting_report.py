"""The rival scouting report, in words (issue #299): findings, sections and plan built from what the engine collected.

Pure functions over plain dicts (``scouting_collect.scout_team`` and, optionally, the rule-based team report in rival mode and
a comparison with our team). Thresholds live in ``ScoutingConfig``; every figure says how many games stand behind it and a
small sample is said, never dressed up. Nothing here knows a team: it is whatever the data says. Spanish, as the staff reads it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence

from src.live_core.zones import ZONES, zone_family

MAX_KEYS = 8
ORIGIN_LABELS = (("pts_off_tov", "Puntos tras pérdida rival", True), ("pts_second_chance", "Puntos de 2.ª oportunidad", True),
                 ("pts_paint", "Puntos en la pintura", True), ("pts_bench", "Puntos del banquillo", False), ("bench_pct", "% de puntos del banquillo", False))
PLAN_ENGINE_ITEMS = 3      # per side: the plan is the main findings, the full list is already above


@dataclass(frozen=True)
class ScoutingConfig:
    low_sample_games: int = 5          # fewer games than this and the report says so
    scorer_share: float = 0.28         # share of the points of one player that makes the team depend on her
    clutch_min_pts: int = 10           # points in the clutch window and share of them that make a player "the one"
    clutch_share: float = 0.40
    weak_quarter_margin: float = -2.0  # average margin of a quarter (points) that is a weakness
    weak_edge_margin: float = -1.5     # ... of the first or last three minutes of a quarter
    timeout_min_n: int = 8             # timeouts needed to say anything about what follows them
    timeout_gap: float = 1.0           # points more conceded than scored in the two minutes after
    zone_min_attempts: int = 30        # attempts of a zone needed to rate it
    zone_excess_pp: float = 8.0        # percentage points over the league that make a zone a threat or a weakness
    lineup_min_seconds: int = 600
    lineup_net40: float = 8.0
    alert_min_per_game: float = 0.5


# what the engine's alerts say about a team, in words, keyed by the id the ENGINE emits (not the rule id): label, what to do about it
# and the text of the finding when it is one (said only when it fires often enough)
ALERTS: Dict[str, Any] = {
    "own_drought": ("Sequías de anotación", "exploit", "Sufre sequías de anotación: presionar fuerte cuando se atascan"),
    "fg_drought": ("Sequías de canasta de campo", "exploit", None),
    "scoring_drought": ("Sequías de anotación", "exploit", "Sufre sequías de anotación: presionar fuerte cuando se atascan"),
    "turnover_streak": ("Rachas de pérdidas", "exploit", "Acumula rachas de pérdidas: presión sobre el balón"),
    "cold_fg_streak": ("Rachas frías de tiro de campo", "exploit", "Se enfría con facilidad en ataque: defender fuerte y no dejarle recuperar el ritmo"),
    "cold_3p_streak": ("Rachas de triples fallados", "exploit", None),
    "cold_3p_volume": ("Exceso de triples", "exploit", None),
    "ft_cold": ("Tiros libres fallados", "exploit", None),
    "own_cold_player": ("Jugadoras que no acierta con volumen", "exploit", None),
    "own_hot_player": ("Jugadoras en racha", "neutralize", None),
    "own_orb_player": ("Rebote ofensivo individual", "neutralize", None),
    "own_zone_hot": ("Zonas calientes de tiro", "neutralize", None),
    "own_zone_cold": ("Zonas frías de tiro", "exploit", None),
    "own_zone_selection": ("Mala selección de tiro", "exploit", None),
    "paint_battle": ("Pintura perdida", "exploit", "Pierde con frecuencia la batalla de la pintura: atacar el aro y cargar el rebote"),
    "static_offense": ("Ataque estático", "exploit", None),
    "fatigue_high": ("Fatiga de sus jugadoras", "exploit", None),
    "foul_trouble": ("Jugadoras con problemas de faltas", "exploit", None),
    "team_fouls_bonus": ("Entra pronto en bonus", "exploit", "Acumula faltas de equipo pronto en el periodo: atacar el aro para llegar al bonus"),
    "key_fouls_close": ("Faltas de sus clave en el cierre", "exploit", None),
    "disqualification_risk": ("Riesgo de descalificación", "exploit", None),
    "player_plus_minus": ("Jugadoras con +/- negativo en pista", "exploit", None),
    "lineup_net": ("Quintetos que rinden mal", "exploit", None),
    "rival_run": ("Parciales en contra", "exploit", "Sus rivales les hacen parciales largos: insistir cuando lleguen"),
    "long_run": ("Parciales largos en contra", "exploit", None),
    "own_run": ("Parciales a favor", "neutralize", None),
    "comeback_plan": ("Situaciones de remontada", "neutralize", None),
    "closing_briefing": ("Finales igualados", "exploit", None),
    "advantage_management": ("Gestión de las ventajas", "exploit", None),
    "period_edge_deficit": ("Finales de cuarto en negativo", "exploit", None),
    "timeout_budget": ("Gestión de los tiempos muertos", "exploit", None),
    "first_half_timeouts": ("Tiempos muertos sin usar al descanso", "exploit", None),
    "rest_starters": ("Descanso de las titulares en partido decidido", "exploit", None),
    "pace_control": ("Control del ritmo", "neutralize", None),
    "points_off_turnovers": ("Puntos del rival tras sus pérdidas", "exploit", None),
    "formation_lineup": ("Alineación indebida (jugadoras de formación)", "exploit", None),
    "four_factors_lever": ("Palanca de los Four Factors", "exploit", None),
    "win_flip": ("Caídas bruscas de su probabilidad de victoria", "exploit", None),
}


def fmt(value: float, digits: int = 1, sign: bool = False) -> str:
    """Spanish number: decimal comma; a real minus sign is not used so figures survive plain-text fonts."""
    text = f"{value:+.{digits}f}" if sign else f"{value:.{digits}f}"
    return text.replace(".", ",")


def _ordinal(n: int) -> str:
    return {1: "1.er", 2: "2.º", 3: "3.er", 4: "4.º"}.get(n, f"{n}.º")


def _pct(m: float, a: float) -> Optional[float]:
    return m / a * 100 if a else None


def _delta_pct(value: Optional[float], league: Optional[float]) -> Optional[float]:
    return (value - league) / abs(league) * 100 if value is not None and league else None


def _origin_rows(origin: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Points by origin of the team (per game), what it concedes and the league, with the gap to the league in % (#358)."""
    if not origin:
        return []
    own, conceded, league = origin.get("own", {}), origin.get("conceded", {}), origin.get("league", {})
    rows = []
    for key, label, has_conceded in ORIGIN_LABELS:
        mine, theirs, lg = own.get(key), conceded.get(key) if has_conceded else None, league.get(key)
        rows.append({"key": key, "label": label, "own": mine, "conceded": theirs, "league": lg,
                     "own_delta_pct": _delta_pct(mine, lg), "conceded_delta_pct": _delta_pct(theirs, lg)})
    return rows


def _record(games: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(games) or 1
    return {"wins": sum(1 for g in games if g["margin"] > 0), "losses": sum(1 for g in games if g["margin"] <= 0),
            "avg_for": sum(g["score_for"] for g in games) / n, "avg_against": sum(g["score_against"] for g in games) / n,
            "avg_margin": sum(g["margin"] for g in games) / n}


def _zone_rows(zones: Dict[str, Dict[str, Dict[str, int]]], cfg: ScoutingConfig) -> List[Dict[str, Any]]:
    own, conceded, league = zones.get("own", {}), zones.get("conceded", {}), zones.get("league", {})
    rows = []
    for zone in set(own) | set(conceded):
        o, c, lg = own.get(zone, {"a": 0, "m": 0}), conceded.get(zone, {"a": 0, "m": 0}), league.get(zone, {"a": 0, "m": 0})
        league_pct, own_pct, conc_pct = _pct(lg["m"], lg["a"]), _pct(o["m"], o["a"]), _pct(c["m"], c["a"])
        rows.append({
            "zone": zone, "label": ZONES.get(zone, {}).get("name", zone), "family": zone_family(zone) if zone in ZONES else zone,
            "own_fga": o["a"], "own_fg_pct": own_pct, "league_fg_pct": league_pct,
            "own_delta_pp": own_pct - league_pct if own_pct is not None and league_pct is not None else None,
            "conceded_fga": c["a"], "conceded_fg_pct": conc_pct,
            "conceded_delta_pp": conc_pct - league_pct if conc_pct is not None and league_pct is not None else None,
            "low_sample": o["a"] < cfg.zone_min_attempts})
    return sorted((r for r in rows if r["own_fga"] or r["conceded_fga"]), key=lambda r: (-r["own_fga"], r["zone"]))


def _scorer_key(data: Dict[str, Any], cfg: ScoutingConfig) -> List[Dict[str, str]]:
    top = data["players"][0] if data["players"] else None
    if not top or top["share"] < cfg.scorer_share:
        return []
    return [{"area": "jugadoras", "action": "neutralize",
             "text": f"Depende de {top['name']}: {top['share'] * 100:.0f} % de sus puntos ({fmt(top['pts_per_game'])} por partido). Limitarla es la prioridad."}]


def _clutch_key(data: Dict[str, Any], cfg: ScoutingConfig) -> List[Dict[str, str]]:
    total = sum(p["clutch"]["pts"] for p in data["players"])
    best = max(data["players"], key=lambda p: p["clutch"]["pts"], default=None)
    if not best or best["clutch"]["pts"] < cfg.clutch_min_pts or best["clutch"]["pts"] < cfg.clutch_share * total:
        return []
    c = best["clutch"]
    return [{"area": "cierres", "action": "neutralize",
             "text": f"En los finales ajustados busca a {best['name']}: {c['pts']} puntos y {c['fga']} tiros de campo en {best['games']} partidos."}]


def _quarter_keys(data: Dict[str, Any], cfg: ScoutingConfig) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    quarters = data.get("quarters", {})
    if quarters:
        period, q = min(quarters.items(), key=lambda kv: kv[1]["margin"])
        if q["margin"] <= cfg.weak_quarter_margin:
            out.append({"area": "ritmo", "action": "exploit",
                        "text": f"Su peor cuarto es el {_ordinal(int(period))} cuarto: {fmt(q['margin'])} de media ({fmt(q['for'])} a favor, {fmt(q['against'])} en contra)."})
    for edge, verb in (("start", "empieza mal"), ("close", "cierra mal")):
        values = data.get("edges", {}).get(edge, {})
        if values:
            period, margin = min(values.items(), key=lambda kv: kv[1])
            if margin <= cfg.weak_edge_margin:
                where = "los 3 primeros minutos" if edge == "start" else "los 3 últimos minutos"
                out.append({"area": "ritmo", "action": "exploit",
                            "text": f"{_ordinal(int(period))} cuarto: {verb} ({fmt(margin)} de media en {where}). Apretar en ese tramo."})
    return out


def _timeout_key(data: Dict[str, Any], cfg: ScoutingConfig) -> List[Dict[str, str]]:
    t = data.get("timeouts", {})
    if t.get("after_n", 0) >= cfg.timeout_min_n and t["after_against"] - t["after_for"] >= cfg.timeout_gap:
        return [{"area": "gestión", "action": "exploit",
                 "text": f"Tras cada tiempo muerto suyo anotan {fmt(t['after_for'])} y reciben {fmt(t['after_against'])} de media en los 2 minutos siguientes ({t['after_n']} tiempos muertos): atacar justo después."}]
    return []


def _zone_keys(rows: List[Dict[str, Any]], cfg: ScoutingConfig) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    weak = [r for r in rows if r["conceded_fga"] >= cfg.zone_min_attempts and (r["conceded_delta_pp"] or 0) >= cfg.zone_excess_pp]
    if weak:
        r = max(weak, key=lambda r: r["conceded_delta_pp"])
        out.append({"area": "defensa", "action": "exploit",
                    "text": f"Defiende mal {r['label']}: concede {r['conceded_fg_pct']:.0f} % (liga {r['league_fg_pct']:.0f} %, {r['conceded_fga']} tiros). Atacarla ahí."})
    strong = [r for r in rows if r["own_fga"] >= cfg.zone_min_attempts and (r["own_delta_pp"] or 0) >= cfg.zone_excess_pp]
    if strong:
        r = max(strong, key=lambda r: r["own_delta_pp"])
        out.append({"area": "ataque", "action": "neutralize",
                    "text": f"Es peligroso desde {r['label']}: {r['own_fg_pct']:.0f} % (liga {r['league_fg_pct']:.0f} %, {r['own_fga']} tiros). No dejarle tirar cómodo."})
    return out


def _alert_rows(data: Dict[str, Any], cfg: ScoutingConfig) -> List[Dict[str, Any]]:
    rows = []
    for a in data.get("alerts", []):
        label = ALERTS.get(a["id"], (f"Alerta «{a['id'].replace('_', ' ')}»", "exploit", None))[0]
        rows.append({"id": a["id"], "label": label, "per_game": a["per_game"], "avg_minute": a["avg_minute"], "games": a["games"],
                     "count": a["count"], "text": f"{label}: {fmt(a['per_game'])} por partido (en {a['games']} partidos, hacia el minuto {a['avg_minute']:.0f})."})
    return rows


def _alert_keys(data: Dict[str, Any], cfg: ScoutingConfig) -> List[Dict[str, str]]:
    out = []
    for a in data.get("alerts", []):
        _, action, text = ALERTS.get(a["id"], (None, "exploit", None))
        if text and a["per_game"] >= cfg.alert_min_per_game:
            out.append({"area": "gestión", "action": action, "text": f"{text} ({fmt(a['per_game'])} por partido)."})
    return out


def _lineup_rows(data: Dict[str, Any], cfg: ScoutingConfig) -> List[Dict[str, Any]]:
    rows = []
    for row in data.get("lineups", []):
        minutes = row["seconds"] / 60
        names = ", ".join(row["players"])
        tag = ""
        if row["seconds"] >= cfg.lineup_min_seconds:
            tag = " Rinde muy bien." if row["net40"] >= cfg.lineup_net40 else " Rinde mal." if row["net40"] <= -cfg.lineup_net40 else ""
        rows.append({**row, "minutes": minutes, "text": f"{names}: {fmt(minutes, 0)} min en {row['games']} partidos, {fmt(row['net40'], 1, True)} por 40'.{tag}"})
    return rows


def _plan(keys: List[Dict[str, str]], team_report: Optional[Dict[str, Any]]) -> Dict[str, List[Dict[str, str]]]:
    plan: Dict[str, List[Dict[str, str]]] = {"neutralize": [], "exploit": []}
    seen = set()
    for item in sorted((team_report or {}).get("training", []), key=lambda t: t.get("priority", 99)):
        if item.get("kind") in plan and item["text"] not in seen:
            plan[item["kind"]].append({"text": item["text"], "source": "informe"})
            seen.add(item["text"])
    taken = {side: 0 for side in plan}
    for key in keys:
        if key["text"] not in seen and taken[key["action"]] < PLAN_ENGINE_ITEMS:
            plan[key["action"]].append({"text": key["text"], "source": "motor"})
            taken[key["action"]] += 1
    return plan


def build_scouting_report(data: Dict[str, Any], team_report: Optional[Dict[str, Any]] = None,
                          comparison: Optional[Sequence[Dict[str, Any]]] = None, config: Optional[ScoutingConfig] = None) -> Dict[str, Any]:
    """The report of the team in ``data`` (``scout_team`` output), with the rule-based team report and a comparison when there are."""
    cfg = config or ScoutingConfig()
    n = data["sample_games"]
    zones = _zone_rows(data.get("zones", {}), cfg)
    findings: List[Callable[[], List[Dict[str, str]]]] = [
        lambda: _scorer_key(data, cfg), lambda: _clutch_key(data, cfg), lambda: _quarter_keys(data, cfg), lambda: _timeout_key(data, cfg),
        lambda: _zone_keys(zones, cfg), lambda: _alert_keys(data, cfg)]
    low = n < cfg.low_sample_games
    keys = [k for f in findings for k in f()][:MAX_KEYS]
    if low:      # a finding from two games is a hint, and it says so
        keys = [{**k, "text": f"{k['text']} (solo {n} partidos)"} for k in keys]
    notices = [f"Muestra pequeña: solo {n} partidos con jugada a jugada detrás de estos datos; son orientativos."] if low else []
    return {
        "team": data["team"], "sample_games": n, "low_sample": low, "notices": notices,
        "record": _record(data["games"]), "games": data["games"], "factors": data.get("factors"), "pace": data.get("pace"),
        "profile": [f"Ritmo medio: {fmt(data['pace'])} posesiones por 40 minutos."] + list((team_report or {}).get("profile", [])) if data.get("pace") else list((team_report or {}).get("profile", [])),
        "keys": keys, "players": data["players"][:6], "lineups": _lineup_rows(data, cfg), "zones": zones,
        "quarters": data.get("quarters", {}), "edges": data.get("edges", {}), "timeouts": data.get("timeouts", {}),
        "origin": _origin_rows(data.get("origin")),
        "alerts": _alert_rows(data, cfg), "plan": _plan(keys, team_report),
        "team_report": {k: (team_report or {}).get(k, []) for k in ("strengths", "weaknesses", "differentials", "tactics")},
        "comparison": list(comparison or []),
    }
