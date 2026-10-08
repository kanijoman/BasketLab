"""Team-level rules: fouls (players and team), scoring runs and turnover streaks."""

from __future__ import annotations

from typing import Any, Dict, List

from .advice_types import Advice, RuleContext
from .rules_fouls import FOUL_OUT, evaluate_player_fouls, warn_threshold


def foul_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    period, out = snap["period"], []
    for pid, p in snap["players"].items():
        pf = p["pf"]
        if p["team_id"] == ctx.own_team_id:
            alert = evaluate_player_fouls(pid, p["name"], pf, period)
            if alert:
                out.append(Advice(
                    key=f"foul:{pid}:{pf}", id="foul_trouble", severity=alert.severity,
                    category="faltas", message=alert.message,
                    evidence={"player_id": pid, "team_id": p["team_id"], "pf": pf, "period": period},
                ))
        elif p["team_id"] == ctx.rival_team_id and warn_threshold(period) <= pf < FOUL_OUT:
            out.append(Advice(
                key=f"rfoul:{pid}:{pf}", id="rival_foul_trouble", severity="info", category="faltas",
                message=f"Rival {p['name']} con {pf} faltas personales: atacarle y forzar contacto.",
                evidence={"player_id": pid, "team_id": p["team_id"], "pf": pf, "period": period},
            ))
    return out


def team_fouls_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    period, limit, out = snap["period"], ctx.config.team_foul_bonus, []
    for team_id, own in ((ctx.own_team_id, True), (ctx.rival_team_id, False)):
        team = snap["teams"].get(team_id) if team_id else None
        count = (team or {}).get("fouls_by_period", {}).get(str(period), 0)
        if count < limit:
            continue
        evidence = {"team_id": team_id, "team_fouls": count, "period": period}
        if own:
            msg = ("Equipo con {n} faltas en el periodo: el rival entra en bonus con la siguiente."
                   if count == limit else
                   "Equipo con {n} faltas en el periodo: el rival ya está en bonus, evitar faltas.")
            out.append(Advice(key=f"bonus:{team_id}:{period}", id="team_fouls_bonus", severity="warning",
                              category="faltas", message=msg.format(n=count), evidence=evidence))
        else:
            msg = ("Rival con {n} faltas de equipo en el periodo: su siguiente falta da tiros libres."
                   if count == limit else
                   "Rival con {n} faltas de equipo en el periodo: ya estamos en bonus, atacar el aro.")
            out.append(Advice(key=f"rbonus:{team_id}:{period}", id="rival_near_bonus", severity="info",
                              category="faltas", message=msg.format(n=count), evidence=evidence))
    return out


def _recent(log: List[List[Any]], now: int, window: int, kind: str, team_id: str) -> List[List[Any]]:
    return [e for e in log if e[2] == kind and e[1] == team_id and now - window <= e[0] <= now]


def run_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    if not ctx.rival_team_id:
        return []
    cfg, now, log = ctx.config, snap["elapsed"], snap.get("log", [])
    rival = sum(e[3] for e in _recent(log, now, cfg.run_window_s, "pts", ctx.rival_team_id))
    own = sum(e[3] for e in _recent(log, now, cfg.run_window_s, "pts", ctx.own_team_id))
    if rival < cfg.run_points or own > 0:
        return []
    window = f"{cfg.run_window_s // 60}:{cfg.run_window_s % 60:02d}"
    return [Advice(
        key="rival_run", id="rival_run", severity="critical", category="gestion",
        message=f"Parcial de 0-{rival} en contra en los últimos {window}. Valorar tiempo muerto.",
        evidence={"rival_points": rival, "own_points": own, "window_s": cfg.run_window_s},
        rearm_s=cfg.run_window_s * 2,
    )]


def turnover_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    cfg = ctx.config
    count = len(_recent(snap.get("log", []), snap["elapsed"], cfg.turnover_window_s, "tov", ctx.own_team_id))
    if count < cfg.turnover_streak:
        return []
    return [Advice(
        key="tov_streak", id="turnover_streak", severity="warning", category="gestion",
        message=f"{count} pérdidas propias en los últimos {cfg.turnover_window_s // 60} min. Asegurar el balón.",
        evidence={"turnovers": count, "window_s": cfg.turnover_window_s},
        rearm_s=cfg.turnover_window_s,
    )]
