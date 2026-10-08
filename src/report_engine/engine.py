"""Builds the structured report: findings -> profile -> tactics -> training / game plan."""
from typing import Any, Dict, List, Optional

from . import rules
from .zones import zone_findings
from .config import ReportConfig
from .templates import FLIP, THEMES

MODES = ("own", "rival")


def _level(stats, quartiles, key) -> Optional[int]:
    v = rules._number(stats, key)
    return None if v is None else rules.classify_quartile(v, quartiles.get(key) or {})


def _profile(stats: Dict[str, Any], quartiles: Dict[str, Any]) -> List[str]:
    lines = []
    tempo = _level(stats, quartiles, "possessions_per_game")
    if tempo == 4:
        lines.append("Ritmo alto: juega muchas posesiones por partido y busca correr.")
    elif tempo == 1:
        lines.append("Ritmo bajo: prefiere partidos de pocas posesiones y ataque estático.")
    mix = _level(stats, quartiles, "three_point_rate")
    if mix == 4:
        lines.append("Alta dependencia del triple: gran parte de sus tiros llegan desde el perímetro.")
    elif mix == 1:
        lines.append("Juego interior: lanza pocos triples y busca finalizar cerca del aro.")
    off, de = _level(stats, quartiles, "offensive_rating"), _level(stats, quartiles, "defensive_rating")
    if off is not None and de is not None:
        if off >= 3 and de <= 2:
            lines.append("Equipo equilibrado: ataque y defensa por encima de la media.")
        elif off >= 3:
            lines.append("Perfil ofensivo: su fuerza está en el ataque y concede más en defensa.")
        elif de <= 2:
            lines.append("Perfil defensivo: su fuerza está en la defensa y le cuesta anotar.")
    if _level(stats, quartiles, "offensive_rebound_rate") == 4:
        lines.append("Insiste en el rebote ofensivo para generar segundas oportunidades.")
    return lines


def _area(theme: str, mode: str) -> str:
    side = THEMES[theme]["side"]
    return side if mode == "own" else FLIP[side]


def _action(f: Dict[str, Any], mode: str) -> Dict[str, Any]:
    """One tactical action for a finding (improve/leverage for us, neutralize/exploit for a rival)."""
    t = THEMES[f["theme"]]
    if mode == "own":
        text = t["drill"] if f["kind"] == "weakness" else t["s_own"]
        kind = "improve" if f["kind"] == "weakness" else "leverage"
    else:
        text = t["neutralize"] if f["kind"] == "strength" else t["exploit"]
        kind = "neutralize" if f["kind"] == "strength" else "exploit"
    return {"key": f["key"], "label": f["label"], "area": _area(f["theme"], mode), "kind": kind, "text": text}


def _tactics(strengths, weaknesses, mode, cfg) -> List[Dict[str, Any]]:
    ranked = sorted(strengths + weaknesses, key=lambda f: -abs(f["diff_pct"] or 0.0))
    seen, out = set(), []
    for f in ranked:
        a = _action(f, mode)
        sig = (a["area"], a["text"])
        if sig not in seen:
            seen.add(sig)
            out.append(a)
    return out[: cfg.max_tactics]


def _training(strengths, weaknesses, mode, cfg) -> List[Dict[str, Any]]:
    if mode == "own":
        items = [_action(f, mode) for f in weaknesses[: cfg.max_training_items]]
    else:
        items = [_action(f, mode) for f in strengths[: cfg.max_plan_each]]
        items += [_action(f, mode) for f in weaknesses[: cfg.max_plan_each]]
    for i, item in enumerate(items, 1):
        item["priority"] = i
    return items


def build_team_report(
    team: str,
    team_stats: Dict[str, Any],
    quartiles: Dict[str, Any],
    consistency_map: Optional[Dict[str, Any]],
    mode: str = "own",
    config: Optional[ReportConfig] = None,
    zones: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Rule-based report for ``team`` (``mode``: ``own`` analysis or ``rival`` scouting).

    ``zones`` are zone rows already rated against the league (``shotcharts.zone_rating``).
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    cfg = config or ReportConfig()
    stats, quartiles = team_stats or {}, quartiles or {}
    found = rules.quartile_findings(stats, quartiles, mode)
    strengths, weaknesses = found["strength"], found["weakness"]
    games = int(stats.get("total_games") or stats.get("games_played") or 0)
    return {
        "team": team,
        "mode": mode,
        "games_played": games,
        "low_sample": games < cfg.low_sample_games,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "differentials": rules.differentials(stats, quartiles, cfg),
        "consistency": rules.consistency(consistency_map, mode, cfg),
        "zones": zone_findings(zones, mode),
        "profile": _profile(stats, quartiles),
        "tactics": _tactics(strengths, weaknesses, mode, cfg),
        "training": _training(strengths, weaknesses, mode, cfg),
    }
