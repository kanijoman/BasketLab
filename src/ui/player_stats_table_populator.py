"""Table population utilities for player statistics."""

from typing import Dict, List, Any
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem

from .table_items import NumericTableWidgetItem
from .stats_config import calculate_quartiles, get_quartile_color
from .player_stats_calculator import PlayerStatsCalculator


class PlayerStatsTablePopulator:
    """Handles population of player statistics table."""

    # Field definitions for quartile calculation and coloring
    STAT_FIELDS = {
        3: ('minutes', False),  # Min
        4: ('points', False),   # Pts
        5: ('fg1_pct', False),  # %TL
        6: ('fg2_pct', False),  # %T2
        7: ('fg3_pct', False),  # %T3
        8: ('ro', False),       # RO
        9: ('rd', False),       # RD
        10: ('reb', False),     # Reb
        11: ('ast', False),     # Ast
        12: ('st', False),      # Rob
        13: ('to', True),       # BP (reverse - less is better)
        14: ('bs', False),      # Tap
        15: ('pf', True),       # FP (reverse)
        16: ('rf', False),      # FR
        17: ('pllss', False),   # +/-
        18: ('val', False)      # Val
    }

    @staticmethod
    def calculate_quartiles(all_players: List[Dict[str, Any]], view_mode: str) -> Dict[int, List[float]]:
        """
        Calculate quartiles for all statistics based on all players.

        Args:
            all_players: List of all player statistics
            view_mode: Current view mode ("average", "total", "projection")

        Returns:
            Dictionary mapping column index to quartile values [Q1, Q2, Q3]
        """
        quartiles = {}

        for col_idx, (field_key, _) in PlayerStatsTablePopulator.STAT_FIELDS.items():
            values = []
            for player in all_players:
                games_played = player.get('games_played', 0)
                minutes_per_game = player.get('minutes_per_game', 0)

                val = PlayerStatsCalculator.get_stat_value(
                    player, field_key, view_mode, games_played, minutes_per_game
                )
                values.append(val)

            if len(values) >= 4:
                quartiles[col_idx] = calculate_quartiles(values)

        return quartiles

    @staticmethod
    def populate_table(table: QTableWidget, filtered_stats: List[Dict[str, Any]],
                      view_mode: str, quartiles: Dict[int, List[float]]):
        """
        Populate table with player statistics.

        Args:
            table: QTableWidget to populate
            filtered_stats: List of filtered player statistics to display
            view_mode: Current view mode
            quartiles: Pre-calculated quartiles for coloring
        """
        table.setSortingEnabled(False)
        table.setRowCount(len(filtered_stats))

        for row, player in enumerate(filtered_stats):
            PlayerStatsTablePopulator._populate_row(
                table, row, player, view_mode, quartiles
            )

        table.setSortingEnabled(True)

    @staticmethod
    def _populate_row(table: QTableWidget, row: int, player: Dict[str, Any],
                     view_mode: str, quartiles: Dict[int, List[float]]):
        """Populate a single row in the table."""
        games_played = player.get('games_played', 0)
        minutes_per_game = player.get('minutes_per_game', 0)

        # Player name (col 0)
        table.setItem(row, 0, QTableWidgetItem(str(player.get('player_name', ''))))

        # Team name (col 1)
        table.setItem(row, 1, QTableWidgetItem(str(player.get('team_name', ''))))

        # Games played (col 2)
        table.setItem(row, 2, NumericTableWidgetItem(games_played, str(games_played)))

        # Minutes (col 3)
        PlayerStatsTablePopulator._add_minutes_cell(
            table, row, player, view_mode, games_played, minutes_per_game, quartiles
        )

        # Points (col 4)
        PlayerStatsTablePopulator._add_points_cell(
            table, row, player, view_mode, games_played, minutes_per_game, quartiles
        )

        # Shooting stats (cols 5-7)
        PlayerStatsTablePopulator._add_shooting_cells(
            table, row, player, view_mode, quartiles
        )

        # Other stats (cols 8-18)
        PlayerStatsTablePopulator._add_stat_cells(
            table, row, player, view_mode, games_played, minutes_per_game, quartiles
        )

    @staticmethod
    def _add_minutes_cell(table: QTableWidget, row: int, player: Dict[str, Any],
                         view_mode: str, games_played: int, minutes_per_game: float,
                         quartiles: Dict[int, List[float]]):
        """Add minutes cell with appropriate formatting."""
        if view_mode == "total":
            total_minutes = minutes_per_game * games_played
            item = NumericTableWidgetItem(total_minutes, f"{total_minutes:.0f}")
        elif view_mode == "projection":
            item = NumericTableWidgetItem(30.0, "30.0")
        else:
            item = NumericTableWidgetItem(minutes_per_game, f"{minutes_per_game:.1f}")

        if 3 in quartiles:
            item.setBackground(get_quartile_color(
                item._numeric_value, quartiles[3],
                PlayerStatsTablePopulator.STAT_FIELDS[3][1]
            ))
        table.setItem(row, 3, item)

    @staticmethod
    def _add_points_cell(table: QTableWidget, row: int, player: Dict[str, Any],
                        view_mode: str, games_played: int, minutes_per_game: float,
                        quartiles: Dict[int, List[float]]):
        """Add points cell with appropriate formatting."""
        pts = PlayerStatsCalculator.get_stat_value(
            player, 'points', view_mode, games_played, minutes_per_game
        )

        item = NumericTableWidgetItem(pts, f"{pts:.1f}")
        if 4 in quartiles:
            item.setBackground(get_quartile_color(
                pts, quartiles[4],
                PlayerStatsTablePopulator.STAT_FIELDS[4][1]
            ))
        table.setItem(row, 4, item)

    @staticmethod
    def _add_shooting_cells(table: QTableWidget, row: int, player: Dict[str, Any],
                           view_mode: str, quartiles: Dict[int, List[float]]):
        """Add shooting percentage/totals cells (cols 5-7)."""
        shooting_stats = [
            (5, 'total_p1m', 'total_p1a', 'fg1_percentage'),
            (6, 'total_p2m', 'total_p2a', 'fg2_percentage'),
            (7, 'total_p3m', 'total_p3a', 'fg3_percentage')
        ]

        for col, made_key, att_key, pct_key in shooting_stats:
            pct = player.get(pct_key, 0)

            if view_mode == "total":
                # Show as "made-attempted" for totals
                made = player.get(made_key, 0)
                att = player.get(att_key, 0)
                item = NumericTableWidgetItem(pct, f"{made}-{att}")
            else:
                # Show as percentage for averages and projection
                item = NumericTableWidgetItem(pct, f"{pct:.1f}")

            if col in quartiles:
                item.setBackground(get_quartile_color(
                    pct, quartiles[col],
                    PlayerStatsTablePopulator.STAT_FIELDS[col][1]
                ))
            table.setItem(row, col, item)

    @staticmethod
    def _add_stat_cells(table: QTableWidget, row: int, player: Dict[str, Any],
                       view_mode: str, games_played: int, minutes_per_game: float,
                       quartiles: Dict[int, List[float]]):
        """Add remaining statistics cells (cols 8-18)."""
        # Define column mappings
        stat_mappings = [
            (8, 'total_ro', 'ro', False),        # RO
            (9, 'total_rd', 'rd', False),        # RD
            (10, 'total_rt', 'reb', False),      # Reb
            (11, 'total_assist', 'ast', False),  # Ast
            (12, 'total_st', 'st', False),       # Rob
            (13, 'total_to', 'to', True),        # BP (reverse)
            (14, 'total_bs', 'bs', False),       # Tap
            (15, 'total_pf', 'pf', True),        # FP (reverse)
            (16, 'total_rf', 'rf', False),       # FR
            (17, 'total_pllss', 'pllss', False), # +/-
            (18, 'total_val', 'val', False)      # Val
        ]

        for col, total_key, field_key, reverse in stat_mappings:
            val = PlayerStatsCalculator.get_stat_value(
                player, field_key, view_mode, games_played, minutes_per_game
            )

            # Special formatting for +/-
            if col == 17:
                text = f"+{val:.1f}" if val > 0 else f"{val:.1f}"
            else:
                text = f"{val:.1f}"

            item = NumericTableWidgetItem(val, text)
            if col in quartiles:
                item.setBackground(get_quartile_color(val, quartiles[col], reverse))
            table.setItem(row, col, item)
