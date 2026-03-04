"""Helper functions for IN/OUT statistics calculations and display."""

from typing import Dict, List, Tuple
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
from PyQt6.QtGui import QColor

from .table_items import NumericTableWidgetItem


class InOutStatsHelper:
    """Shared logic for IN/OUT statistics processing and display."""

    @staticmethod
    def build_team_dict(stats: Dict, team_name: str = "Team") -> Dict:
        """
        Build team statistics dictionary from aggregated stats.

        Args:
            stats: Aggregated statistics dictionary
            team_name: Name of the team

        Returns:
            Dictionary formatted for StatsCalculator
        """
        return {
            'name': team_name,
            'pts': int(stats.get('points_for', 0)),
            'p2m': int(stats.get('fgm_2', 0)),
            'p2a': int(stats.get('fga_2', 0)),
            'p3m': int(stats.get('fgm_3', 0)),
            'p3a': int(stats.get('fga_3', 0)),
            'p1m': int(stats.get('ftm', 0)),
            'p1a': int(stats.get('fta', 0)),
            'ro': int(stats.get('orb', 0)),
            'rd': int(stats.get('drb', 0)),
            'assist': int(stats.get('ast', 0)),
            'st': int(stats.get('stl', 0)),
            'to': int(stats.get('tov', 0)),
            'bs': int(stats.get('blk', 0))
        }

    @staticmethod
    def build_opp_dict(stats: Dict) -> Dict:
        """
        Build opponent statistics dictionary from aggregated stats.

        Args:
            stats: Aggregated statistics dictionary

        Returns:
            Dictionary formatted for StatsCalculator
        """
        return {
            'name': 'OPP',
            'pts': int(stats.get('points_against', 0)),
            'p2m': int(stats.get('opp_fgm_2', 0)),
            'p2a': int(stats.get('opp_fga_2', 0)),
            'p3m': int(stats.get('opp_fgm_3', 0)),
            'p3a': int(stats.get('opp_fga_3', 0)),
            'p1m': int(stats.get('opp_ftm', 0)),
            'p1a': int(stats.get('opp_fta', 0)),
            'ro': int(stats.get('opp_orb', 0)),
            'rd': int(stats.get('opp_drb', 0)),
            'assist': int(stats.get('opp_ast', 0)),
            'st': int(stats.get('opp_stl', 0)),
            'to': int(stats.get('opp_tov', 0)),
            'bs': int(stats.get('opp_blk', 0))
        }

    @staticmethod
    def normalize_possessions(adv_stats: Dict, minutes: float) -> Dict:
        """
        Normalize possessions to 40 minutes baseline.

        Args:
            adv_stats: Advanced statistics dictionary
            minutes: Total minutes played

        Returns:
            Updated adv_stats with possessions_per_40
        """
        NORMALIZED_MINUTES = 40.0
        poss = float(adv_stats.get('possessions_per_game', 0))
        
        if minutes > 0:
            adv_stats['possessions_per_40'] = poss * (NORMALIZED_MINUTES / minutes)
        else:
            adv_stats['possessions_per_40'] = poss
            
        return adv_stats

    @staticmethod
    def add_derived_fields(adv_stats: Dict, team_dict: Dict, opp_dict: Dict) -> Dict:
        """
        Add derived fields - not needed as calculate_single_match_stats already includes them.

        Args:
            adv_stats: Advanced statistics dictionary
            team_dict: Team statistics dictionary
            opp_dict: Opponent statistics dictionary

        Returns:
            adv_stats unchanged (kept for backward compatibility)
        """
        # Fields like points_scored, points_received already exist from calculate_single_match_stats
        return adv_stats

    @staticmethod
    def get_display_fields() -> List[Tuple[str, str, bool]]:
        """
        Get list of fields to display in comparison tables.

        Returns:
            List of tuples (label, key, reverse_coloring)
        """
        return [
            ("Posesiones/40min", 'possessions_per_40', False),
            ("ORtg", 'offensive_rating', False),
            ("DRtg", 'defensive_rating', True),
            ("NetRtg", 'net_rating', False),
            ("eFG%", 'efg_percentage', False),
            ("TS%", 'true_shooting', False),
            ("3Pr", 'three_point_rate', False),
            ("FTr", 'free_throw_rate', False),
            ("%AST", 'assist_rate', False),
            ("%TO", 'turnover_rate', True),
            ("OR%", 'offensive_rebound_rate', False),
            ("DR%", 'defensive_rebound_rate', False)
        ]
    
    @staticmethod
    def get_teammate_comparison_fields() -> List[Tuple[str, str, bool]]:
        """
        Get list of fields for teammate comparison (individual player stats per 100 possessions).

        Returns:
            List of tuples (label, key, reverse_coloring)
        """
        return [
            ("Puntos/100", "points", False),
            ("T2/100", "fga_2", False),
            ("T3/100", "fga_3", False),
            ("TL/100", "fta", False),
            ("eFG%", "efg_pct", False),
            ("TS%", "ts_pct", False),
            ("REB-O/100", "orb", False),
            ("REB-D/100", "drb", False),
            ("Asist./100", "ast", False),
            ("Robos/100", "stl", False),
            ("Tapones/100", "blk", False),
            ("Pérdidas/100", "tov", True),
            ("Faltas/100", "pf", True)
        ]

    @staticmethod
    def populate_comparison_table(table: QTableWidget, adv_a: Dict, adv_b: Dict,
                                  display_fields: List[Tuple[str, str, bool]]) -> None:
        """
        Populate comparison table with statistics and deltas.

        Args:
            table: QTableWidget to populate
            adv_a: Advanced stats for condition A
            adv_b: Advanced stats for condition B
            display_fields: List of fields to display
        """
        table.setRowCount(len(display_fields))
        
        for row, (label, key, reverse) in enumerate(display_fields):
            # Stat name
            table.setItem(row, 0, QTableWidgetItem(label))
            
            # Value A
            val_a = adv_a.get(key, 0)
            table.setItem(row, 1, NumericTableWidgetItem(val_a, f"{val_a:.2f}"))
            
            # Value B
            val_b = adv_b.get(key, 0)
            table.setItem(row, 2, NumericTableWidgetItem(val_b, f"{val_b:.2f}"))
            
            # Delta %
            if val_b != 0:
                delta_pct = ((val_a - val_b) / abs(val_b)) * 100
            else:
                delta_pct = 0.0
            
            delta_item = NumericTableWidgetItem(delta_pct, f"{delta_pct:.1f}%")
            
            # Color coding (green = A better, red = B better)
            DELTA_THRESHOLD = 0.5
            if abs(delta_pct) > DELTA_THRESHOLD:
                if (delta_pct > 0 and not reverse) or (delta_pct < 0 and reverse):
                    delta_item.setBackground(QColor("#c8e6c9"))  # Green
                else:
                    delta_item.setBackground(QColor("#ffcdd2"))  # Red
            
            table.setItem(row, 3, delta_item)

    @staticmethod
    def calculate_advanced_metrics(stats_calculator, stats: Dict, team_name: str) -> Dict:
        """
        Calculate advanced metrics from aggregated statistics.

        Args:
            stats_calculator: StatsCalculator instance
            stats: Aggregated statistics
            team_name: Name of the team

        Returns:
            Dictionary with advanced metrics and normalized possessions
        """
        team_dict = InOutStatsHelper.build_team_dict(stats, team_name)
        opp_dict = InOutStatsHelper.build_opp_dict(stats)
        
        adv_stats = stats_calculator.calculate_single_match_stats(team_dict, opp_dict)
        
        minutes = float(stats.get('minutes', 0))
        adv_stats = InOutStatsHelper.normalize_possessions(adv_stats, minutes)
        adv_stats = InOutStatsHelper.add_derived_fields(adv_stats, team_dict, opp_dict)
        
        return adv_stats
    
    @staticmethod
    def populate_teammate_comparison_table(
        table: QTableWidget, 
        norm_a: Dict, 
        norm_b: Dict,
        teammate_a: str,
        teammate_b: str
    ) -> None:
        """
        Populate teammate comparison table with normalized stats per 100 possessions.

        Args:
            table: QTableWidget to populate
            norm_a: Normalized stats (per 100 poss) with teammate A
            norm_b: Normalized stats (per 100 poss) with teammate B
            teammate_a: Name of teammate A
            teammate_b: Name of teammate B
        """
        display_fields = InOutStatsHelper.get_teammate_comparison_fields()
        
        # Update headers
        table.setHorizontalHeaderLabels([
            "Estadística", f"Con {teammate_a}", f"Con {teammate_b}", "Δ %"
        ])
        
        # Populate table
        table.setRowCount(len(display_fields))
        
        for row, (label, key, reverse) in enumerate(display_fields):
            # Stat name
            table.setItem(row, 0, QTableWidgetItem(label))
            
            # Value A (normalized per 100 possessions)
            val_a = norm_a.get(key, 0)
            table.setItem(row, 1, NumericTableWidgetItem(val_a, f"{val_a:.2f}"))
            
            # Value B (normalized per 100 possessions)
            val_b = norm_b.get(key, 0)
            table.setItem(row, 2, NumericTableWidgetItem(val_b, f"{val_b:.2f}"))
            
            # Delta %
            if val_b != 0:
                delta_pct = ((val_a - val_b) / abs(val_b)) * 100
            else:
                delta_pct = 0.0
            
            delta_item = NumericTableWidgetItem(delta_pct, f"{delta_pct:.1f}%")
            
            # Color coding (green = A better, red = B better)
            DELTA_THRESHOLD = 0.5
            if abs(delta_pct) > DELTA_THRESHOLD:
                if (delta_pct > 0 and not reverse) or (delta_pct < 0 and reverse):
                    delta_item.setBackground(QColor("#c8e6c9"))  # Green
                else:
                    delta_item.setBackground(QColor("#ffcdd2"))  # Red
            
            table.setItem(row, 3, delta_item)
    
    @staticmethod
    def add_summary_rows_to_comparison(
        table: QTableWidget,
        minutes_a: float,
        minutes_b: float,
        possessions_a: float,
        possessions_b: float,
        games_a: int,
        games_b: int,
        current_row: int
    ) -> None:
        """
        Add summary rows (minutes, possessions, games) to comparison table.

        Args:
            table: QTableWidget to update
            minutes_a: Minutes with teammate/condition A
            minutes_b: Minutes with teammate/condition B
            possessions_a: Possessions with A
            possessions_b: Possessions with B
            games_a: Games played with A
            games_b: Games played with B
            current_row: Row index to start adding summary rows
        """
        table.setRowCount(current_row + 3)
        
        # Minutes row
        table.setItem(current_row, 0, QTableWidgetItem("Min Juntos"))
        table.setItem(current_row, 1, NumericTableWidgetItem(minutes_a, f"{minutes_a:.1f}"))
        table.setItem(current_row, 2, NumericTableWidgetItem(minutes_b, f"{minutes_b:.1f}"))
        diff = minutes_a - minutes_b
        table.setItem(current_row, 3, NumericTableWidgetItem(diff, f"{diff:.1f}"))
        
        # Possessions row
        table.setItem(current_row + 1, 0, QTableWidgetItem("Posesiones"))
        table.setItem(current_row + 1, 1, NumericTableWidgetItem(possessions_a, f"{possessions_a:.1f}"))
        table.setItem(current_row + 1, 2, NumericTableWidgetItem(possessions_b, f"{possessions_b:.1f}"))
        poss_diff = possessions_a - possessions_b
        table.setItem(current_row + 1, 3, NumericTableWidgetItem(poss_diff, f"{poss_diff:.1f}"))
        
        # Games row
        table.setItem(current_row + 2, 0, QTableWidgetItem("Partidos"))
        table.setItem(current_row + 2, 1, NumericTableWidgetItem(games_a, f"{games_a}"))
        table.setItem(current_row + 2, 2, NumericTableWidgetItem(games_b, f"{games_b}"))
        games_diff = games_a - games_b
        table.setItem(current_row + 2, 3, NumericTableWidgetItem(games_diff, f"{games_diff}"))

