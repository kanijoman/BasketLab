"""Rule thresholds. Business logic for the coaching staff: proposed defaults, meant to be
confirmed and, later, edited by the user (they travel inside the preparation package)."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Dict, Iterable, Optional, Tuple

# Ids of the alert rules, in evaluation order (advice.RULES). A package can switch any of them off with
# ``rule_config["rules_off"]``. ``team_fouls`` covers both team_fouls_bonus and rival_near_bonus.
RULE_IDS: Tuple[str, ...] = (
    "foul_trouble", "rival_foul_trouble", "formation_lineup", "team_fouls", "rival_run", "turnover_streak",
    "fatigue_high", "four_factors_lever", "rival_hot_player", "rival_zone", "rest_starters",
    "cold_shooting", "rival_hot_shooting", "free_throw_cold", "scoring_drought", "long_run", "game_flow_windows",
    "rival_player_form", "own_player_form", "rival_star_bench",
    "disqualification", "timeout_budget", "key_fouls_close", "rival_foul_pair",
)
# Engine features that can be switched off with ``rules_off`` like a rule but have no alerts of their own.
FEATURE_IDS: Tuple[str, ...] = ("game_context",)


def unknown_rule_ids(rule_ids: Iterable[str]) -> Tuple[str, ...]:
    """Ids that are neither rules nor switchable features of this engine. The engine ignores them (a package written
    for a newer engine must not crash the app); tools that write a package or a configuration use this to reject typos."""
    return tuple(r for r in rule_ids if r not in RULE_IDS and r not in FEATURE_IDS)


@dataclass(frozen=True)
class RuleConfig:
    # Rules and features switched off (ids in RULE_IDS and FEATURE_IDS). Nothing is off by default.
    rules_off: Tuple[str, ...] = ()
    # Game context: a game is "decided" with this margin and less time left of the 4th period, and "close_late" within
    # this margin and this much time left of the 4th period (or in overtime). Alerts change one level (game_context).
    # Illegal lineup: players of "formación" that must be on court at all times (0 = the competition has no such rule), and
    # how many consecutive evaluations the violation must last before it is said (a substitution is two feed lines).
    formation_min_on_court: int = 2
    formation_confirm_polls: int = 2
    decided_margin: int = 20
    # Rest in a decided game: a player is important with at least this average and this many seconds played today.
    rest_important_avg_min_s: int = 1200
    rest_important_today_s: int = 600
    decided_remaining_s: int = 480
    close_margin: int = 6
    close_remaining_s: int = 240
    # Shooting streaks (last N attempts, oldest first): own cold field goals / threes (made at most), rival hot field goals /
    # threes (made at least), own free throws at or below this share with at least this many attempts (issue #243).
    cold_fg_n: int = 8
    cold_fg_max_made: int = 1
    cold_3p_n: int = 7
    cold_3p_max_made: int = 1
    hot_fg_n: int = 8
    hot_fg_min_made: int = 6
    hot_3p_n: int = 6
    hot_3p_min_made: int = 4
    ft_cold_min_attempts: int = 8
    ft_cold_max_pct: float = 0.5
    # Game flow (issue #242): own drought (warning; critical from the second value), rival drought (a window to run), no field
    # goal; long run against (net points in the window), run for us (net, in run_window_s); counts in the flow window: rival
    # offensive rebounds, rival points within a few seconds of our turnovers, rival turnovers. Quiet after our own timeout.
    drought_own_s: int = 240
    drought_critical_s: int = 360
    drought_rival_s: int = 210
    drought_fg_s: int = 180
    after_timeout_quiet_s: int = 60
    long_run_net: int = 10
    long_run_window_s: int = 300
    own_run_net: int = 8
    flow_window_s: int = 180
    rival_orb_n: int = 3
    tov_points_n: int = 6
    tov_points_horizon_s: int = 8
    rival_tov_n: int = 4
    # Revised rules (issue #241). Fouls: three personal fouls are a risk only with more than this left in the game. Bonus: seconds
    # left in the period above which being in bonus is critical / a warning. Rival fouls: average seconds of an important rival
    # and the z of free-throw rate from which an own player is the one who draws contact. Turnovers: from this many of one player
    # he is named. Fatigue: index from which it is critical. Lever: the step (pts/100) it must worsen to be said again.
    foul_min_left_s: int = 360
    bonus_long_left_s: int = 300
    bonus_short_left_s: int = 120
    rival_important_avg_min_s: int = 1200
    contact_ftr_z: float = 0.5
    turnover_player_min: int = 3
    fatigue_critical_index: float = 95.0
    lever_step_pts100: float = 5.0
    # Players (issue #244): a streak is this many points in the window or this many baskets in a row; a rival depends on one
    # player above this share of his points (with this minimum); an own player is cold with at least this many attempts, an
    # eFG at most this, and a volume this many times above his usual; the rival's key players (by production) and the fouls
    # from which the key player coming back is a warning.
    hot_player_pts: int = 7
    hot_player_window_s: int = 180
    hot_player_row: int = 3
    dependence_share: float = 0.40
    dependence_min_pts: int = 12
    cold_player_min_fga: int = 6
    cold_player_max_efg: float = 0.30
    cold_player_volume_ratio: float = 1.5
    rival_key_n: int = 1
    key_return_pf: int = 3
    # Sanctions and the finish (issue #245): the timeout budget is warned from this many seconds left of the 4th period, the rival
    # without timeouts is pressed with at most this margin, and two rivals with this many fouls on court are attacked.
    timeout_budget_s: int = 240
    timeout_pressure_margin: int = 10
    rival_pair_pf: int = 3
    # Team fouls: the next foul after this many in a period puts the opponent in the bonus.
    team_foul_bonus: int = 4
    # Scoring run against us: opponent points with no answer inside the window.
    run_points: int = 8
    run_net_info: int = 6   # net points of a run that is already information (issue #241)
    run_window_s: int = 150
    # Own turnovers inside the window.
    turnover_streak: int = 4
    turnover_window_s: int = 300
    # Fatigue index (0-100): weighted mix of stint length, minutes pace and projected minutes.
    fatigue_alert_index: float = 60.0
    fatigue_warning_index: float = 80.0   # from here fatigue is a warning; between alert and warning it is context
    fatigue_rearm_s: int = 240            # no longer used by the rule since #241 (kept: a package may carry it)
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
    ff_lever_rearm_s: int = 600           # no longer used by the rule since #241 (kept: a package may carry it)
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
    # Diagnosis of a run or a drought (windows.run_causes): events of one kind needed to count as a cause, and how
    # many causes are said at most.
    cause_min_count: int = 2
    cause_max: int = 3
    # Game pace (possessions per 40 min): minimum game time before the pace, its projection and its +/- are
    # trusted (the extrapolation is very noisy in the first minutes: 45 vs 69 possessions at 3 min in a real game).
    pace_min_elapsed_s: int = 300
    # Prior weight (in possessions) of the season expectation per factor.
    ff_n0_efg: float = 40.0
    ff_n0_tov: float = 25.0
    ff_n0_orb: float = 30.0
    ff_n0_ftr: float = 40.0

    @classmethod
    def from_dict(cls, overrides: Optional[Dict[str, Any]]) -> "RuleConfig":
        """Build from a package's ``rule_config``; unknown keys are ignored."""
        known = {f.name for f in fields(cls)}
        values = {k: v for k, v in (overrides or {}).items() if k in known}
        off = values.get("rules_off")
        # JSON gives a list; the dataclass is frozen and hashable, so keep a tuple. Anything else is ignored.
        values["rules_off"] = tuple(str(r) for r in off) if isinstance(off, (list, tuple)) else ()
        return cls(**values)

    def enabled(self, rule_id: str) -> bool:
        return rule_id not in self.rules_off
