"""Players on a streak and the rival's key player (issue #244).

* ``rival_player_form``: J1 a rival on a short streak (``hot_player_pts`` points in ``hot_player_window_s`` or
  ``hot_player_row`` baskets in a row: double him or change the matchup) and J2 a rival who concentrates more than
  ``dependence_share`` of his team's points (with ``dependence_min_pts``: deny him the ball).
* ``own_player_form``: J3 an own player on a streak (look for him; the fatigue rule defers its warning for him, see
  ``rules_rotation``) and J4 an own player who shoots cold with a volume above his usual (change his role or look for
  another shooter).
* ``own_orb_player`` (J8, issue #251): an own player on court with ``orb_player_min`` or more offensive rebounds and ``orb_player_excess``
  above what her minutes and her usual rate give: keep her on court (the fatigue warning of that player goes down a level too, see
  ``rules_rotation``). It is said again every ``orb_player_min`` rebounds.
* ``rival_star_bench``: V1 the rival's key player (the most production: minutes x points per 40 in the package) leaves
  the court (the moment to press) and comes back with fouls (attack him). It remembers who was on court in
  ``ctx.memory``, so it needs evaluations in order, as the engine does.

Streaks of one player are said once per player and period; thresholds are provisional, in ``RuleConfig``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .advice_types import Advice, RuleContext
from .proposals import tactic_proposal
from .windows import player_form

GAME_SECONDS = 2400
DEFAULT_ORB40 = 1.5   # the league's offensive rebounds per 40 minutes when the package has no rate for the player


def _name(p: Dict[str, Any]) -> str:
    return p["name"].strip()


def is_hot(form: Dict[str, int], cfg: Any) -> bool:
    return form["pts"] >= cfg.hot_player_pts or form["made_in_row"] >= cfg.hot_player_row


def orb_dominant(p: Dict[str, Any], base: Optional[Dict[str, Any]], cfg: Any) -> Optional[Dict[str, Any]]:
    """The offensive-rebound numbers of a player when she is clearly above her usual (J8), else None."""
    orb = (p.get("stats") or {}).get("orb", 0)
    rate = ((base or {}).get("rates") or {}).get("orb40", DEFAULT_ORB40)
    expected = rate * p["minutes"] / GAME_SECONDS
    if orb < cfg.orb_player_min or orb < expected + cfg.orb_player_excess:
        return None
    return {"orb": orb, "expected": round(expected, 1)}


def own_orb_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    out = []
    for pid, p in snap["players"].items():
        if p["team_id"] != ctx.own_team_id or not p["on_court"]:
            continue
        found = orb_dominant(p, ctx.baselines.get(pid), ctx.config)
        if found:
            out.append(Advice(
                key=f"own_orb:{pid}:{found['orb'] // ctx.config.orb_player_min}", id="own_orb_player", severity="info",
                category="four_factors",
                message=f"{_name(p)} lleva {found['orb']} rebotes ofensivos en {p['minutes'] // 60} min (esperados {found['expected']}).",
                evidence={"player_id": pid, "team_id": p["team_id"], **found},
                proposal=[tactic_proposal(f"Mantener a {_name(p)} en pista: rebote ofensivo", pid, _name(p))]))
    return out


def rival_player_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    rival = ctx.rival_team_id
    if not rival:
        return []
    cfg, log, now, period, out = ctx.config, snap.get("log", []), snap["elapsed"], snap["period"], []
    team_pts = (snap.get("score") or {}).get(rival) or 0
    for pid, p in snap["players"].items():
        if p["team_id"] != rival:
            continue
        form = player_form(log, rival, pid, now, cfg.hot_player_window_s)
        if p["on_court"] and is_hot(form, cfg):
            out.append(Advice(
                key=f"rival_hot:{pid}:{period}", id="rival_hot_run", severity="warning", category="rival",
                message=(f"Rival {_name(p)} en racha: {form['pts']} puntos en los últimos {cfg.hot_player_window_s // 60} min "
                         f"({form['made_in_row']} canastas seguidas)."),
                evidence={"player_id": pid, "team_id": rival, **form},
                proposal=[tactic_proposal(f"2x1 o cambiar el emparejamiento sobre {_name(p)}", pid, _name(p))]))
        if team_pts and p["pts"] >= cfg.dependence_min_pts and p["pts"] / team_pts > cfg.dependence_share:
            share = round(100 * p["pts"] / team_pts)
            out.append(Advice(
                key=f"rival_dependence:{pid}:{1 if period <= 2 else 2}", id="rival_dependence", severity="info", category="rival",
                message=f"Rival {_name(p)} concentra el {share} % de sus puntos ({p['pts']} de {team_pts}): negarle el balón.",
                evidence={"player_id": pid, "team_id": rival, "pts": p["pts"], "team_pts": team_pts, "share": share},
                proposal=[tactic_proposal(f"Negar el balón a {_name(p)}", pid, _name(p))]))
    return out


def _cold_volume(p: Dict[str, Any], base: Optional[Dict[str, Any]], cfg: Any) -> Optional[Dict[str, Any]]:
    """The cold shooting of the player if it is cold AND above his usual volume, else None."""
    rates = (base or {}).get("rates") or {}
    if "fg2a40" not in rates or "fg3a40" not in rates:
        return None
    stats = p.get("stats") or {}
    attempts, made = stats.get("fg2a", 0) + stats.get("fg3a", 0), stats.get("fg2m", 0) + stats.get("fg3m", 0)
    if attempts < cfg.cold_player_min_fga:
        return None
    efg = (made + 0.5 * stats.get("fg3m", 0)) / attempts
    expected = (rates["fg2a40"] + rates["fg3a40"]) * p["minutes"] / GAME_SECONDS
    if efg > cfg.cold_player_max_efg or attempts < cfg.cold_player_volume_ratio * expected:
        return None
    return {"made": made, "attempts": attempts, "expected": round(expected, 1)}


def own_player_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    cfg, log, now, period, out = ctx.config, snap.get("log", []), snap["elapsed"], snap["period"], []
    for pid, p in snap["players"].items():
        if p["team_id"] != ctx.own_team_id or not p["on_court"]:
            continue
        form = player_form(log, ctx.own_team_id, pid, now, cfg.hot_player_window_s)
        if is_hot(form, cfg):
            out.append(Advice(
                key=f"own_hot:{pid}:{period}", id="own_hot_player", severity="info", category="four_factors",
                message=f"{_name(p)} en racha: {form['pts']} puntos en los últimos {cfg.hot_player_window_s // 60} min.",
                evidence={"player_id": pid, "team_id": p["team_id"], **form},
                proposal=[tactic_proposal(f"Buscar a {_name(p)}", pid, _name(p))]))
        cold = _cold_volume(p, ctx.baselines.get(pid), cfg)
        if cold:
            out.append(Advice(
                key=f"own_cold:{pid}:{period}", id="own_cold_player", severity="info", category="four_factors",
                message=(f"{_name(p)}: {cold['made']}/{cold['attempts']} en tiros de campo con más volumen del habitual "
                         f"(esperados {cold['expected']:.0f})."),
                evidence={"player_id": pid, "team_id": p["team_id"], **cold},
                proposal=[tactic_proposal(f"Buscar otro tirador en lugar de {_name(p)}", pid, _name(p))]))
    return out


def _key_players(ctx: RuleContext) -> List[str]:
    """The rival players with the most production (average seconds x points per 40) in the package."""
    scored = [(((b.get("avg_min") or 0) * ((b.get("impact40") or {}).get("pts") or 0)), pid)
              for pid, b in ctx.rival_baselines.items()]
    return [pid for score, pid in sorted(scored, key=lambda item: (-item[0], item[1])) if score > 0][:ctx.config.rival_key_n]


def rival_star_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    if not ctx.rival_team_id:
        return []
    memory, out = ctx.memory.setdefault("rival_star", {}), []
    for pid in _key_players(ctx):
        p = snap["players"].get(pid)
        if not p or p["team_id"] != ctx.rival_team_id:
            continue
        before = memory.get(pid)
        exits = (before or {}).get("exits", 0) + (1 if before and before["on"] and not p["on_court"] else 0)
        memory[pid] = {"on": p["on_court"], "exits": exits}
        if before is None:
            continue
        if before["on"] and not p["on_court"]:
            out.append(Advice(
                key=f"star_out:{pid}:{exits}", id="rival_star_out", severity="info", category="rival",
                message=f"{_name(p)}, su jugadora clave, sale a banquillo.",
                evidence={"player_id": pid, "team_id": p["team_id"], "pf": p["pf"]},
                proposal=[tactic_proposal(f"Apretar mientras {_name(p)} descansa", pid, _name(p))]))
        elif not before["on"] and p["on_court"] and p["pf"] >= ctx.config.key_return_pf:
            out.append(Advice(
                key=f"star_back:{pid}:{exits}", id="rival_star_back", severity="warning", category="rival",
                message=f"{_name(p)}, su jugadora clave, vuelve a pista con {p['pf']} faltas: atacarla desde el primer ataque.",
                evidence={"player_id": pid, "team_id": p["team_id"], "pf": p["pf"]},
                proposal=[tactic_proposal(f"Atacar a {_name(p)}, que vuelve con {p['pf']} faltas", pid, _name(p))]))
    return out
