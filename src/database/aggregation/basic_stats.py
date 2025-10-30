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
    return {
        "points_per_game": {"$divide": ["$points_scored", "$total_games"]},
        "points_against_per_game": {"$divide": ["$points_received", "$total_games"]},
        "possessions_per_game": {"$divide": ["$total_possessions", "$total_games"]}
    }


def get_possessions_calculation() -> dict:
    """
    Calculate possessions per match: FGA2 + FGA3 + (0.45 * FTA) + TO - OREB.

    Returns:
        MongoDB expression for possessions calculation
    """
    return {
        "$add": [
            {"$toInt": "$BOXSCORE.TEAM.TOTAL.p2a"},
            {"$toInt": "$BOXSCORE.TEAM.TOTAL.p3a"},
            {"$multiply": [0.45, {"$toInt": "$BOXSCORE.TEAM.TOTAL.p1a"}]},
            {"$toInt": "$BOXSCORE.TEAM.TOTAL.to"},
            {"$multiply": [-1, {"$toInt": "$BOXSCORE.TEAM.TOTAL.ro"}]}
        ]
    }
