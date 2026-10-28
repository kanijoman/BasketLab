"""Rotation rules: fatigue of the players currently on court (own team)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .advice_types import Advice, RuleContext
from .config import RuleConfig
from .game_context import game_phase
from .rules_players import orb_dominant
from .clock import period_start
from .windows import player_form, run_start, window_stats

GAME_SECONDS = 2400


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def baseline_trusted(baseline: Optional[Dict[str, Any]], cfg: RuleConfig) -> bool:
    """Is the baseline of the player backed by enough games and stints? A baseline that does not say its sample (older packages) is trusted."""
    baseline = baseline or {}
    if baseline.get("games") is not None and baseline["games"] < cfg.fatigue_min_games:
        return False
    return not (baseline.get("stints") is not None and baseline["stints"] < cfg.fatigue_min_stints)


def fatigue_index(
    stint: int,
    minutes: int,
    elapsed: int,
    baseline: Optional[Dict[str, Any]],
    config: Optional[RuleConfig] = None,
) -> Tuple[float, Dict[str, float]]:
    """Heuristic fatigue index 0-100 and its components (each 0-1).

    Not a calibrated probability. Components that cannot be computed (no season baseline, too little game played, a baseline of too few games
    or stints, #479) are left out and the weights re-normalised.
    """
    cfg = config or RuleConfig()
    trusted = baseline_trusted(baseline, cfg)
    baseline = (baseline or {}) if trusted else {}
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


def _level(index: float, cfg: RuleConfig, stint: int = 10 ** 6) -> Optional[str]:
    """The level of an index, capped by how long the player has been on court: nothing below the first floor, never critical below the second (#479)."""
    if stint < cfg.fatigue_floor_warning_s:
        return None
    if index >= cfg.fatigue_critical_index and stint >= cfg.fatigue_floor_critical_s:
        return "critical"
    if index >= cfg.fatigue_warning_index:
        return "warning"
    return "info" if index >= cfg.fatigue_alert_index else None


def _reason_to_keep(snap: Dict[str, Any], ctx: RuleContext, pid: str) -> Optional[str]:
    """Why a tired player may stay for now: the team is on a run, or he is on a hot streak (else None)."""
    cfg, own, rival, now, log = ctx.config, ctx.own_team_id, ctx.rival_team_id, snap["elapsed"], snap.get("log", [])
    start = run_start(snap, cfg.run_window_s)
    net = window_stats(log, own, start, now)["pts"] - (window_stats(log, rival, start, now)["pts"] if rival else 0)
    if net >= cfg.own_run_net:
        return "parcial a favor"
    form = player_form(log, own, pid, now, cfg.hot_player_window_s, period_start(snap.get("period", 1)))
    if form["pts"] >= cfg.hot_player_pts or form["made_in_row"] >= cfg.hot_player_row:
        return "está en racha"
    if orb_dominant(snap["players"][pid], ctx.baselines.get(pid), cfg):
        return "está dominando el rebote ofensivo"
    return None


def _decided_offset(snap: Dict[str, Any], ctx: RuleContext) -> float:
    """Index points added in a decided game: fatigue alerts earlier when nothing is at stake (issue #320)."""
    cfg = ctx.config
    if not cfg.decided_only_rotation or not ctx.rival_team_id:
        return 0.0
    return cfg.decided_fatigue_offset if game_phase(snap, ctx.own_team_id, ctx.rival_team_id, cfg)["phase"] == "decided" else 0.0


def _stoppage_open(snap: Dict[str, Any]) -> bool:
    """A timeout (either team) at the snapshot's own game second: FEB writes its substitutions AFTER the timeout line, so the
    lineup is not reliable until the game goes on (issue #400)."""
    now = snap["elapsed"]
    return any(len(e) > 2 and e[2] == "timeout" and e[0] == now for e in snap.get("log", []))


def fatigue_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    """Fatigue of the own players on court, escalated info -> warning -> critical (issue #241, R5).

    Each level is said once per stint (the key carries the second the stint began), so nothing repeats by time. With an own
    run or a player on a hot streak the level goes down one step (never below information) and the message says why.
    """
    out = []
    if _stoppage_open(snap):
        return out   # not said yet, not lost: the key is only stored when the alert is emitted
    for pid, p in snap["players"].items():
        if p["team_id"] != ctx.own_team_id or not p["on_court"]:
            continue
        index, parts = fatigue_index(p["stint"], p["minutes"], snap["elapsed"],
                                     ctx.baselines.get(pid), ctx.config)
        level = _level(index + _decided_offset(snap, ctx), ctx.config, p["stint"])
        if level is None:
            continue
        reason = _reason_to_keep(snap, ctx, pid)
        severity = _LEVELS[min(len(_LEVELS) - 1, _LEVELS.index(level) + 1)] if reason else level
        baseline = ctx.baselines.get(pid)
        trusted = baseline_trusted(baseline, ctx.config)
        usual = (baseline or {}).get("avg_stint") if trusted else None
        usual = usual or ctx.config.fatigue_default_avg_stint_s
        message = (f"{p['name']}: riesgo de fatiga {'muy alto' if level == 'critical' else 'alto'}, "
                   f"{_clock(p['stint'])} seguidos en pista (su tramo habitual: {_clock(int(usual))}) y {p['minutes'] // 60} min jugados. "
                   + ("Cambio recomendado." if level == "critical" else "Valorar descanso."))
        if reason:
            message += f" Se baja un nivel: {reason}."
        out.append(Advice(
            key=f"fatigue:{pid}:{snap['elapsed'] - p['stint']}:{level}" + ("~context" if reason else ""),
            id="fatigue_high", severity=severity, category="rotacion", message=message,
            evidence={"player_id": pid, "team_id": p["team_id"], "index": index, "components": parts,
                      "stint_s": p["stint"], "minutes_s": p["minutes"], "level": level, "kept_because": reason,
                      "has_baseline": pid in ctx.baselines, "avg_stint_s": int(usual),
                      "sample": {"games": (baseline or {}).get("games"), "stints": (baseline or {}).get("stints"), "trusted": trusted}},
        ))
    return out
