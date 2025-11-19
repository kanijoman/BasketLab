"""Advanced statistics calculations for MongoDB aggregation pipeline."""

from typing import Dict, Any
from ..utils import safe_divide


def _percentage_metric(numerator, denominator) -> Dict:
    """
    Create a percentage metric (value * 100).

    Args:
        numerator: Numerator expression
        denominator: Denominator expression

    Returns:
        MongoDB expression for percentage calculation
    """
    return {
        "$multiply": [
            safe_divide(numerator, denominator),
            100
        ]
    }


def _rate_per_100_possessions(value: str) -> Dict:
    """
    Calculate a rate per 100 possessions.

    Args:
        value: Field name for the value to calculate rate for (with or without $ prefix)

    Returns:
        MongoDB expression for rate per 100 possessions
    """
    # Ensure the value has the $ prefix
    field_ref = value if value.startswith("$") else f"${value}"

    return {
        "$multiply": [
            safe_divide(
                {"$multiply": [field_ref, 100]},
                "$total_possessions"
            ),
            1
        ]
    }


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
        "efg_percentage": _percentage_metric(
            {"$add": ["$fg2_made", {"$multiply": [1.5, "$fg3_made"]}]},
            total_fga
        ),
        "turnover_rate": _percentage_metric("$turnovers", "$total_possessions"),
        "offensive_rebound_rate": _percentage_metric(
            "$rebounds_off",
            {"$add": ["$rebounds_off", "$opponent_rebounds_def"]}
        ),
        "free_throw_rate": _percentage_metric("$ft_attempted", total_fga)
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
        "three_point_rate": _percentage_metric("$fg3_attempted", total_fga),
        "true_shooting": _percentage_metric(
            "$points_scored",
            {"$multiply": [2, {"$add": [total_fga, {"$multiply": [0.44, "$ft_attempted"]}]}]}
        )
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
        "assist_fg_rate": _percentage_metric("$assists", total_fg_made),
        "assist_rate": _rate_per_100_possessions("$assists"),
        "steal_rate": _rate_per_100_possessions("$steals"),
        "block_rate": _rate_per_100_possessions("$blocks")
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
        "defensive_rebound_rate": _percentage_metric(
            "$rebounds_def",
            {"$add": ["$rebounds_def", "$opponent_rebounds_off"]}
        )
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
            {"$eq": ["$opponent_possessions", 0]},
            0,
            {"$multiply": [
                {"$divide": ["$points_received", "$opponent_possessions"]},
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
