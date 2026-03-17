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


def get_possessions_calculation() -> dict:
    """
    Calculate possessions per match adjusted for game duration (including overtime).
    Formula: (FGA2 + FGA3 + (0.45 * FTA) + TO - OREB) * (40 / total_minutes)

    Total minutes is calculated from the number of quarters:
    - 4 quarters = 40 minutes (regular game)
    - 5 quarters = 45 minutes (1 overtime)
    - 6 quarters = 50 minutes (2 overtimes), etc.

    Returns:
        MongoDB expression for possessions calculation
    """
    raw_possessions = {
        "$add": [
            {"$toInt": "$BOXSCORE.TEAM.TOTAL.p2a"},
            {"$toInt": "$BOXSCORE.TEAM.TOTAL.p3a"},
            {"$multiply": [0.45, {"$toInt": "$BOXSCORE.TEAM.TOTAL.p1a"}]},
            {"$toInt": "$BOXSCORE.TEAM.TOTAL.to"},
            {"$multiply": [-1, {"$toInt": "$BOXSCORE.TEAM.TOTAL.ro"}]}
        ]
    }

    # Calculate total minutes based on number of quarters
    # Each quarter = 10 min, overtime = 5 min
    # Total minutes = (num_quarters - 4) * 5 + 40
    num_quarters = {"$size": "$HEADER.QUARTERS.QUARTER"}
    total_minutes = {
        "$add": [
            40,
            {"$multiply": [
                {"$subtract": [num_quarters, 4]},
                5
            ]}
        ]
    }

    # Adjust possessions: raw_possessions * (40 / total_minutes)
    return {
        "$multiply": [
            raw_possessions,
            {"$divide": [40, total_minutes]}
        ]
    }
