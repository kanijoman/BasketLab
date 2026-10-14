"""The finish and the pace (issue #246): C1, C4 and G1.

* C1 ``closing_briefing``: a close finish (``game_context``: 4:00 or less, margin within 6, or overtime) gets ONE briefing per
  period: the timeouts that are left (own and rival), the team fouls of the period, our poor free throws of the day (T5 is
  integrated here) and, with the package's free-throw percentages (``ft_pct`` shrunk to the league mean), the best free-throw
  shooters on court and who to foul. Without that data it leaves those parts out.
* C4 ``advantage_management``: ``advantage_margin`` points up with less than ``advantage_remaining_s`` left of the 4th period:
  spend clock, do not concede threes, avoid fouls.
* G1 ``pace_control``: the game is being played at the pace of the rival (closer to its habitual one than to ours, habits that
  differ by ``pace_gap`` possessions per 40) and we lose by ``pace_losing_margin`` or more: raise the pace if the rival slows the
  game down, lower it if it speeds it up (``PaceModel``).

Thresholds are provisional, in ``RuleConfig``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .advice_types import Advice, RuleContext
from .game_context import game_phase
from .proposals import tactic_proposal, timeout_proposal
from .timeouts import timeouts_left

LAST_PERIOD = 4


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


def _own_free_throws(snap: Dict[str, Any], ctx: RuleContext) -> Optional[str]:
    """Our free throws of the day when they are poor (T5 integrated in the briefing), else None."""
    made = sum((p.get("stats") or {}).get("ftm", 0) for p in snap["players"].values() if p["team_id"] == ctx.own_team_id)
    attempts = sum((p.get("stats") or {}).get("fta", 0) for p in snap["players"].values() if p["team_id"] == ctx.own_team_id)
    if attempts >= ctx.config.ft_cold_min_attempts and made / attempts <= ctx.config.ft_cold_max_pct:
        return f"tiros libres propios hoy {made}/{attempts}: el balón a quien los mete"
    return None


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
    return [Advice(
        key=f"closing:{snap['period']}", id="closing_briefing", severity="warning", category="gestion",
        message=f"Cierre igualado ({context['margin']:+d} a {_clock(context['remaining_s'])}): " + "; ".join(parts) + ".",
        evidence={"margin": context["margin"], "own_timeouts": own_left, "rival_timeouts": rival_left, "fouls": fouls,
                  "shooters": shooters, "foul_targets": targets},
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
        message=f"Gestión de ventaja (+{margin} a {_clock(snap['remaining'])}): gastar reloj, no conceder triples y evitar faltas.",
        evidence={"margin": margin, "remaining_s": snap["remaining"]},
        proposal=[tactic_proposal("Gastar reloj en cada ataque"), tactic_proposal("No conceder triples: defender el perímetro"),
                  tactic_proposal("Evitar faltas innecesarias")])]


def pace_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    cfg, score, rival = ctx.config, snap.get("score") or {}, ctx.rival_team_id
    if ctx.pace is None or not rival or rival not in score or ctx.own_team_id not in score:
        return []
    margin = score[ctx.own_team_id] - score[rival]
    pace = ctx.pace.evaluate(snap)
    if margin > -cfg.pace_losing_margin or not pace or not pace["reliable"]:
        return []
    own_habit, rival_habit, current = pace["habit_own40"], pace["habit_rival40"], pace["current40"]
    if own_habit is None or rival_habit is None or abs(own_habit - rival_habit) < cfg.pace_gap:
        return []
    if abs(current - rival_habit) >= abs(current - own_habit):
        return []                     # the game is closer to our pace than to theirs: they are not imposing theirs
    direction = "up" if rival_habit < own_habit else "down"
    verb = "subir" if direction == "up" else "bajar"
    return [Advice(
        key=f"pace:{direction}:{snap['period']}", id="pace_control", severity="info", category="gestion",
        message=(f"El rival impone su ritmo ({current:.0f} posesiones por 40 min; el suyo {rival_habit:.0f}, el nuestro "
                 f"{own_habit:.0f}) y vamos perdiendo ({margin:+d}): {verb} el ritmo."),
        evidence={"direction": direction, "current40": current, "habit_own40": own_habit, "habit_rival40": rival_habit, "margin": margin},
        proposal=[tactic_proposal(f"{verb.capitalize()} el ritmo: " + ("correr más, transición rápida" if direction == "up"
                                                                         else "atacar más tiempo y cuidar cada posesión"))])]
