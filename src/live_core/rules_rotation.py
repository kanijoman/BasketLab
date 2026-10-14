"""Rotation rules: fatigue of the players currently on court (own team)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .advice_types import Advice, RuleContext
from .config import RuleConfig
from .windows import last_shots, trailing_makes, window_stats

GAME_SECONDS = 2400


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def fatigue_index(
    stint: int,
    minutes: int,
    elapsed: int,
    baseline: Optional[Dict[str, Any]],
    config: Optional[RuleConfig] = None,
) -> Tuple[float, Dict[str, float]]:
    """Heuristic fatigue index 0-100 and its components (each 0-1).

    Not a calibrated probability. Components that cannot be computed (no season baseline,
    too little game played) are left out and the weights re-normalised.
    """
    cfg = config or RuleConfig()
    baseline = baseline or {}
    parts: Dict[str, float] = {}
    weights: Dict[str, float] = {}

    avg_stint = baseline.get("avg_stint") or cfg.fatigue_default_avg_stint_s
    parts["stint"] = _clamp((stint / avg_stint - 1) / (cfg.fatigue_stint_full_ratio - 1))
    weights["stint"] = cfg.fatigue_weight_stint

    if elapsed >= cfg.fatigue_min_elapsed_s:
        avg_min = baseline.get("avg_min")
        if avg_min:
            expected = avg_min * elapsed / GAME_SECONDS
            parts["minutes"] = _clamp((minutes / expected - 1) / (cfg.fatigue_minutes_full_ratio - 1))
            weights["minutes"] = cfg.fatigue_weight_minutes
        p90 = baseline.get("p90_min")
        if p90:
            projected = minutes / elapsed * GAME_SECONDS
            parts["projection"] = _clamp((projected - p90) / (cfg.fatigue_projection_full_excess * p90))
            weights["projection"] = cfg.fatigue_weight_projection

    total_weight = sum(weights.values())
    index = sum(weights[k] * parts[k] for k in parts) / total_weight * 100 if total_weight else 0.0
    return round(index, 2), {k: round(v, 3) for k, v in parts.items()}


def _clock(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


_LEVELS = ("critical", "warning", "info")     # most to least urgent
_HOT_STREAK = 3                              # consecutive made field goals of the player that count as a hot streak


def _level(index: float, cfg: RuleConfig) -> Optional[str]:
    if index >= cfg.fatigue_critical_index:
        return "critical"
    if index >= cfg.fatigue_warning_index:
        return "warning"
    return "info" if index >= cfg.fatigue_alert_index else None


def _reason_to_keep(snap: Dict[str, Any], ctx: RuleContext, pid: str) -> Optional[str]:
    """Why a tired player may stay for now: the team is on a run, or he is on a hot streak (else None)."""
    cfg, own, rival, now, log = ctx.config, ctx.own_team_id, ctx.rival_team_id, snap["elapsed"], snap.get("log", [])
    start = now - cfg.run_window_s
    net = window_stats(log, own, start, now)["pts"] - (window_stats(log, rival, start, now)["pts"] if rival else 0)
    if net >= cfg.own_run_net:
        return "parcial a favor"
    if trailing_makes(last_shots(log, own, _HOT_STREAK, player_id=pid)) >= _HOT_STREAK:
        return "está en racha"
    return None


def fatigue_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    """Fatigue of the own players on court, escalated info -> warning -> critical (issue #241, R5).

    Each level is said once per stint (the key carries the second the stint began), so nothing repeats by time. With an own
    run or a player on a hot streak the level goes down one step (never below information) and the message says why.
    """
    out = []
    for pid, p in snap["players"].items():
        if p["team_id"] != ctx.own_team_id or not p["on_court"]:
            continue
        index, parts = fatigue_index(p["stint"], p["minutes"], snap["elapsed"],
                                     ctx.baselines.get(pid), ctx.config)
        level = _level(index, ctx.config)
        if level is None:
            continue
        reason = _reason_to_keep(snap, ctx, pid)
        severity = _LEVELS[min(len(_LEVELS) - 1, _LEVELS.index(level) + 1)] if reason else level
        message = (f"{p['name']}: riesgo de fatiga {'muy alto' if level == 'critical' else 'alto'} (índice {index:.0f}/100), "
                   f"{_clock(p['stint'])} seguidos en pista y {p['minutes'] // 60} min jugados. "
                   + ("Cambio recomendado." if level == "critical" else "Valorar descanso."))
        if reason:
            message += f" Se baja un nivel: {reason}."
        out.append(Advice(
            key=f"fatigue:{pid}:{snap['elapsed'] - p['stint']}:{level}" + ("~context" if reason else ""),
            id="fatigue_high", severity=severity, category="rotacion", message=message,
            evidence={"player_id": pid, "team_id": p["team_id"], "index": index, "components": parts,
                      "stint_s": p["stint"], "minutes_s": p["minutes"], "level": level, "kept_because": reason,
                      "has_baseline": pid in ctx.baselines},
        ))
    return out
