"""Thresholds of the rule-based report engine (placeholders to confirm with the staff)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ReportConfig:
    # |value - league median| / median, in %, to report a differential
    diff_threshold_pct: float = 10.0
    # coefficient of variation (%) above / below which a stat is (in)consistent
    cv_inconsistent: float = 30.0
    cv_consistent: float = 15.0
    # minimum number of games behind a CV to trust it
    min_games_cv: int = 5
    max_training_items: int = 5
    max_tactics: int = 6
    # rival game plan: items per kind (neutralize / exploit)
    max_plan_each: int = 3
