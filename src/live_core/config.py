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

    @classmethod
    def from_dict(cls, overrides: Optional[Dict[str, Any]]) -> "RuleConfig":
        """Build from a package's ``rule_config``; unknown keys are ignored."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (overrides or {}).items() if k in known})
