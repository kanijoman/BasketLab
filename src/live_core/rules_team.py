"""Foul rules (players and team): own fouls by risk, the bonus by time left, rival fouls with a concrete tactic."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .advice_types import Advice, RuleContext
from .clock import game_seconds_left
from .proposals import tactic_proposal
from .rules_fouls import FOUL_OUT, evaluate_player_fouls, warn_threshold


def foul_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    """Own players close to fouling out."""
    period, out = snap["period"], []
    left = game_seconds_left(period, snap["remaining"])
    for pid, p in snap["players"].items():
        if p["team_id"] != ctx.own_team_id:
            continue
        alert = evaluate_player_fouls(pid, p["name"], p["pf"], period, seconds_left=left,
                                      min_left_s=ctx.config.foul_min_left_s)
        if alert:
            out.append(Advice(
                key=f"foul:{pid}:{p['pf']}", id="foul_trouble", severity=alert.severity,
                category="faltas", message=alert.message,
                evidence={"player_id": pid, "team_id": p["team_id"], "pf": p["pf"], "period": period},
            ))
    return out


def _contact_player(snap: Dict[str, Any], ctx: RuleContext) -> Optional[Dict[str, Any]]:
    """The own player on court who draws the most contact (free-throw rate z above the threshold), or None."""
    best = None
    for pid, p in snap["players"].items():
        if p["team_id"] != ctx.own_team_id or not p["on_court"]:
            continue
        ftr = ((ctx.baselines.get(pid) or {}).get("z") or {}).get("ftr")
        if ftr is not None and ftr >= ctx.config.contact_ftr_z and (best is None or ftr > best[0]):
            best = (ftr, pid, p["name"].strip())
    return {"player_id": best[1], "name": best[2]} if best else None


def _attack_proposal(contact: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if contact is None:
        return [tactic_proposal("Atacar el aro y forzar el contacto")]
    return [tactic_proposal(f"Balón a {contact['name']}, que provoca contacto", contact["player_id"], contact["name"])]


def rival_foul_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    """Rival players in foul trouble: an opportunity to attack them. An important rival is a warning; the ball goes to
    the own player who draws the most contact (issue #241, R8)."""
    period, out = snap["period"], []
    contact = _contact_player(snap, ctx)
    for pid, p in snap["players"].items():
        pf = p["pf"]
        if p["team_id"] == ctx.rival_team_id and warn_threshold(period) <= pf < FOUL_OUT:
            important = ((ctx.rival_baselines.get(pid) or {}).get("avg_min") or 0) >= ctx.config.rival_important_avg_min_s
            message = f"Rival {p['name']} con {pf} faltas personales: atacarle y forzar contacto."
            if contact:
                message += f" Balón a {contact['name']}, que provoca contacto."
            out.append(Advice(
                key=f"rfoul:{pid}:{pf}", id="rival_foul_trouble", severity="warning" if important else "info", category="faltas",
                message=message,
                evidence={"player_id": pid, "team_id": p["team_id"], "pf": pf, "period": period, "important": important},
                proposal=_attack_proposal(contact),
            ))
    return out


def _bonus_severity(count: int, limit: int, remaining: int, cfg: Any) -> str:
    """Own team: the longer we would be in bonus the more serious (issue #241, F3)."""
    if count == limit:     # the next foul puts the rival in the bonus
        return "warning" if remaining > cfg.bonus_short_left_s else "info"
    if remaining > cfg.bonus_long_left_s:
        return "critical"
    return "warning" if remaining > cfg.bonus_short_left_s else "info"


def team_fouls_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    period, limit, out = snap["period"], ctx.config.team_foul_bonus, []
    contact = _contact_player(snap, ctx)
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
            out.append(Advice(key=f"bonus:{team_id}:{period}", id="team_fouls_bonus",
                              severity=_bonus_severity(count, limit, snap["remaining"], ctx.config),
                              category="faltas", message=msg.format(n=count), evidence=evidence))
        else:
            msg = ("Rival con {n} faltas de equipo en el periodo: su siguiente falta da tiros libres."
                   if count == limit else
                   "Rival con {n} faltas de equipo en el periodo: ya estamos en bonus, atacar el aro.")
            out.append(Advice(key=f"rbonus:{team_id}:{period}", id="rival_near_bonus", severity="info",
                              category="faltas", message=msg.format(n=count), evidence=evidence,
                              proposal=_attack_proposal(contact)))
    return out
