"""Rotation rules: fatigue of the players currently on court (own team)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .advice_types import Advice, RuleContext
from .config import RuleConfig

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


def fatigue_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    out = []
    for pid, p in snap["players"].items():
        if p["team_id"] != ctx.own_team_id or not p["on_court"]:
            continue
        index, parts = fatigue_index(p["stint"], p["minutes"], snap["elapsed"],
                                     ctx.baselines.get(pid), ctx.config)
        if index < ctx.config.fatigue_alert_index:
            continue
        out.append(Advice(
            key=f"fatigue:{pid}", id="fatigue_high", severity="warning", category="rotacion",
            message=(f"{p['name']}: riesgo de fatiga alto (índice {index:.0f}/100), "
                     f"{_clock(p['stint'])} seguidos en pista y {p['minutes'] // 60} min jugados. "
                     "Valorar descanso."),
            evidence={"player_id": pid, "team_id": p["team_id"], "index": index, "components": parts,
                      "stint_s": p["stint"], "minutes_s": p["minutes"],
                      "has_baseline": pid in ctx.baselines},
            rearm_s=ctx.config.fatigue_rearm_s,
        ))
    return out
