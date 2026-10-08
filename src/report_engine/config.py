"""Thresholds of the rule-based report engine (placeholders to confirm with the staff)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ReportConfig:
    # |value - league median| / median, in %, to report a differential
    diff_threshold_pct: float = 10.0
    # coefficient of variation (%) above / below which a stat is (in)consistent
    cv_inconsistent: float = 30.0
    cv_consistent: float = 15.0
    # a CV needs at least 2 games (1 game has no variability); no other minimum, so the
    # report is useful from the first matchdays
    min_games_cv: int = 2
    # below this many games everything is flagged as low reliability (early season)
    low_sample_games: int = 5
    max_training_items: int = 5
    max_tactics: int = 6
    # rival game plan: items per kind (neutralize / exploit)
    max_plan_each: int = 3
