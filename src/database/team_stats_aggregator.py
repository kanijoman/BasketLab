"""
Team Stats Aggregator - Aggregate and calculate team statistics.

This module provides utilities for aggregating team statistics from the database
and calculating league-wide quartiles for comparative analysis.
"""

import numpy as np
from typing import Dict, List, Any, Optional


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


class TeamStatsAggregator:
    """Aggregate and calculate team statistics."""

    def __init__(self, db_handler, collection_name: str):
        """
        Initialize stats aggregator.

        Args:
            db_handler: Database handler instance
            collection_name: MongoDB collection name
        """
        self.db_handler = db_handler
        self.collection_name = collection_name

    def get_team_season_stats(self, team_name: str) -> dict:
        """
        Get team's overall season statistics from database.

        Args:
            team_name: Name of the team

        Returns:
            Dictionary with team statistics
        """
        try:
            # Get aggregated team stats
            team_stats_list = self.db_handler.get_team_stats(self.collection_name)

            # Find this team's stats
            for team_stat in team_stats_list:
                if team_stat.get('team_name') == team_name:
                    # Extract ALL available stats from the database
                    result = {
                        # Basic info
                        'games_played': safe_float(team_stat.get('total_games', 0)),

                        # Per-game stats (from basic_stats.py)
                        'points_per_game': safe_float(team_stat.get('points_per_game', 0)),
                        'points_allowed_per_game': safe_float(team_stat.get('points_allowed_per_game', 0)),
                        'rebounds_per_game': safe_float(team_stat.get('rebounds_per_game', 0)),
                        'assists_per_game': safe_float(team_stat.get('assists_per_game', 0)),
                        'steals_per_game': safe_float(team_stat.get('steals_per_game', 0)),
                        'turnovers_per_game': safe_float(team_stat.get('turnovers_per_game', 0)),
                        'blocks_per_game': safe_float(team_stat.get('blocks_per_game', 0)),
                        'possessions_per_game': safe_float(team_stat.get('possessions_per_game', 0)),

                        # Shooting percentages (from basic_stats.py)
                        'fg2_percentage': safe_float(team_stat.get('fg2_percentage', 0)),
                        'fg3_percentage': safe_float(team_stat.get('fg3_percentage', 0)),
                        'ft_percentage': safe_float(team_stat.get('ft_percentage', 0)),

                        # Four Factors (from advanced_stats.py)
                        'effective_fg_percentage': safe_float(team_stat.get('efg_percentage', 0)),
                        'true_shooting_percentage': safe_float(team_stat.get('true_shooting', 0)),
                        'turnover_rate': safe_float(team_stat.get('turnover_rate', 0)),
                        'offensive_rebound_rate': safe_float(team_stat.get('offensive_rebound_rate', 0)),
                        'free_throw_rate': safe_float(team_stat.get('free_throw_rate', 0)),

                        # Advanced shooting metrics (from advanced_stats.py)
                        'three_point_rate': safe_float(team_stat.get('three_point_rate', 0)),

                        # Playmaking metrics (from advanced_stats.py)
                        'assist_rate': safe_float(team_stat.get('assist_rate', 0)),
                        'assist_fg_rate': safe_float(team_stat.get('assist_fg_rate', 0)),
                        'steal_rate': safe_float(team_stat.get('steal_rate', 0)),
                        'block_rate': safe_float(team_stat.get('block_rate', 0)),

                        # Rebounding metrics (from advanced_stats.py)
                        'defensive_rebound_rate': safe_float(team_stat.get('defensive_rebound_rate', 0)),

                        # Efficiency ratings (from advanced_stats.py)
                        'offensive_rating': safe_float(team_stat.get('offensive_rating', 0)),
                        'defensive_rating': safe_float(team_stat.get('defensive_rating', 0)),
                        'net_rating': safe_float(team_stat.get('net_rating', 0)),

                        # Additional calculated stats
                        'pace': safe_float(team_stat.get('possessions_per_game', 0)),  # Pace is possessions per game

                        # Raw totals (for reference)
                        'total_points': safe_float(team_stat.get('points_scored', 0)),
                        'total_rebounds': safe_float(team_stat.get('total_rebounds', 0)),
                        'offensive_rebounds': safe_float(team_stat.get('rebounds_off', 0)),
                        'defensive_rebounds': safe_float(team_stat.get('rebounds_def', 0)),
                    }

                    return result

            # Return empty dict if team not found
            return {}

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {}

    def calculate_league_quartiles(self) -> dict:
        """
        Calculate quartiles for all statistics across the league.

        Returns:
            Dictionary with stat names as keys, each containing q1, q2 (median), q3, min, max
        """
        try:
            # Get all teams' stats
            team_stats_list = self.db_handler.get_team_stats(self.collection_name)

            if not team_stats_list:
                return {}

            # Stat fields to calculate quartiles for (comprehensive list from basic_stats + advanced_stats)
            stat_fields = [
                # Per-game stats
                'points_per_game', 'points_allowed_per_game', 'rebounds_per_game',
                'assists_per_game', 'steals_per_game', 'turnovers_per_game', 'blocks_per_game',
                'possessions_per_game',
                # Shooting percentages
                'fg2_percentage', 'fg3_percentage', 'ft_percentage',
                # Four Factors
                'efg_percentage', 'true_shooting', 'turnover_rate',
                'offensive_rebound_rate', 'free_throw_rate',
                # Advanced shooting
                'three_point_rate',
                # Playmaking
                'assist_rate', 'assist_fg_rate', 'steal_rate', 'block_rate',
                # Rebounding
                'defensive_rebound_rate',
                # Efficiency
                'offensive_rating', 'defensive_rating', 'net_rating'
            ]

            quartiles = {}

            for stat_field in stat_fields:
                # Extract values for this stat from all teams
                values = []
                for team_stat in team_stats_list:
                    value = team_stat.get(stat_field, None)
                    if value is not None:  # Include zero values, just exclude None/missing
                        try:
                            values.append(float(value))
                        except (ValueError, TypeError):
                            pass  # Skip invalid values

                if len(values) >= 4:  # Need at least 4 teams for meaningful quartiles
                    values.sort()
                    n = len(values)

                    # Calculate quartiles using numpy.percentile
                    q1_value = np.percentile(values, 25)
                    q2_value = np.percentile(values, 50)
                    q3_value = np.percentile(values, 75)

                    quartiles[stat_field] = {
                        'min': values[0],
                        'q1': q1_value,
                        'q2': q2_value,  # median
                        'q3': q3_value,
                        'max': values[-1],
                        'count': n
                    }

            return quartiles

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {}
