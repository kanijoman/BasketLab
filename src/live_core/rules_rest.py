"""Rest for the key players in a decided game (issue #273).

In phase ``decided`` the result will not change: the important players (many minutes on average and today) can rest and
the lowest profiles can play. Winning it is a warning; losing it is information with another text (some coaches prefer to
keep their best players on court). One alert per important player and game. The category ``descanso`` is not shifted by the
phase (``game_context.PHASE_SHIFT``): the severity here is the one the rule means.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .advice_types import Advice, RuleContext
from .game_context import game_phase


def _played(seconds: int) -> str:
    return "sin minutos hoy" if seconds <= 0 else f"{seconds // 60} min hoy"


def _is_important(pid: str, player: Dict[str, Any], ctx: RuleContext) -> bool:
    avg = (ctx.baselines.get(pid) or {}).get("avg_min") or 0
    return avg >= ctx.config.rest_important_avg_min_s and player["minutes"] >= ctx.config.rest_important_today_s


def _message(name: str, today: int, entry: Dict[str, Any], margin: int) -> str:
    came_in = f"{entry['in_name']} ({_played(entry['minutes_today_s'])})"
    if margin > 0:
        return f"Partido decidido (+{margin}): descansa a {name} ({_played(today)}) y da minutos a {came_in}."
    return (f"Partido decidido ({margin}): si el cuerpo técnico da el partido por perdido, {name} ({_played(today)}) "
            f"puede descansar y entrar {came_in}.")


def rest_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    cfg, recommender = ctx.config, ctx.recommender
    if recommender is None or not cfg.enabled("game_context"):
        return []
    context = game_phase(snap, ctx.own_team_id, ctx.rival_team_id, cfg)
    if context["phase"] != "decided":
        return []
    margin = context["margin"]
    important = sorted(
        ((pid, p) for pid, p in snap["players"].items()
         if p["team_id"] == ctx.own_team_id and p["on_court"] and _is_important(pid, p, ctx)),
        key=lambda item: (-item[1]["minutes"], item[0]))
    out: List[Advice] = []
    taken: List[str] = []        # each alert brings in somebody different
    for pid, p in important:
        proposal = recommender.suggest_rest(snap, pid, exclude=taken)
        if not proposal:
            continue
        taken.append(proposal[0]["in_id"])
        out.append(Advice(
            key=f"rest:{pid}", id="rest_starters", severity="warning" if margin > 0 else "info", category="descanso",
            message=_message(p["name"].strip(), p["minutes"], proposal[0], margin),
            evidence={"player_id": pid, "team_id": p["team_id"], "margin": margin, "minutes_s": p["minutes"],
                      "in_id": proposal[0]["in_id"]},
            proposal=proposal))
    return out
