"""Advanced statistics of a team season for the MongoDB aggregation pipelines.

Every rate is defined ONCE in ``config/formulas.json`` (#1153; ``src.stats.formulas``): these functions only say where the counters of a season ``$group`` are. The field names the
pipelines of a league publish (``fg2_made``, ``rebounds_off``, ``total_possessions``...) map to the counters of the registry; the possessions are the REAL ones (#1154).
"""

from typing import Dict

from src.stats.formulas import mongo_expression

# the counters of the registry -> the fields of the season ``$group`` of FEB's pipelines
SEASON_FIELDS: Dict[str, str] = {
    "points": "$points_scored", "points_against": "$points_received",
    "fg2m": "$fg2_made", "fg2a": "$fg2_attempted", "fg3m": "$fg3_made", "fg3a": "$fg3_attempted", "fta": "$ft_attempted",
    "ast": "$assists", "stl": "$steals", "blk": "$blocks", "tov": "$turnovers",
    "orb": "$rebounds_off", "drb": "$rebounds_def", "opp_orb": "$opponent_rebounds_off", "opp_drb": "$opponent_rebounds_def",
    "poss": "$total_possessions", "opp_poss": "$opponent_possessions",
}


def _rates(*names: str, fields: Dict[str, str] = SEASON_FIELDS) -> dict:
    return {name: mongo_expression(name, fields) for name in names}


def get_four_factors() -> dict:
    """Dean Oliver's Four Factors: eFG%, TOV% (TOV / (FGA + 0.44 FTA + TOV)), ORB% (against the rival's defensive rebounds) and FTr."""
    return _rates("efg_percentage", "turnover_rate", "offensive_rebound_rate", "free_throw_rate")


def get_advanced_shooting_metrics() -> dict:
    """3Pr (share of the FGA that are threes) and TS%."""
    return _rates("three_point_rate", "true_shooting")


def get_playmaking_metrics() -> dict:
    """AST% (assisted share of the made field goals), assists per 100 own possessions, and steals and blocks per 100 RIVAL possessions (decided 27/11/2026, #1153)."""
    return _rates("assist_fg_rate", "assist_rate", "steal_rate", "block_rate")


def get_rebounding_metrics() -> dict:
    """DRB%: the team's defensive rebounds over those plus the rival's offensive ones."""
    return _rates("defensive_rebound_rate")


def get_efficiency_ratings() -> dict:
    """ORtg (points per 100 own possessions), DRtg (points allowed per 100 RIVAL possessions) and their difference."""
    return _rates("offensive_rating", "defensive_rating", "net_rating")


def get_all_advanced_stats() -> dict:
    """All the advanced statistics of a season."""
    stats = {}
    stats.update(get_four_factors())
    stats.update(get_advanced_shooting_metrics())
    stats.update(get_playmaking_metrics())
    stats.update(get_rebounding_metrics())
    stats.update(get_efficiency_ratings())
    return stats
