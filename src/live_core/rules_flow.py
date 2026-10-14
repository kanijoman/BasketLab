"""Game-flow rules (issue #242), read from the event log with ``windows``.

* ``scoring_drought``: R2 own team without scoring (timeout or change of system, with the diagnosis of the window) and
  the rival without scoring while we do (a window to run); P2 no field goal for a while although free throws went in.
* ``long_run``: P3 a long run against (net -10 in 5 min: timeout) and P4 a run for us (do not break the lineup).
* ``after_timeout_scoring`` (P5, issue #249): the rival scores right after coming out of its timeouts (at least ``timeout_score_n`` of
  its ``timeout_score_min`` or more timeouts, inside ``timeout_score_window_s``): prepare a special defence of the inbound pass.
* ``static_offense`` (G4, issue #252): ``static_min_fgm`` or more made baskets with an assist share of ``static_ast_share`` or less:
  move the ball. Said once per half.
* ``game_flow_windows``: G2 rival offensive rebounds, G3 rival points right after our turnovers, G5 rival turnovers,
  all in the last three minutes.

Droughts and runs are said once per episode (``timeouts.episode``: the stretch since the team's last timeout of the period)
and not in the minute after our own timeout. Thresholds are provisional, in ``RuleConfig``.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .advice_types import Advice, RuleContext
from .proposals import tactic_proposal, timeout_proposal
from .timeouts import episode, timeout_within, timeouts_left
from .windows import field_goal_gap, points_after_turnovers, run_causes, scoring_gap, scores_after_timeouts, window_stats


def _clock(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def _quiet(snap: Dict[str, Any], ctx: RuleContext) -> bool:
    """True just after our own timeout: the coach has just reacted, say nothing yet."""
    return timeout_within(snap, ctx.own_team_id, ctx.config.after_timeout_quiet_s)


def _names(snap: Dict[str, Any]) -> Dict[str, str]:
    return {pid: p["name"].strip() for pid, p in snap.get("players", {}).items()}


def _own_drought(snap: Dict[str, Any], ctx: RuleContext, gap: int) -> Advice:
    log, now, cfg = snap.get("log", []), snap["elapsed"], ctx.config
    own = window_stats(log, ctx.own_team_id, now - gap, now)
    rival = window_stats(log, ctx.rival_team_id or "", now - gap, now)
    causes = "; ".join(c["text"] for c in run_causes(own, rival, _names(snap), cfg))
    left = timeouts_left(snap, ctx.own_team_id)
    proposal = ([timeout_proposal(left)] if left > 0 else []) + [tactic_proposal("Cambio de sistema")]
    return Advice(
        key=f"drought:{episode(snap, ctx.own_team_id)}", id="own_drought",
        severity="critical" if gap >= cfg.drought_critical_s else "warning", category="gestion",
        message=(f"Sequía de {_clock(gap)} sin anotar" + (f" ({causes})" if causes else "")
                 + ". Valorar tiempo muerto o cambio de sistema."),
        evidence={"gap_s": gap, "causes": causes}, proposal=proposal)


def drought_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    cfg, own, rival, now, log = ctx.config, ctx.own_team_id, ctx.rival_team_id, snap["elapsed"], snap.get("log", [])
    out: List[Advice] = []
    own_gap = scoring_gap(log, own, now)
    if own_gap >= cfg.drought_own_s and not _quiet(snap, ctx):
        out.append(_own_drought(snap, ctx, own_gap))
    fg_gap = field_goal_gap(log, own, now)
    if fg_gap >= cfg.drought_fg_s and own_gap < fg_gap and not _quiet(snap, ctx):   # free throws kept the score moving
        out.append(Advice(
            key=f"fg_drought:{episode(snap, own)}", id="fg_drought", severity="warning", category="gestion",
            message=f"Sin canasta de campo en {_clock(fg_gap)} (solo tiros libres). Atacar el aro.",
            evidence={"gap_s": fg_gap}, proposal=[tactic_proposal("Atacar el aro y cambiar de sistema")]))
    rival_gap = scoring_gap(log, rival, now) if rival else 0
    if rival and rival_gap >= cfg.drought_rival_s and own_gap < rival_gap:
        out.append(Advice(
            key=f"rival_drought:{episode(snap, rival)}", id="rival_drought", severity="info", category="rival",
            message=f"El rival lleva {_clock(rival_gap)} sin anotar: ventana para correr.",
            evidence={"gap_s": rival_gap, "team_id": rival}, proposal=[tactic_proposal("Correr: transición y ritmo alto")]))
    return out


def long_run_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    rival = ctx.rival_team_id
    if not rival:
        return []
    cfg, own, now, log, out = ctx.config, ctx.own_team_id, snap["elapsed"], snap.get("log", []), []
    long_net = (window_stats(log, own, now - cfg.long_run_window_s, now)["pts"]
                - window_stats(log, rival, now - cfg.long_run_window_s, now)["pts"])
    if long_net <= -cfg.long_run_net and not _quiet(snap, ctx):
        out.append(Advice(
            key=f"long_run:{episode(snap, own)}", id="long_run", severity="warning", category="gestion",
            message=(f"Parcial largo en contra: {long_net} neto en los últimos {cfg.long_run_window_s // 60} min. "
                     "Valorar tiempo muerto."),
            evidence={"net": long_net, "window_s": cfg.long_run_window_s},
            proposal=[timeout_proposal(timeouts_left(snap, own))]))
    net = (window_stats(log, own, now - cfg.run_window_s, now)["pts"]
           - window_stats(log, rival, now - cfg.run_window_s, now)["pts"])
    if net >= cfg.own_run_net:
        out.append(Advice(
            key=f"own_run:{episode(snap, rival)}", id="own_run", severity="info", category="gestion",
            message=(f"Parcial a favor: +{net} neto en los últimos {_clock(cfg.run_window_s)}. No romper el quinteto "
                     "y preparar la defensa tras el tiempo muerto del rival."),
            evidence={"net": net, "window_s": cfg.run_window_s}))
    return out


def window_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    rival = ctx.rival_team_id
    if not rival:
        return []
    cfg, own, now, log, out = ctx.config, ctx.own_team_id, snap["elapsed"], snap.get("log", []), []
    start, minutes = now - cfg.flow_window_s, cfg.flow_window_s // 60
    theirs = window_stats(log, rival, start, now)
    if theirs["orb"] >= cfg.rival_orb_n:
        out.append(Advice(
            key=f"rival_orb:{episode(snap, own)}", id="rival_orb_window", severity="warning", category="four_factors",
            message=f"El rival lleva {theirs['orb']} rebotes ofensivos en los últimos {minutes} min. Cerrar el rebote y meter un reboteador.",
            evidence={"orb": theirs["orb"], "window_s": cfg.flow_window_s},
            proposal=[tactic_proposal("Cerrar el rebote: bloqueo y balance")]))
    points = points_after_turnovers(log, own, rival, start, now, cfg.tov_points_horizon_s)
    if points >= cfg.tov_points_n:
        out.append(Advice(
            key=f"tov_points:{episode(snap, own)}", id="points_off_turnovers", severity="warning", category="four_factors",
            message=f"El rival ha anotado {points} puntos tras nuestras pérdidas en los últimos {minutes} min. Balance defensivo.",
            evidence={"points": points, "window_s": cfg.flow_window_s},
            proposal=[tactic_proposal("Balance defensivo tras pérdida")]))
    if theirs["tov"] >= cfg.rival_tov_n:
        out.append(Advice(
            key=f"rival_tov:{episode(snap, rival)}", id="rival_turnovers", severity="info", category="rival",
            message=f"El rival suma {theirs['tov']} pérdidas en los últimos {minutes} min. Mantener la presión.",
            evidence={"turnovers": theirs["tov"], "window_s": cfg.flow_window_s, "team_id": rival},
            proposal=[tactic_proposal("Mantener la presión defensiva")]))
    return out


def after_timeout_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    rival, cfg = ctx.rival_team_id, ctx.config
    if not rival:
        return []
    timeouts, followed = scores_after_timeouts(snap.get("log", []), rival, cfg.timeout_score_window_s, snap["elapsed"])
    if timeouts < cfg.timeout_score_min or followed < cfg.timeout_score_n:
        return []
    return [Advice(
        key=f"after_timeout:{timeouts}", id="rival_scores_after_timeout", severity="info", category="rival",
        message=f"El rival anota al salir de sus tiempos muertos ({followed} de {timeouts}): preparar la defensa del saque.",
        evidence={"timeouts": timeouts, "scored": followed, "window_s": cfg.timeout_score_window_s, "team_id": rival},
        proposal=[tactic_proposal("Defensa especial del saque tras el tiempo muerto del rival")])]


def static_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    stats = (snap["teams"].get(ctx.own_team_id) or {}).get("stats") or {}
    fgm, ast, cfg = stats.get("fg2m", 0) + stats.get("fg3m", 0), stats.get("ast", 0), ctx.config
    if fgm < cfg.static_min_fgm or ast / fgm > cfg.static_ast_share:
        return []
    return [Advice(
        key=f"static:{1 if snap['period'] <= 2 else 2}", id="static_offense", severity="info", category="four_factors",
        message=f"Juego estático: {ast} asistencias en {fgm} canastas ({round(100 * ast / fgm)} %). Mover el balón.",
        evidence={"ast": ast, "fgm": fgm, "share": round(ast / fgm, 3)},
        proposal=[tactic_proposal("Mover el balón: un pase más antes de tirar")])]
