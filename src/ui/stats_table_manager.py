"""Table population and management for statistics display.

This module provides the StatsTableManager class which handles populating
QTableWidget instances with basketball statistics. It manages:
- Basic statistics tables with color-coded quartiles
- Advanced statistics tables with trend indicators
- Comparative tables (monthly vs rest, home vs away, won vs lost)
- Last match comparison tables

The manager uses trend indicators (arrows) and background colors to provide
visual insights into team performance and trends.
"""

from PyQt6.QtWidgets import QTableWidget, QLabel, QTableWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from typing import Dict, List, Tuple

from .table_items import NumericTableWidgetItem, process_numeric_value
from .stats_config import (
    PERCENTAGE_FIELDS, NON_PERCENTAGE_FIELDS,
    get_basic_stats_config, get_advanced_stats_config,
    get_quartile_color
)
from .trend_calculator import TrendCalculator


class StatsTableManager:
    """Manage table population and updates for statistics display."""

    def __init__(self, trend_calculator: TrendCalculator):
        """
        Initialize table manager.

        Args:
            trend_calculator: TrendCalculator instance for trend indicators
        """
        self.trend_calculator = trend_calculator

    def populate_basic_stats_row(self, table: QTableWidget, row: int, team: Dict,
                                 numeric_data: Dict, quartiles: Dict):
        """
        Populate a row in the basic statistics table.

        Args:
            table: Table widget to populate
            row: Row index
            team: Team statistics dictionary
            numeric_data: Numeric data for all teams
            quartiles: Quartile data for coloring
        """
        # Set team info columns explicitly (indices 0-3)
        table.setItem(row, 0, NumericTableWidgetItem(team["team_name"], team["team_name"], False))
        table.setItem(row, 1, NumericTableWidgetItem(team["total_games"], str(team["total_games"])))
        table.setItem(row, 2, NumericTableWidgetItem(team["games_home"], str(team["games_home"])))
        table.setItem(row, 3, NumericTableWidgetItem(team["games_away"], str(team["games_away"])))

        # Set numeric stats columns (indices 4+)
        stats_config = get_basic_stats_config(team)

        for idx, key, raw_value in stats_config:
            num_value, display_value = process_numeric_value(raw_value, key)

            # Add percentage symbol if needed
            if key in PERCENTAGE_FIELDS:
                display_value = f"{display_value}%"

            # Determine background color based on quartile
            bg_color = None
            if key in numeric_data and key in quartiles:
                reverse = key in {"turnover_percentage", "points_allowed_per_game"}
                bg_color = get_quartile_color(num_value, quartiles[key], reverse)

            item = NumericTableWidgetItem(num_value, display_value)

            if bg_color:
                item.setBackground(QColor(bg_color))

            table.setItem(row, idx, item)

    def populate_advanced_stats_row(self, table: QTableWidget, row: int, team: Dict,
                                   numeric_data: Dict, quartiles: Dict):
        """
        Populate a row in the advanced statistics table.

        Args:
            table: Table widget to populate
            row: Row index
            team: Team statistics dictionary
            numeric_data: Numeric data for all teams
            quartiles: Quartile data for coloring
        """
        # Set team info columns explicitly (indices 0-1)
        table.setItem(row, 0, NumericTableWidgetItem(team["team_name"], team["team_name"], False))
        table.setItem(row, 1, NumericTableWidgetItem(team["total_games"], str(team["total_games"])))

        # Set numeric stats columns (indices 2+)
        stats_config = get_advanced_stats_config(team)

        for idx, key, raw_value in stats_config:
            num_value, display_value = process_numeric_value(raw_value, key)

            # Add percentage symbol if needed
            if key not in NON_PERCENTAGE_FIELDS:
                display_value = f"{display_value}%"

            # Determine background color based on quartile
            bg_color = None
            if key in numeric_data and key in quartiles:
                reverse = key in {
                    "defensive_rating", "turnover_rate", "points_allowed_per_game"
                }
                bg_color = get_quartile_color(num_value, quartiles[key], reverse)

            item = NumericTableWidgetItem(num_value, display_value)

            if bg_color:
                item.setBackground(QColor(bg_color))

            table.setItem(row, idx, item)

    def populate_comparative_basic_row(self, table: QTableWidget, row: int, comp_stat: Dict,
                                      numeric_data: Dict, quartiles: Dict):
        """
        Populate a row with comparative statistics (monthly vs rest).

        Args:
            table: Table widget to populate
            row: Row index
            comp_stat: Comparative statistics dictionary with structure:
                       {"team_name": ..., "monthly": {...}, "rest": {...}, "deltas": {...}}
            numeric_data: Numeric data for all teams
            quartiles: Quartile data for coloring
        """
        monthly = comp_stat.get("monthly", {})
        rest = comp_stat.get("rest", {})
        deltas = comp_stat.get("deltas", {})

        # Team name
        team_name = monthly.get("team_name", "Unknown")
        table.setItem(row, 0, NumericTableWidgetItem(team_name, team_name, False))

        # Total games (show monthly + rest)
        total_games = monthly.get("total_games", 0) + rest.get("total_games", 0)
        games_text = f"{monthly.get('total_games', 0)} + {rest.get('total_games', 0)}"
        table.setItem(row, 1, NumericTableWidgetItem(total_games, games_text))

        # Local games (monthly + rest)
        local_games = monthly.get("games_home", 0) + rest.get("games_home", 0)
        local_text = f"{monthly.get('games_home', 0)} + {rest.get('games_home', 0)}"
        table.setItem(row, 2, NumericTableWidgetItem(local_games, local_text))

        # Away games (monthly + rest)
        away_games = monthly.get("games_away", 0) + rest.get("games_away", 0)
        away_text = f"{monthly.get('games_away', 0)} + {rest.get('games_away', 0)}"
        table.setItem(row, 3, NumericTableWidgetItem(away_games, away_text))

        # For other numeric columns, show monthly value with trend indicator
        basic_stats_config = get_basic_stats_config(monthly)

        for idx, key, raw_value in basic_stats_config:
            if idx < 4:  # Skip team_name, total_games, games_home, games_away (already set)
                continue

            num_value, display_value = process_numeric_value(raw_value, key)

            # Add percentage symbol if needed
            if key in PERCENTAGE_FIELDS:
                display_value = f"{display_value}%"

            # Add trend indicator with color
            if key in deltas:
                delta = deltas[key]
                trend_symbol, trend_color = self.trend_calculator.get_trend_indicator(delta, key)

                cell_widget, item = self._create_trend_cell_widget(
                    display_value, trend_symbol, trend_color, num_value,
                    key, numeric_data, quartiles
                )
                table.setCellWidget(row, idx, cell_widget)
                table.setItem(row, idx, item)
            else:
                # No trend data available - show "—" indicator
                trend_symbol, trend_color = self.trend_calculator.get_no_data_indicator()
                cell_widget, item = self._create_trend_cell_widget(
                    display_value, trend_symbol, trend_color, num_value,
                    key, numeric_data, quartiles
                )
                cell_widget.setProperty("title", "Sin datos para comparar")
                table.setCellWidget(row, idx, cell_widget)
                table.setItem(row, idx, item)

    def populate_comparative_advanced_row(self, table: QTableWidget, row: int, comp_stat: Dict,
                                         numeric_data: Dict, quartiles: Dict):
        """
        Populate a row with comparative advanced statistics.

        Args:
            table: Table widget to populate
            row: Row index
            comp_stat: Comparative statistics dictionary with structure:
                       {"team_name": ..., "monthly": {...}, "rest": {...}, "deltas": {...}}
            numeric_data: Numeric data for all teams
            quartiles: Quartile data for coloring
        """
        monthly = comp_stat.get("monthly", {})
        rest = comp_stat.get("rest", {})
        deltas = comp_stat.get("deltas", {})

        # Team name and games
        team_name = monthly.get("team_name", "Unknown")
        total_games = monthly.get("total_games", 0) + rest.get("total_games", 0)
        games_text = f"{monthly.get('total_games', 0)} + {rest.get('total_games', 0)}"

        table.setItem(row, 0, NumericTableWidgetItem(team_name, team_name, False))
        table.setItem(row, 1, NumericTableWidgetItem(total_games, games_text))

        # Get advanced stats configuration
        advanced_stats_config = get_advanced_stats_config(monthly)

        for idx, key, raw_value in advanced_stats_config:
            num_value, display_value = process_numeric_value(raw_value, key)

            # Add percentage symbol if needed
            if key not in NON_PERCENTAGE_FIELDS:
                display_value = f"{display_value}%"

            # Add trend indicator with color
            if key in deltas:
                delta = deltas[key]
                trend_symbol, trend_color = self.trend_calculator.get_trend_indicator(delta, key)

                # Determine reverse flag for quartile coloring
                reverse = key in {"defensive_rating", "turnover_rate"}

                cell_widget, item = self._create_trend_cell_widget(
                    display_value, trend_symbol, trend_color, num_value,
                    key, numeric_data, quartiles, reverse
                )
                table.setCellWidget(row, idx, cell_widget)
                table.setItem(row, idx, item)
            else:
                # No trend data available - show "—" indicator
                trend_symbol, trend_color = self.trend_calculator.get_no_data_indicator()

                # Determine reverse flag for quartile coloring
                reverse = key in {"defensive_rating", "turnover_rate"}

                cell_widget, item = self._create_trend_cell_widget(
                    display_value, trend_symbol, trend_color, num_value,
                    key, numeric_data, quartiles, reverse
                )
                cell_widget.setProperty("title", "Sin datos para comparar")
                table.setCellWidget(row, idx, cell_widget)
                table.setItem(row, idx, item)

    def populate_last_match_row(self, table: QTableWidget, row: int, team_stats: Dict,
                               opponent_stats: Dict, season_stats: Dict, is_selected_team: bool,
                               is_basic: bool = False):
        """
        Populate a row in the table for last match comparison.

        Args:
            table: Table widget to populate
            row: Row index
            team_stats: Match stats for this team
            opponent_stats: Match stats for the opponent
            season_stats: Season stats for trend calculation
            is_selected_team: Whether this is the selected team row
            is_basic: Whether this is the basic stats table
        """
        # Team name
        team_name = team_stats["team_name"]
        table.setItem(row, 0, NumericTableWidgetItem(team_name, team_name, False))

        # Get stats configuration based on table type
        if is_basic:
            table.setItem(row, 1, NumericTableWidgetItem(1, "1"))  # Total games
            table.setItem(row, 2, NumericTableWidgetItem(1 if is_selected_team else 0,
                                                         "1" if is_selected_team else "0"))  # Games home
            table.setItem(row, 3, NumericTableWidgetItem(0 if is_selected_team else 1,
                                                         "0" if is_selected_team else "1"))  # Games away
            stats_config = get_basic_stats_config(team_stats)
        else:
            table.setItem(row, 1, NumericTableWidgetItem(1, "1"))
            stats_config = get_advanced_stats_config(team_stats)

        # Define which stats are "higher is better"
        higher_is_better = {
            "points_per_game", "fg2_percentage", "fg3_percentage", "ft_percentage",
            "fg_percentage", "efg_percentage", "true_shooting", "assists_per_game",
            "steals_per_game", "blocks_per_game", "offensive_rating", "net_rating",
            "rebounds_per_game", "oreb_percentage", "possessions_per_game",
            "offensive_rebound_rate", "three_point_rate", "free_throw_rate",
            "assist_fg_rate", "assist_rate", "steal_rate", "block_rate",
            "points_scored", "total_rebounds", "rebounds_def", "rebounds_off",
            "assists", "steals", "blocks"
        }

        lower_is_better = {
            "defensive_rating", "turnover_rate", "turnovers_per_game",
            "points_against_per_game", "points_received", "turnovers"
        }

        # Process each stat
        for idx, key, raw_value in stats_config:
            if is_basic and idx < 4:
                continue
            elif not is_basic and idx < 2:
                continue

            num_value, display_value = process_numeric_value(raw_value, key)

            # Add percentage symbol
            if is_basic:
                if key in PERCENTAGE_FIELDS:
                    display_value = f"{display_value}%"
            else:
                if key not in NON_PERCENTAGE_FIELDS:
                    display_value = f"{display_value}%"

            # Get opponent value for comparison
            opponent_value = opponent_stats.get(key, 0)

            # Determine comparison color
            if abs(num_value - opponent_value) < 0.01:
                bg_color = "#D3D3D3"  # Gray
            elif key in higher_is_better:
                bg_color = "#90EE90" if num_value > opponent_value else "#FFB6C1"
            elif key in lower_is_better:
                bg_color = "#90EE90" if num_value < opponent_value else "#FFB6C1"
            else:
                bg_color = "#90EE90" if num_value > opponent_value else "#FFB6C1"

            # Calculate trend vs season average
            trend_symbol = ""
            trend_color = "gray"

            if season_stats and key in season_stats:
                season_value = season_stats.get(key, 0)

                if isinstance(season_value, (int, float)) and season_value != 0:
                    delta = ((num_value - season_value) / abs(season_value)) * 100
                    trend_symbol, trend_color = self.trend_calculator.get_trend_indicator(
                        delta, key, is_opponent=False
                    )

            # Create cell widget with color and trend
            cell_label = QLabel()
            cell_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            cell_label.setStyleSheet(f"background-color: {bg_color}; padding: 4px;")

            if trend_symbol:
                cell_label.setText(
                    f'{display_value} <span style="color: {trend_color}; font-weight: bold;">{trend_symbol}</span>'
                )
            else:
                cell_label.setText(display_value)

            item = NumericTableWidgetItem(num_value, "")

            table.setCellWidget(row, idx, cell_label)
            table.setItem(row, idx, item)

    def _create_trend_cell_widget(self, display_value: str, trend_symbol: str, trend_color: str,
                                  num_value: float, key: str, numeric_data: Dict, quartiles: Dict,
                                  reverse_flag: bool = None) -> Tuple[QLabel, QTableWidgetItem]:
        """
        Create a cell widget with trend indicator and background color.

        Args:
            display_value: Display string for the value
            trend_symbol: Trend symbol (arrows)
            trend_color: Color for the trend symbol
            num_value: Numeric value
            key: Stat key
            numeric_data: Numeric data for all teams
            quartiles: Quartile data for coloring
            reverse_flag: Optional override for reverse coloring logic

        Returns:
            Tuple of (QLabel widget, QTableWidgetItem)
        """
        cell_label = QLabel()
        cell_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Determine background color
        bg_color = "transparent"
        if key in numeric_data and key in quartiles:
            if reverse_flag is None:
                reverse = key in {"turnover_percentage", "points_allowed_per_game",
                                "defensive_rating", "turnover_rate"}
            else:
                reverse = reverse_flag

            qcolor = get_quartile_color(num_value, quartiles[key], reverse)
            bg_color = qcolor.name()  # Convert QColor to hex string

        # Set style with background color
        cell_label.setStyleSheet(f"background-color: {bg_color}; padding: 4px;")

        # Set text with trend symbol
        if trend_symbol:
            cell_label.setText(
                f'{display_value} <span style="color: {trend_color}; font-weight: bold;">{trend_symbol}</span>'
            )
        else:
            cell_label.setText(display_value)

        # Create item for sorting
        item = NumericTableWidgetItem(num_value, "")

        return cell_label, item
