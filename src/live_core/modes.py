"""Alert modes (issue #130): how many alerts the staff wants, without tuning thresholds.

``aggressive`` warns more and earlier, ``medium`` is the stock configuration and ``conservative`` says only what is clear. A mode is a set of
``RuleConfig`` values that we calibrate (the staff has no way to judge a single threshold): it applies under the package's own
``rule_config`` (``AdviceEngine.from_package``), so what a package says explicitly (a rule off, a threshold) still wins. The values are
provisional: they were set by hand around the stock ones and checked on the recorded match (more alerts the more aggressive the mode).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

DEFAULT_MODE = "medium"

# The same settings in aggressive and conservative, on each side of the stock value (tests/test_live_core_modes.py checks it).
MODES: Dict[str, Dict[str, Any]] = {
    "aggressive": {
        "fatigue_alert_index": 65.0, "fatigue_warning_index": 75.0,
        "run_points": 7, "long_run_net": 9, "own_run_net": 7,
        "drought_own_s": 210, "drought_rival_s": 180, "drought_fg_s": 150,
        "ff_lever_min_pts100": 2.0, "lever_step_pts100": 4.0,
        "wp_flip_drop": 0.15, "lineup_net": 5, "pm_player_net": 7,
        "turnover_streak": 4, "zone_concede_excess": 0.12, "edge_net": 5,
        "hot_player_pts": 6, "rival_orb_n": 2, "rival_tov_n": 3, "cold_fg_n": 7, "cold_3p_n": 6,
    },
    "medium": {},
    "conservative": {
        "fatigue_alert_index": 85.0, "fatigue_warning_index": 90.0,
        "run_points": 10, "long_run_net": 12, "own_run_net": 10,
        "drought_own_s": 300, "drought_rival_s": 270, "drought_fg_s": 240,
        "ff_lever_min_pts100": 4.5, "lever_step_pts100": 6.5,
        "wp_flip_drop": 0.30, "lineup_net": 8, "pm_player_net": 10,
        "turnover_streak": 6, "zone_concede_excess": 0.20, "edge_net": 8,
        "hot_player_pts": 8, "rival_orb_n": 4, "rival_tov_n": 5, "cold_fg_n": 9, "cold_3p_n": 8,
    },
}


def mode_overrides(mode: Optional[str]) -> Dict[str, Any]:
    """The ``RuleConfig`` values of a mode; an unknown or missing mode is the default one (nothing changes)."""
    return dict(MODES.get(mode or DEFAULT_MODE, {}))
