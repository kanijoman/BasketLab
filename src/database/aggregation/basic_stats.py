"""Basic statistics calculations for MongoDB aggregation pipeline."""

from ..utils import safe_divide


def get_shooting_percentages() -> dict:
    """
    Calculate shooting percentages (FG2%, FG3%, FT%).

    Returns:
        Dictionary with field definitions for shooting percentages
    """
    return {
        "fg2_percentage": {
            "$multiply": [
                safe_divide("$fg2_made", "$fg2_attempted"),
                100
            ]
        },
        "fg3_percentage": {
            "$multiply": [
                safe_divide("$fg3_made", "$fg3_attempted"),
                100
            ]
        },
        "ft_percentage": {
            "$multiply": [
                safe_divide("$ft_made", "$ft_attempted"),
                100
            ]
        }
    }


def get_per_game_stats() -> dict:
    """
    Calculate per-game statistics.

    Returns:
        Dictionary with field definitions for per-game stats
    """
    # Inline the total rebound sum so this works even when total_rebounds is
    # computed in the same $addFields stage (MongoDB evaluates all expressions
    # against the *input* document, not sibling computed fields).
    _reb_total = {"$add": ["$rebounds_def", "$rebounds_off"]}

    return {
        "points_per_game": {"$divide": ["$points_scored", "$total_games"]},
        "points_against_per_game": {"$divide": ["$points_received", "$total_games"]},
        "points_allowed_per_game": {"$divide": ["$points_received", "$total_games"]},  # Alias for compatibility
        "possessions_per_game": {"$divide": ["$total_possessions", "$total_games"]},
        "rebounds_per_game": {"$divide": [_reb_total, "$total_games"]},
        "offensive_rebounds_per_game": {"$divide": ["$rebounds_off", "$total_games"]},
        "defensive_rebounds_per_game": {"$divide": ["$rebounds_def", "$total_games"]},
        "assists_per_game": {"$divide": ["$assists", "$total_games"]},
        "steals_per_game": {"$divide": ["$steals", "$total_games"]},
        "turnovers_per_game": {"$divide": ["$turnovers", "$total_games"]},
        "blocks_per_game": {"$divide": ["$blocks", "$total_games"]}
    }
