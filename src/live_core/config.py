"""Rule thresholds. Business logic for the coaching staff: proposed defaults, meant to be
confirmed and, later, edited by the user (they travel inside the preparation package)."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RuleConfig:
    # Team fouls: the next foul after this many in a period puts the opponent in the bonus.
    team_foul_bonus: int = 4
    # Scoring run against us: opponent points with no answer inside the window.
    run_points: int = 8
    run_window_s: int = 150
    # Own turnovers inside the window.
    turnover_streak: int = 4
    turnover_window_s: int = 300
    # Fatigue index (0-100): weighted mix of stint length, minutes pace and projected minutes.
    fatigue_alert_index: float = 60.0
    fatigue_rearm_s: int = 240
    fatigue_default_avg_stint_s: int = 420
    fatigue_weight_stint: float = 40.0
    fatigue_weight_minutes: float = 35.0
    fatigue_weight_projection: float = 25.0
    fatigue_stint_full_ratio: float = 2.0      # stint / usual stint at which the component maxes out
    fatigue_minutes_full_ratio: float = 1.5    # minutes / expected minutes at this point
    fatigue_projection_full_excess: float = 0.25  # projected minutes above the p90, as a fraction
    fatigue_min_elapsed_s: int = 600           # minutes-based components need this much game
    # Four Factors (Oliver): enough possessions to trust the game, expected net rating per
    # unit of the weighted score (placeholder until calibrated), smallest lever worth a call.
    ff_min_possessions: float = 15.0
    ff_beta: float = 9.0
    ff_lever_min_pts100: float = 3.0
    ff_lever_rearm_s: int = 600
    # Recommender: widest role gap accepted, weight of that gap in the ranking, how much the
    # quintet's rebounding/creation/spacing/interior may drop (sum of z), results per advice.
    rec_max_role_distance: float = 3.0
    rec_distance_weight: float = 0.5
    rec_balance_tolerance: float = 1.5
    rec_max_results: int = 3
    rec_min_lever_gain: float = 0.5   # smallest improvement (sigma) worth proposing for a lever
    # Rival players producing far above their season rate: minutes needed, excess in Poisson
    # standard deviations over the expected count, and the minimum count per metric.
    rival_min_seconds: int = 240
    rival_sigma: float = 2.0
    rival_min_pts: int = 10
    rival_min_orb: int = 3
    rival_min_stl: int = 3
    rival_min_ast: int = 4
    rival_min_fg3m: int = 3
    rival_min_fta: int = 5
    # Rival shot zones (by family): attempts/makes and points-per-shot excess for the efficiency
    # alert; attempts, share and share excess for the volume alert; prior weight in attempts.
    zone_min_attempts: int = 5
    zone_min_makes: int = 3
    zone_pps_excess: float = 0.5
    zone_min_share_attempts: int = 8
    zone_share: float = 0.35
    zone_share_excess: float = 0.15
    zone_shrink_n0: float = 20.0
    # Prior weight (in possessions) of the season expectation per factor.
    ff_n0_efg: float = 40.0
    ff_n0_tov: float = 25.0
    ff_n0_orb: float = 30.0
    ff_n0_ftr: float = 40.0

    @classmethod
    def from_dict(cls, overrides: Optional[Dict[str, Any]]) -> "RuleConfig":
        """Build from a package's ``rule_config``; unknown keys are ignored."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (overrides or {}).items() if k in known})
