"""The finish and the pace (issue #246): C1, C4 and G1.

* C1 ``closing_briefing`` (with the clutch players of K2, issue #275): a close finish (``game_context``: 4:00 or less, margin within 6, or overtime) gets ONE briefing per
  period: the timeouts that are left (own and rival), the team fouls of the period, our poor free throws of the day (T5 is
  integrated here) and, with the package's free-throw percentages (``ft_pct`` shrunk to the league mean), the best free-throw
  shooters on court and who to foul. K2: the two rival players on court who take most responsibility in a close finish (labelled
  "eficaz" only if their shrunk accuracy is above their season's) and the own players to look for (the effective ones first). The
  clutch data comes from the package (``clutch``, see ``clutch.py``); with a small sample it says so (4th-period usage). Without
  any of that data it leaves those parts out.
* C4 ``advantage_management``: ``advantage_margin`` points up with less than ``advantage_remaining_s`` left of the 4th period:
  spend clock, do not concede threes, avoid fouls.
* C2 ``comeback_plan`` (issue #253): ``comeback_margin`` (8) or more down in the last ``comeback_left_s`` (10:00) of the game: how many
  possessions each team has left at the current pace and how many net points per possession the comeback takes, against what we do.
  Provisional until the win-probability model (epic #261) gives a calibrated projection.
* G1 ``pace_control`` (#401): only in the last ``pace_max_left_s`` (6:00): the pace lever of the win probability (estimated possessions left,
  estimated net rating and the score) says to lower the pace when ahead (avoid the flip) or raise it when behind, if it is worth at
  least ``pace_min_gain`` of probability (``WinProbabilityModel.levers``).

Thresholds are provisional, in ``RuleConfig``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .advice_types import Advice, RuleContext
from .clock import game_seconds_left
from .game_context import game_phase
from .proposals import tactic_proposal, timeout_proposal
from .rules_winflip import pace_reason_text
from .timeouts import timeouts_left

LAST_PERIOD = 4
GAME_SECONDS = 2400


def _clock(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def _times(n: int) -> str:
    return f"{n} tiempo muerto" if n == 1 else f"{n} tiempos muertos"


def _ranked(snap: Dict[str, Any], team_id: str, table: Dict[str, Dict[str, Any]], best: bool) -> List[Dict[str, Any]]:
    """The two players of ``team_id`` on court with the best (or worst) free-throw percentage in the package."""
    found = [(table[pid]["ft_pct"], pid, p["name"].strip()) for pid, p in snap["players"].items()
             if p["team_id"] == team_id and p["on_court"] and (table.get(pid) or {}).get("ft_pct") is not None]
    found.sort(key=lambda t: (-t[0], t[1]) if best else (t[0], t[1]))
    return [{"player_id": pid, "name": name, "ft_pct": round(100 * pct)} for pct, pid, name in found[:2]]


def _clutch_players(snap: Dict[str, Any], team_id: Optional[str], table: Dict[str, Dict[str, Any]], effective_first: bool) -> List[Dict[str, Any]]:
    """The two players of ``team_id`` on court with most clutch responsibility in the package (the effective ones first if asked)."""
    found = []
    for pid, p in snap["players"].items():
        data = (table.get(pid) or {}).get("clutch") or {}
        if p["team_id"] == team_id and p["on_court"] and data.get("basis") in ("clutch", "q4"):
            found.append((bool(data["effective"]) if effective_first else False, data["usage"], pid, p["name"].strip(), data))
    found.sort(key=lambda t: (-t[0], -t[1], t[2]))
    return [{"player_id": pid, "name": name, "usage": usage, "effective": bool(d["effective"]), "sample": d["sample"]}
            for _, usage, pid, name, d in found[:2]]


def _clutch_label(entry: Dict[str, Any]) -> str:
    tags = (["eficaz"] if entry["effective"] else []) + (["muestra pequeña"] if entry["sample"] == "small" else [])
    return entry["name"] + (f" ({', '.join(tags)})" if tags else "")


def _own_free_throws(snap: Dict[str, Any], ctx: RuleContext) -> Optional[str]:
    """Our free throws of the day when they are poor (T5 integrated in the briefing), else None."""
    made = sum((p.get("stats") or {}).get("ftm", 0) for p in snap["players"].values() if p["team_id"] == ctx.own_team_id)
    attempts = sum((p.get("stats") or {}).get("fta", 0) for p in snap["players"].values() if p["team_id"] == ctx.own_team_id)
    if attempts >= ctx.config.ft_cold_min_attempts and made / attempts <= ctx.config.ft_cold_max_pct:
        return f"tiros libres propios hoy {made}/{attempts}: el balón a quien los mete"
    return None


def _ft_reminder(snap: Dict[str, Any], ctx: RuleContext, context: Dict[str, Any], shooters: List[Dict[str, Any]],
                 targets: List[Dict[str, Any]]) -> List[Advice]:
    """The free-throw part of the briefing, kept alive during the whole close finish (#489): the briefing is said once per period (at 4:00) and the
    shooters on court and who to foul change; it comes again every ``closing_ft_every_s`` and at once when who is on court changes."""
    if not (shooters or targets):
        return []
    parts = []
    if shooters:
        parts.append("balón a " + ", ".join(f"{s['name']} ({s['ft_pct']} %)" for s in shooters))
    if targets:
        parts.append("hacer falta a " + ", ".join(f"{t['name']} ({t['ft_pct']} %)" for t in targets))
    who = "-".join(s["player_id"] for s in shooters) + "/" + "-".join(t["player_id"] for t in targets)
    every = max(1, ctx.config.closing_ft_every_s)
    return [Advice(
        key=f"closing_ft:{snap['period']}:{snap['remaining'] // every}:{who}", id="closing_ft_reminder", severity="info", category="gestion",
        message=f"Tiros libres en el cierre ({context['margin']:+d} a {_clock(context['remaining_s'])}): " + "; ".join(parts) + ".",
        evidence={"margin": context["margin"], "shooters": shooters, "foul_targets": targets},
        proposal=([tactic_proposal(f"Balón a {' y '.join(s['name'] for s in shooters)} (tiros libres)")] if shooters else []) + (
            [tactic_proposal(f"Hacer falta a {targets[0]['name']} ({targets[0]['ft_pct']} % en tiros libres)", targets[0]["player_id"], targets[0]["name"])] if targets else []))]


def closing_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    cfg = ctx.config
    if not cfg.enabled("game_context"):
        return []
    context = game_phase(snap, ctx.own_team_id, ctx.rival_team_id, cfg)
    if context["phase"] != "close_late":
        return []
    own_left = timeouts_left(snap, ctx.own_team_id)
    rival_left = timeouts_left(snap, ctx.rival_team_id) if ctx.rival_team_id else None
    fouls = {tid: ((snap["teams"].get(tid) or {}).get("fouls_by_period") or {}).get(str(snap["period"]), 0)
             for tid in (ctx.own_team_id, ctx.rival_team_id) if tid}
    parts = [f"quedan {_times(own_left)}" + (f" (rival {rival_left})" if rival_left is not None else "")]
    if fouls:
        parts.append(f"faltas de equipo en el periodo: {fouls.get(ctx.own_team_id, 0)} propias y {fouls.get(ctx.rival_team_id, 0)} del rival")
    poor = _own_free_throws(snap, ctx)
    if poor:
        parts.append(poor)
    shooters = _ranked(snap, ctx.own_team_id, ctx.baselines, best=True)
    targets = _ranked(snap, ctx.rival_team_id, ctx.rival_baselines, best=False) if ctx.rival_team_id else []
    proposal: List[Dict[str, Any]] = [timeout_proposal(own_left)] if own_left > 0 else []
    if shooters:
        names = ", ".join(f"{s['name']} ({s['ft_pct']} %)" for s in shooters)
        parts.append(f"buenos tiradores de tiros libres en pista: {names}")
        proposal.append(tactic_proposal(f"Balón a {' y '.join(s['name'] for s in shooters)} (tiros libres)"))
    if targets:
        parts.append("hacer falta a: " + ", ".join(f"{t['name']} ({t['ft_pct']} %)" for t in targets))
        proposal.append(tactic_proposal(f"Hacer falta a {targets[0]['name']} ({targets[0]['ft_pct']} % en tiros libres)",
                                        targets[0]["player_id"], targets[0]["name"]))
    rival_clutch = _clutch_players(snap, ctx.rival_team_id, ctx.rival_baselines, effective_first=False) if ctx.rival_team_id else []
    own_clutch = _clutch_players(snap, ctx.own_team_id, ctx.baselines, effective_first=True)
    if rival_clutch:
        parts.append("las que más asumen en el cierre: " + ", ".join(_clutch_label(r) for r in rival_clutch))
        proposal.append(tactic_proposal("Vigilar a " + " y ".join(r["name"] for r in rival_clutch) + " en el cierre"))
    if own_clutch:
        parts.append("las propias que más asumen en el cierre: " + ", ".join(_clutch_label(o) for o in own_clutch))
        proposal.append(tactic_proposal("Buscar a " + " y ".join(o["name"] for o in own_clutch) + " en el cierre"))
    reminder = _ft_reminder(snap, ctx, context, shooters, targets)
    return [*reminder, Advice(
        key=f"closing:{snap['period']}", id="closing_briefing", severity="warning", category="gestion",
        message=f"Cierre igualado ({context['margin']:+d} a {_clock(context['remaining_s'])}): " + "; ".join(parts) + ".",
        evidence={"margin": context["margin"], "own_timeouts": own_left, "rival_timeouts": rival_left, "fouls": fouls,
                  "shooters": shooters, "foul_targets": targets, "rival_clutch": rival_clutch, "own_clutch": own_clutch},
        proposal=proposal)]


def advantage_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    cfg, score, rival = ctx.config, snap.get("score") or {}, ctx.rival_team_id
    if snap["period"] != LAST_PERIOD or snap["remaining"] >= cfg.advantage_remaining_s or not rival:
        return []
    if rival not in score or ctx.own_team_id not in score:
        return []
    margin = score[ctx.own_team_id] - score[rival]
    if margin < cfg.advantage_margin:
        return []
    return [Advice(
        key=f"advantage:{LAST_PERIOD}", id="advantage_management", severity="info", category="gestion",
        message=f"Gestión de ventaja (+{margin} a {_clock(snap['remaining'])}).",
        evidence={"margin": margin, "remaining_s": snap["remaining"]},
        proposal=[tactic_proposal("Gastar reloj en cada ataque"), tactic_proposal("No conceder triples: defender el perímetro"),
                  tactic_proposal("Evitar faltas innecesarias")])]


def pace_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    """G1: in the last minutes the pace is advised from the score, the possessions left and the estimated net rating (#401).

    It uses the pace lever of the win probability: ahead, fewer possessions cut the rival's chances of a flip; behind, more
    possessions are the way back. Never earlier than ``pace_max_left_s`` from the end (before that it is speculation).
    """
    cfg, model, score = ctx.config, ctx.win_prob, snap.get("score") or {}
    if model is None or ctx.model is None or ctx.own_team_id not in score or ctx.rival_team_id not in score:
        return []
    if game_seconds_left(snap["period"], snap["remaining"]) > cfg.pace_max_left_s:
        return []
    four_factors = ctx.model.evaluate(snap)
    lever = next((r for r in model.levers(snap, four_factors) if r["id"] == "pace" and r["gain"] >= cfg.pace_min_gain), None)
    current = model.evaluate(snap, four_factors)
    if lever is None or current is None:
        return []
    direction, margin = lever["direction"], score[ctx.own_team_id] - score[ctx.rival_team_id]
    verb = "subir" if direction == "up" else "bajar"
    goal = "forzar la remontada" if direction == "up" else "evitar el vuelco"
    why = pace_reason_text(lever)       # when the pace of the last minutes decided it (#488): who it favoured
    if why:
        goal = ("seguir con el ritmo que nos favorece" if lever["reason"]["kind"] == "benefit" else "salir del ritmo que nos perjudica") + f" ({why})"
    return [Advice(
        key=f"pace:{direction}:{snap['period']}", id="pace_control", severity="info", category="gestion",
        message=(f"Quedan unas {current['poss_remaining']:.0f} posesiones por equipo con el marcador {margin:+d} (proyección "
                 f"{current['projected_margin']:+.0f}): {verb} el ritmo para {goal} (+{lever['gain'] * 100:.0f} % de victoria, experimental)."),
        evidence={"direction": direction, "margin": margin, "poss_remaining": current["poss_remaining"], "p": current["p"],
                  "projected_margin": current["projected_margin"], "gain": lever["gain"], "gain_pts": lever["gain_pts"],
                  **({"reason": lever["reason"]} if lever.get("reason") else {})},
        proposal=[tactic_proposal(f"{verb.capitalize()} el ritmo: " + ("correr más, transición rápida" if direction == "up"
                                                                         else "atacar más tiempo y cuidar cada posesión"))])]


def comeback_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    cfg, score, rival = ctx.config, snap.get("score") or {}, ctx.rival_team_id
    if ctx.pace is None or not rival or rival not in score or ctx.own_team_id not in score or snap["period"] != LAST_PERIOD:
        return []
    deficit = score[rival] - score[ctx.own_team_id]
    left = max(0, snap["remaining"])
    if deficit < cfg.comeback_margin or not 0 < left <= cfg.comeback_left_s:
        return []
    pace = ctx.pace.evaluate(snap)
    if not pace or not pace["reliable"] or not pace["possessions"]:
        return []
    possessions_left = pace["current40"] * left / GAME_SECONDS
    if possessions_left <= 0:
        return []
    need, now = deficit / possessions_left, -deficit / pace["possessions"]
    if need > cfg.comeback_max_need:
        return []            # an impossible comeback is not advice
    hard = need >= cfg.comeback_hard
    reading = "Hace falta mucho más que el ritmo normal." if hard else "Es posible a ritmo normal."
    return [Advice(
        key=f"comeback:{left // 240}", id="comeback_plan", severity="info", category="gestion",
        message=(f"Remontada: perdemos por {deficit} con unas {possessions_left:.0f} posesiones por equipo: hace falta ganar "
                 f"{need:+.2f} netos por posesión (hoy {now:+.2f}). {reading}"),
        evidence={"deficit": deficit, "possessions_left": round(possessions_left, 1), "need": round(need, 3), "now": round(now, 3)},
        proposal=[tactic_proposal("Buscar posesiones extra: presión, rebote ofensivo y faltas tácticas" if hard
                                  else "Mantener el ritmo y no perder balones")])]
