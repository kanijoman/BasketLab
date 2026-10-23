"""Rival run and own turnovers (issue #241, R1 and R3), read from the event log with ``windows``.

* ``rival_run``: levels by net points in ``run_window_s`` (info from ``run_net_info``, warning from ``run_points``, critical
  when the rival scores ``run_points`` or more and we score nothing); says why (``windows.run_causes``) and proposes a timeout
  if there are any left.
* ``turnover_streak``: ``turnover_streak`` own turnovers in ``turnover_window_s``; proposes a timeout, names the player who
  concentrates them (``turnover_player_min`` or more) and proposes taking him off the ball handling.

Neither repeats by time: each level of a run, and each streak, is said once per episode (``timeouts.episode``: the stretch since our
last timeout of the period), and both stay silent in the minute after our own timeout (``after_timeout_quiet_s``).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .advice_types import Advice, RuleContext
from .proposals import tactic_proposal, timeout_proposal
from .timeouts import episode, timeout_within, timeouts_left
from .windows import run_causes, run_start, window_stats


def _clock(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def _names(snap: Dict[str, Any]) -> Dict[str, str]:
    return {pid: p["name"].strip() for pid, p in snap.get("players", {}).items()}


def _run_level(rival: int, own: int, cfg: Any) -> Optional[str]:
    if rival >= cfg.run_points and own == 0:
        return "critical"
    if rival - own >= cfg.run_points:
        return "warning"
    if rival - own >= cfg.run_net_info:
        return "info"
    return None


def run_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    if not ctx.rival_team_id or timeout_within(snap, ctx.own_team_id, ctx.config.after_timeout_quiet_s):
        return []
    cfg, now, log = ctx.config, snap["elapsed"], snap.get("log", [])
    start = run_start(snap, cfg.run_window_s)
    own = window_stats(log, ctx.own_team_id, start, now)
    rival = window_stats(log, ctx.rival_team_id, start, now)
    level = _run_level(rival["pts"], own["pts"], cfg)
    if level is None:
        return []
    causes = "; ".join(c["text"] for c in run_causes(own, rival, _names(snap), cfg))
    left = timeouts_left(snap, ctx.own_team_id)
    return [Advice(
        key=f"rival_run:{episode(snap, ctx.own_team_id)}:{level}", id="rival_run", severity=level, category="gestion",
        message=(f"Parcial de {own['pts']}-{rival['pts']} en contra en los últimos {_clock(cfg.run_window_s)}"
                 + (f" ({causes})" if causes else "") + "."),
        evidence={"rival_points": rival["pts"], "own_points": own["pts"], "window_s": cfg.run_window_s,
                  "net": rival["pts"] - own["pts"], "causes": causes},
        proposal=[timeout_proposal(left)] if left > 0 else [tactic_proposal("Sin tiempos muertos: cambio táctico o de defensa")],
    )]


def turnover_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    cfg, now = ctx.config, snap["elapsed"]
    if timeout_within(snap, ctx.own_team_id, cfg.after_timeout_quiet_s):
        return []
    own = window_stats(snap.get("log", []), ctx.own_team_id, now - cfg.turnover_window_s, now)
    if own["tov"] < cfg.turnover_streak:
        return []
    main = max(sorted(own["tov_by_player"].items()), key=lambda kv: kv[1], default=(None, 0))
    named = main[0] is not None and main[1] >= cfg.turnover_player_min
    name = _names(snap).get(main[0], main[0]) if named else ""
    left = timeouts_left(snap, ctx.own_team_id)
    proposal: List[Dict[str, Any]] = [timeout_proposal(left)] if left > 0 else []
    if named:
        proposal.append(tactic_proposal(f"Sacar a {name} del manejo del balón", main[0], name))
    return [Advice(
        key=f"tov_streak:{episode(snap, ctx.own_team_id)}", id="turnover_streak", severity="warning", category="gestion",
        message=(f"{own['tov']} pérdidas propias en los últimos {cfg.turnover_window_s // 60} min"
                 + (f" ({main[1]} de {name})" if named else "") + ". Asegurar el balón."),
        evidence={"turnovers": own["tov"], "window_s": cfg.turnover_window_s, "main_player_id": main[0] if named else None},
        proposal=proposal,
    )]
