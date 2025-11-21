"""Radar chart visualization for player statistics with grouped metrics."""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.projections import PolarAxes
from typing import Dict, List, Tuple, Optional, Any
import math


class RadarChart:
    """
    Create radar charts with hierarchical grouping of metrics.

    Groups metrics in two levels:
    - Level 1: Defense, Style, Ball Handling, Shooting
    - Level 2: Specific metrics for each category
    """

    # Define the metric groups with their sub-metrics
    METRIC_GROUPS = {
        'Defensa': {
            'metrics': ['TAP%', 'RD%', 'DRating', 'STL%'],
            'color': '#E74C3C',  # Red
            'reverse_metrics': ['DRating']  # Lower is better
        },
        'Tiro': {
            'metrics': ['TS%', 'T3%', 'T2%', 'TL%'],
            'color': '#3498DB',  # Blue
            'reverse_metrics': []
        },
        'Manejo': {
            'metrics': ['AST%', 'TO%', 'AST Ratio', 'AST/TO'],
            'color': '#2ECC71',  # Green
            'reverse_metrics': ['TO%']  # Lower is better
        },
        'Estilo': {
            'metrics': ['AST/USG', '3Pr', 'FTr', 'USG%'],
            'color': '#F39C12',  # Orange
            'reverse_metrics': []
        }
    }

    # Mapping from display names to database field names
    METRIC_FIELD_MAPPING = {
        'TAP%': 'blk_pct',
        'RD%': 'drb_pct',
        'DRating': 'drating',
        'STL%': 'stl_pct',
        'TS%': 'ts',
        'T3%': 'fg3_pct',
        'T2%': 'fg2_pct',
        'TL%': 'ft_pct',
        'AST%': 'ast_pct',
        'TO%': 'tov_pct',
        'AST Ratio': 'ast_ratio',
        'AST/TO': 'ast_to_ratio',
        'AST/USG': 'ast_usg',
        '3Pr': 'three_pr',
        'FTr': 'ftr',
        'USG%': 'usage'
    }

    def __init__(self, figsize: Tuple[int, int] = (12, 10)):
        """
        Initialize the radar chart.

        Args:
            figsize: Figure size (width, height)
        """
        self.figsize = figsize
        self.all_metrics = []
        self.group_boundaries = {}
        self._build_metric_structure()

    def _build_metric_structure(self):
        """Build the ordered list of metrics and group boundaries."""
        current_index = 0

        for group_name, group_info in self.METRIC_GROUPS.items():
            metrics = group_info['metrics']
            self.all_metrics.extend(metrics)

            # Store start and end indices for each group
            self.group_boundaries[group_name] = {
                'start': current_index,
                'end': current_index + len(metrics) - 1,
                'color': group_info['color'],
                'metrics': metrics
            }

            current_index += len(metrics)

    def normalize_values(self, player_data: Dict[str, float],
                        league_data: List[Dict[str, float]]) -> Tuple[List[float], List[float]]:
        """
        Normalize player values against league averages.

        Args:
            player_data: Dictionary with player's metric values
            league_data: List of dictionaries with all players' data

        Returns:
            Tuple of (normalized_values, league_averages) for all metrics
        """
        normalized_values = []
        league_averages = []

        for metric in self.all_metrics:
            field_name = self.METRIC_FIELD_MAPPING.get(metric, metric.lower())

            # Get player value
            player_value = player_data.get(field_name, 0)

            # Calculate league statistics
            league_values = [p.get(field_name, 0) for p in league_data if p.get(field_name) is not None]

            if not league_values:
                normalized_values.append(0)
                league_averages.append(0)
                continue

            league_avg = np.mean(league_values)
            league_std = np.std(league_values)
            league_min = np.min(league_values)
            league_max = np.max(league_values)

            # Check if this is a reverse metric (lower is better)
            is_reverse = False
            for group_info in self.METRIC_GROUPS.values():
                if metric in group_info['reverse_metrics']:
                    is_reverse = True
                    break

            # Normalize using min-max normalization (0-100 scale)
            if league_max - league_min > 0:
                if is_reverse:
                    # For reverse metrics, invert the scale
                    normalized = 100 * (league_max - player_value) / (league_max - league_min)
                    avg_normalized = 100 * (league_max - league_avg) / (league_max - league_min)
                else:
                    normalized = 100 * (player_value - league_min) / (league_max - league_min)
                    avg_normalized = 100 * (league_avg - league_min) / (league_max - league_min)
            else:
                normalized = 50  # Middle value if no variation
                avg_normalized = 50

            normalized_values.append(normalized)
            league_averages.append(avg_normalized)

        return normalized_values, league_averages

    def create_chart(self, player_data: Dict[str, Any], league_data: List[Dict[str, Any]],
                    player_name: str, title: Optional[str] = None) -> plt.Figure:
        """
        Create a radar chart for a player.

        Args:
            player_data: Dictionary with player's statistics
            league_data: List of dictionaries with all players' data for normalization
            player_name: Name of the player
            title: Optional custom title

        Returns:
            Matplotlib Figure object
        """
        # Normalize values
        player_values, league_averages = self.normalize_values(player_data, league_data)

        # Number of variables
        num_vars = len(self.all_metrics)

        # Compute angle for each axis
        angles = [n / float(num_vars) * 2 * math.pi for n in range(num_vars)]

        # Initialize the plot
        fig, ax = plt.subplots(figsize=self.figsize, subplot_kw=dict(projection='polar'))

        # Set limits to match the data range exactly
        ax.set_ylim(0, 100)  # Circle ends at 100, labels will be placed outside with clip_on=False

        # Draw the group backgrounds
        self._draw_group_backgrounds(ax, angles, num_vars)

        # Plot league average line (thin gray line)
        league_avg_angles = angles + [angles[0]]
        league_avg_values = league_averages + [league_averages[0]]
        ax.plot(league_avg_angles, league_avg_values, linewidth=1.5, color='gray',
                alpha=0.5, linestyle='--')

        # Plot player values as colored bars for each group
        bar_width = (angles[1] - angles[0]) * 0.8 if len(angles) > 1 else 0.3

        for i, (metric, value) in enumerate(zip(self.all_metrics, player_values)):
            # Find which group this metric belongs to
            color = '#333333'  # Default color
            for group_name, boundaries in self.group_boundaries.items():
                if boundaries['start'] <= i <= boundaries['end']:
                    color = boundaries['color']
                    break

            # Draw bar for this metric
            ax.bar(angles[i], value, width=bar_width, bottom=0,
                   color=color, alpha=0.7, edgecolor='white', linewidth=1)

        # Set the labels for each axis with padding to avoid overlap
        ax.set_xticks(angles)
        ax.set_xticklabels(self.all_metrics, size=10)

        # Set radial ticks (no labels)
        ax.set_yticks([])
        ax.set_yticklabels([])

        # Adjust label position to be further from the plot
        ax.tick_params(axis='x', pad=15)

        # Add grid
        ax.grid(True, linestyle='--', alpha=0.5)

        # Add group labels AFTER everything else, using axis coordinates
        self._add_group_labels(ax, angles)

        # Add title
        if title is None:
            title = f'Análisis Radar - {player_name}'
        plt.title(title, size=16, weight='bold', pad=20)

        plt.tight_layout()

        return fig

    def _draw_group_backgrounds(self, ax: PolarAxes, angles: List[float], num_vars: int):
        """
        Draw colored background sections for each metric group.

        Args:
            ax: Polar axes object
            angles: List of angles for each metric
            num_vars: Total number of variables
        """
        for group_name, boundaries in self.group_boundaries.items():
            start_idx = boundaries['start']
            end_idx = boundaries['end']
            color = boundaries['color']

            # Create theta values for the wedge
            theta1 = angles[start_idx] - (angles[1] - angles[0]) / 2 if len(angles) > 1 else 0
            theta2 = angles[end_idx] + (angles[1] - angles[0]) / 2 if len(angles) > 1 else 2 * math.pi

            # Draw filled wedge up to radius 100 (the data limit)
            theta_fill = np.linspace(theta1, theta2, 50)
            r_fill = np.ones_like(theta_fill) * 100
            ax.fill_between(theta_fill, 0, r_fill, alpha=0.1, color=color)

    def _add_group_labels(self, ax: PolarAxes, angles: List[float]):
        """
        Add text labels for each metric group outside the plot area.

        Args:
            ax: Polar axes object
            angles: List of angles for each metric
        """
        for group_name, boundaries in self.group_boundaries.items():
            start_idx = boundaries['start']
            end_idx = boundaries['end']
            color = boundaries['color']

            # Calculate the middle angle of the group
            if len(angles) > 1:
                angle_span = angles[1] - angles[0]
                middle_angle = angles[start_idx] + (end_idx - start_idx) * angle_span / 2
            else:
                middle_angle = angles[start_idx]

            # Place labels at radius 120 (20% outside the ylim of 100)
            radius = 120

            # Place text at the calculated angle and radius
            ax.text(middle_angle, radius, group_name,
                   ha='center', va='center',
                   fontsize=13, fontweight='bold',
                   color=color,
                   bbox=dict(boxstyle='round,pad=0.6', facecolor='white',
                            edgecolor=color, alpha=0.9, linewidth=2.5),
                   clip_on=False)  # Allow text outside the axes

    def calculate_metrics_from_stats(self, player_stats: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate all required metrics from raw player statistics.

        Args:
            player_stats: Dictionary with player's raw statistics

        Returns:
            Dictionary with calculated metrics
        """
        metrics = {}

        # Extract basic stats
        games = player_stats.get('games_played', 1)
        minutes = player_stats.get('total_minutes', 0) / 60  # Convert to minutes

        # Shooting percentages (already calculated)
        metrics['ts'] = player_stats.get('ts', 0)
        metrics['fg3_pct'] = player_stats.get('total_p3m', 0) / max(player_stats.get('total_p3a', 1), 1) * 100
        metrics['fg2_pct'] = player_stats.get('total_p2m', 0) / max(player_stats.get('total_p2a', 1), 1) * 100
        metrics['ft_pct'] = player_stats.get('total_p1m', 0) / max(player_stats.get('total_p1a', 1), 1) * 100

        # Advanced stats
        metrics['ast_pct'] = player_stats.get('ast_pct', 0)
        metrics['tov_pct'] = player_stats.get('tov_pct', 0)
        metrics['stl_pct'] = player_stats.get('stl_pct', 0)
        metrics['blk_pct'] = player_stats.get('blk_pct', 0)
        metrics['drb_pct'] = player_stats.get('drb_pct', 0)
        metrics['drating'] = player_stats.get('drating', 100)

        # Ratios
        assists = player_stats.get('total_ast', 0)
        turnovers = player_stats.get('total_to', 1)
        usage = player_stats.get('usage', 1)

        metrics['ast_ratio'] = (assists * 100) / max(turnovers + assists, 1)
        metrics['ast_to_ratio'] = assists / max(turnovers, 1)
        metrics['ast_usg'] = assists / max(usage, 1)

        # Style metrics
        metrics['three_pr'] = player_stats.get('three_pr', 0)
        metrics['ftr'] = player_stats.get('ftr', 0)
        metrics['usage'] = player_stats.get('usage', 0)

        return metrics
