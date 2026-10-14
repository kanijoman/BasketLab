"""Quintets and plus/minus (issue #248): R9 and J7, over the stints the snapshot carries (``lineups.py``).

* R9 ``lineup_net``: our quintet on court is ``lineup_net`` (6) points or more down after ``lineup_min_s`` (3:00) together: consider a
  change, with who could come in for the worst of the five (the recommender). If the package has the quintet's season (at least
  ``lineup_season_min_s`` together) its net rating per 40 minutes is added.
* J7 ``player_plus_minus``: a player on court is ``pm_player_net`` (8) points or more down since he came in, after ``pm_player_min_s``
  (4:00) of stint, and at least ``pm_player_gap`` (3) worse than his teammates on court (if the whole quintet is down it is a lineup
  problem, which R9 covers, and J7 stays quiet while the R9 alert is there): consider his relief, with the recommender's proposal.

Both are said once per stint (the key carries the second it began). Thresholds are provisional, in ``RuleConfig``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .advice_types import Advice, RuleContext
from .lineups import lineup_key


def _clock(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def _swaps(snap: Dict[str, Any], ctx: RuleContext, player_id: str) -> List[Dict[str, Any]]:
    return ctx.recommender.suggest_swaps(snap, player_id) if ctx.recommender is not None else []


def _lineup_is_down(now: Optional[Dict[str, Any]], cfg: Any) -> bool:
    return bool(now) and now["seconds"] >= cfg.lineup_min_s and now["pts_for"] - now["pts_against"] <= -cfg.lineup_net


def lineup_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    now = (snap.get("lineup_now") or {}).get(ctx.own_team_id)
    cfg = ctx.config
    if not _lineup_is_down(now, cfg):
        return []
    net = now["pts_for"] - now["pts_against"]
    players = snap["players"]
    names = ", ".join(players[pid]["name"].strip() for pid in now["players"] if pid in players)
    message = f"El quinteto en pista ({names}) lleva {net:+d} en {_clock(now['seconds'])}. Valorar cambio."
    season = ctx.lineups.get(lineup_key(now["players"]))
    if season and season["seconds"] >= cfg.lineup_season_min_s:
        message += f" En la temporada: {season['net40']:+.1f} por 40 min en {season['seconds'] // 60} min juntos."
    worst = min((pid for pid in now["players"] if pid in players), key=lambda pid: (players[pid].get("stint_pm", 0), pid), default=None)
    return [Advice(
        key=f"lineup_net:{lineup_key(now['players'])}:{now['since']}", id="lineup_net", severity="warning", category="rotacion",
        message=message,
        evidence={"players": now["players"], "net": net, "seconds": now["seconds"], "since": now["since"],
                  "season_net40": season["net40"] if season else None},
        proposal=_swaps(snap, ctx, worst) if worst else [])]


def player_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    cfg, out = ctx.config, []
    if _lineup_is_down((snap.get("lineup_now") or {}).get(ctx.own_team_id), cfg):
        return []
    on_court = {pid: p.get("stint_pm", 0) for pid, p in snap["players"].items() if p["team_id"] == ctx.own_team_id and p["on_court"]}
    for pid, p in snap["players"].items():
        if p["team_id"] != ctx.own_team_id or not p["on_court"]:
            continue
        pm = p.get("stint_pm", 0)
        if pm > -cfg.pm_player_net or p["stint"] < cfg.pm_player_min_s:
            continue
        others = [v for other, v in on_court.items() if other != pid]
        if others and pm > sum(others) / len(others) - cfg.pm_player_gap:
            continue
        out.append(Advice(
            key=f"pm:{pid}:{snap['elapsed'] - p['stint']}", id="player_plus_minus", severity="info", category="rotacion",
            message=f"{p['name'].strip()} lleva {pm:+d} desde que entró ({_clock(p['stint'])} en pista). Valorar relevo.",
            evidence={"player_id": pid, "team_id": p["team_id"], "stint_pm": pm, "stint_s": p["stint"]},
            proposal=_swaps(snap, ctx, pid)))
    return out
