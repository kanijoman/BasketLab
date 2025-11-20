"""Calculator for player statistics values based on view mode."""

from typing import Dict, Any


class PlayerStatsCalculator:
    """Calculate player statistics values for different view modes."""

    @staticmethod
    def get_stat_value(player: Dict[str, Any], field_key: str, view_mode: str,
                       games_played: int, minutes_per_game: float) -> float:
        """
        Get the value of a statistic for a player based on the view mode.

        Args:
            player: Player statistics dictionary
            field_key: Key identifying which statistic to retrieve
            view_mode: View mode ("average", "total", or "projection")
            games_played: Number of games played
            minutes_per_game: Average minutes per game

        Returns:
            Calculated statistic value
        """
        if view_mode == "total":
            return PlayerStatsCalculator._get_total_value(player, field_key, games_played, minutes_per_game)
        elif view_mode == "projection":
            return PlayerStatsCalculator._get_projection_value(player, field_key, games_played, minutes_per_game)
        else:  # average
            return PlayerStatsCalculator._get_average_value(player, field_key, games_played, minutes_per_game)

    @staticmethod
    def _get_total_value(player: Dict[str, Any], field_key: str,
                        games_played: int, minutes_per_game: float) -> float:
        """Get total accumulated value."""
        value_map = {
            'minutes': minutes_per_game * games_played,
            'fg1_pct': player.get('fg1_percentage', 0),
            'fg2_pct': player.get('fg2_percentage', 0),
            'fg3_pct': player.get('fg3_percentage', 0),
            'points': player.get('total_pts', 0),
            'ro': player.get('total_ro', 0),
            'rd': player.get('total_rd', 0),
            'reb': player.get('total_rt', 0),
            'ast': player.get('total_assist', 0),
            'st': player.get('total_st', 0),
            'to': player.get('total_to', 0),
            'bs': player.get('total_bs', 0),
            'pf': player.get('total_pf', 0),
            'rf': player.get('total_rf', 0),
            'pllss': player.get('total_pllss', 0),
            'val': player.get('total_val', 0)
        }
        return value_map.get(field_key, 0)

    @staticmethod
    def _get_projection_value(player: Dict[str, Any], field_key: str,
                             games_played: int, minutes_per_game: float) -> float:
        """Get 30-minute projection value."""
        if field_key == 'minutes':
            return 30.0

        if field_key in ('fg1_pct', 'fg2_pct', 'fg3_pct'):
            pct_map = {
                'fg1_pct': 'fg1_percentage',
                'fg2_pct': 'fg2_percentage',
                'fg3_pct': 'fg3_percentage'
            }
            return player.get(pct_map[field_key], 0)

        multiplier = (30.0 / minutes_per_game) if minutes_per_game > 0 else 0

        value_map = {
            'points': player.get('points_per_game', 0) * multiplier,
            'ro': (player.get('total_ro', 0) / games_played if games_played > 0 else 0) * multiplier,
            'rd': (player.get('total_rd', 0) / games_played if games_played > 0 else 0) * multiplier,
            'reb': player.get('rebounds_per_game', 0) * multiplier,
            'ast': player.get('assists_per_game', 0) * multiplier,
            'st': player.get('steals_per_game', 0) * multiplier,
            'to': player.get('turnovers_per_game', 0) * multiplier,
            'bs': player.get('blocks_per_game', 0) * multiplier,
            'pf': (player.get('total_pf', 0) / games_played if games_played > 0 else 0) * multiplier,
            'rf': (player.get('total_rf', 0) / games_played if games_played > 0 else 0) * multiplier,
            'pllss': player.get('pllss_per_game', 0) * multiplier,
            'val': player.get('valoracion_per_game', 0) * multiplier
        }
        return value_map.get(field_key, 0)

    @staticmethod
    def _get_average_value(player: Dict[str, Any], field_key: str,
                          games_played: int, minutes_per_game: float) -> float:
        """Get per-game average value."""
        if field_key == 'minutes':
            return minutes_per_game

        if field_key in ('fg1_pct', 'fg2_pct', 'fg3_pct'):
            pct_map = {
                'fg1_pct': 'fg1_percentage',
                'fg2_pct': 'fg2_percentage',
                'fg3_pct': 'fg3_percentage'
            }
            return player.get(pct_map[field_key], 0)

        value_map = {
            'points': player.get('points_per_game', 0),
            'ro': player.get('total_ro', 0) / games_played if games_played > 0 else 0,
            'rd': player.get('total_rd', 0) / games_played if games_played > 0 else 0,
            'reb': player.get('rebounds_per_game', 0),
            'ast': player.get('assists_per_game', 0),
            'st': player.get('steals_per_game', 0),
            'to': player.get('turnovers_per_game', 0),
            'bs': player.get('blocks_per_game', 0),
            'pf': player.get('total_pf', 0) / games_played if games_played > 0 else 0,
            'rf': player.get('total_rf', 0) / games_played if games_played > 0 else 0,
            'pllss': player.get('pllss_per_game', 0),
            'val': player.get('valoracion_per_game', 0)
        }
        return value_map.get(field_key, 0)
