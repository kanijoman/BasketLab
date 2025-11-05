"""Advanced statistics calculations for MongoDB aggregation pipeline."""

from ..utils import safe_divide


def get_four_factors() -> dict:
    """
    Calculate Dean Oliver's Four Factors of Basketball Success:
    - eFG%: Effective Field Goal Percentage
    - TOV%: Turnover Rate
    - ORB%: Offensive Rebound Rate
    - FTr: Free Throw Rate

    Returns:
        Dictionary with field definitions for Four Factors
    """
    total_fga = {"$add": ["$fg2_attempted", "$fg3_attempted"]}

    return {
        "efg_percentage": {
            "$multiply": [
                safe_divide(
                    {"$add": ["$fg2_made", {"$multiply": [1.5, "$fg3_made"]}]},
                    total_fga
                ),
                100
            ]
        },
        "turnover_rate": {
            "$multiply": [
                safe_divide("$turnovers", "$total_possessions"),
                100
            ]
        },
        "offensive_rebound_rate": {
            "$multiply": [
                safe_divide(
                    "$rebounds_off",
                    {"$add": ["$rebounds_off", "$opponent_rebounds_def"]}
                ),
                100
            ]
        },
        "free_throw_rate": {
            "$multiply": [
                safe_divide("$ft_attempted", total_fga),
                100
            ]
        }
    }


def get_advanced_shooting_metrics() -> dict:
    """
    Calculate advanced shooting metrics:
    - 3Pr: Three Point Rate (% of FGA that are 3-pointers)
    - TS%: True Shooting Percentage

    Returns:
        Dictionary with field definitions for advanced shooting metrics
    """
    total_fga = {"$add": ["$fg2_attempted", "$fg3_attempted"]}

    return {
        "three_point_rate": {
            "$multiply": [
                safe_divide("$fg3_attempted", total_fga),
                100
            ]
        },
        "true_shooting": {
            "$multiply": [
                safe_divide(
                    "$points_scored",
                    {"$multiply": [2, {"$add": [total_fga, {"$multiply": [0.44, "$ft_attempted"]}]}]}
                ),
                100
            ]
        }
    }


def get_playmaking_metrics() -> dict:
    """
    Calculate playmaking and ball control metrics:
    - AST%: Assist Rate (% of made field goals that were assisted)
    - ROB%: Steal Rate
    - TAP%: Block Rate

    Returns:
        Dictionary with field definitions for playmaking metrics
    """
    total_fg_made = {"$add": ["$fg2_made", "$fg3_made"]}

    return {
        "assist_fg_rate": {
            "$multiply": [
                safe_divide("$assists", total_fg_made),
                100
            ]
        },
        "assist_rate": {
            "$multiply": [
                safe_divide(
                    {"$multiply": ["$assists", 100]},
                    "$total_possessions"
                ),
                1
            ]
        },
        "steal_rate": {
            "$multiply": [
                safe_divide(
                    {"$multiply": ["$steals", 100]},
                    "$total_possessions"
                ),
                1
            ]
        },
        "block_rate": {
            "$multiply": [
                safe_divide(
                    {"$multiply": ["$blocks", 100]},
                    "$total_possessions"
                ),
                1
            ]
        }
    }


def get_rebounding_metrics() -> dict:
    """
    Calculate rebounding metrics:
    - DRB%: Defensive Rebound Rate

    Formula: DRB% = (Team Defensive Rebounds / (Team Defensive Rebounds + Opponent Offensive Rebounds)) × 100

    Returns:
        Dictionary with field definitions for rebounding metrics
    """
    return {
        "defensive_rebound_rate": {
            "$multiply": [
                safe_divide(
                    "$rebounds_def",
                    {"$add": ["$rebounds_def", "$opponent_rebounds_off"]}
                ),
                100
            ]
        }
    }


def get_efficiency_ratings() -> dict:
    """
    Calculate efficiency ratings:
    - OER: Offensive Efficiency Rating (points per 100 possessions)
    - DER: Defensive Efficiency Rating (points allowed per 100 possessions)
    - Net Rating: Difference between OER and DER

    Returns:
        Dictionary with field definitions for efficiency ratings
    """
    offensive_rating = {
        "$cond": [
            {"$eq": ["$total_possessions", 0]},
            0,
            {"$multiply": [
                {"$divide": ["$points_scored", "$total_possessions"]},
                100
            ]}
        ]
    }

    defensive_rating = {
        "$cond": [
            {"$eq": ["$total_possessions", 0]},
            0,
            {"$multiply": [
                {"$divide": ["$points_received", "$total_possessions"]},
                100
            ]}
        ]
    }

    return {
        "offensive_rating": offensive_rating,
        "defensive_rating": defensive_rating,
        "net_rating": {
            "$cond": [
                {"$eq": ["$total_possessions", 0]},
                0,
                {"$subtract": [offensive_rating, defensive_rating]}
            ]
        }
    }


def get_all_advanced_stats() -> dict:
    """
    Get all advanced statistics combined.

    Returns:
        Dictionary with all advanced statistics field definitions
    """
    stats = {}
    stats.update(get_four_factors())
    stats.update(get_advanced_shooting_metrics())
    stats.update(get_playmaking_metrics())
    stats.update(get_rebounding_metrics())
    stats.update(get_efficiency_ratings())
    return stats
