#!/usr/bin/env python3
"""
Zone Analysis for FEB Game Data
Analyzes shot data from feb_game.json to calculate zone performance statistics.

This script:
1. Loads shot data from FEB JSON format using existing shot_visualizer
2. Converts coordinates to FIBA half-court system
3. Classifies shots by zones
4. Calculates made/missed statistics per zone
5. Creates visualization with color-coded zones (Red-Amber-Green based on %)
"""

import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LinearSegmentedColormap
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from .detailed_zones import DetailedCourtZones
from .data_loaders import load_feb_game_data
from .court_renderer import CourtRenderer


class ZoneAnalyzer:
    """Analyzes shot data by court zones with performance visualization."""

    def __init__(self, detail_level: str = 'detailed'):
        """
        Initialize zone analyzer.

        Parameters:
        -----------
        detail_level : str
            Zone detail level ('basic' or 'detailed')
        """
        self.zones = DetailedCourtZones(detail_level=detail_level)
        self.court_renderer = CourtRenderer()
        self.shot_stats = {}

        # Color palette for performance visualization
        self.create_performance_colormap()

    def create_performance_colormap(self):
        """Create Red-Amber-Green gradient colormap for smooth performance visualization."""
        # Define colors: Deep Red → Red → Orange → Yellow → Light Green → Green → Bright Green
        colors = [
            '#8B0000',  # Deep red (very poor)
            '#FF0000',  # Red (poor)
            '#FF4500',  # Orange-red (below average)
            '#FFA500',  # Orange (low average)
            '#FFD700',  # Gold/Yellow (average)
            '#ADFF2F',  # Green-yellow (good)
            '#32CD32',  # Lime green (very good)
            '#228B22'   # Forest green (excellent)
        ]

        n_bins = 256  # High resolution for smooth gradients
        self.performance_cmap = LinearSegmentedColormap.from_list(
            'performance_gradient', colors, N=n_bins
        )

        # Basketball-realistic performance thresholds
        self.performance_thresholds = {
            2: {  # 2-point shots
                'poor': 30,      # < 30% is poor for 2PT
                'excellent': 40  # > 40% is excellent for 2PT (30-40% is average)
            },
            3: {  # 3-point shots
                'poor': 20,      # < 20% is poor for 3PT
                'excellent': 30  # > 30% is excellent for 3PT (20-30% is average)
            }
        }

    def get_performance_color(self, percentage: float, zone_points: int) -> Tuple[str, float]:
        """
        Get color based on basketball-realistic performance expectations using gradient palette.

        Parameters:
        -----------
        percentage : float
            Shooting percentage (0-100)
        zone_points : int
            Points value of the zone (2 or 3)

        Returns:
        --------
        Tuple[str, float]
            (color, alpha) values
        """
        thresholds = self.performance_thresholds.get(zone_points, self.performance_thresholds[2])

        # Normalize percentage to 0-1 range based on thresholds
        poor_threshold = thresholds['poor']
        excellent_threshold = thresholds['excellent']

        if percentage <= poor_threshold:
            # Poor range: scale from 0 to poor_threshold
            normalized = max(0, percentage / poor_threshold)
            # Deep red to lighter red
            color_value = 0.0 + (normalized * 0.33)  # 0.0 to 0.33 in colormap
        elif percentage <= excellent_threshold:
            # Average range: scale from poor_threshold to excellent_threshold
            range_size = excellent_threshold - poor_threshold
            normalized = (percentage - poor_threshold) / range_size
            # Red to amber to yellow
            color_value = 0.33 + (normalized * 0.34)  # 0.33 to 0.67 in colormap
        else:
            # Excellent range: scale above excellent_threshold
            # Cap at reasonable maximum (e.g., 80% for visualization)
            max_display = min(80, excellent_threshold * 1.5)
            excess = min(percentage, max_display) - excellent_threshold
            max_excess = max_display - excellent_threshold
            normalized = excess / max_excess if max_excess > 0 else 0
            # Yellow to bright green
            color_value = 0.67 + (normalized * 0.33)  # 0.67 to 1.0 in colormap

        # Get color from the performance colormap
        rgba_color = self.performance_cmap(color_value)
        # Convert to hex
        hex_color = f"#{int(rgba_color[0]*255):02x}{int(rgba_color[1]*255):02x}{int(rgba_color[2]*255):02x}"

        return hex_color, 0.8

    def calculate_optimal_label_positions(self, zone_stats: Dict) -> Dict[str, Tuple[float, float]]:
        """
        Calculate optimal label positions inside zone boundaries to avoid overlaps.

        Parameters:
        -----------
        zone_stats : Dict
            Zone statistics dictionary

        Returns:
        --------
        Dict[str, Tuple[float, float]]
            Dictionary mapping zone keys to (x, y) label positions inside zones
        """
        # Define manual positions INSIDE each zone boundary based on zone geometry
        # Based on actual zone bounds from DetailedCourtZones

        manual_positions = {
            # Interior zones (2-point) - avoiding overlaps with careful positioning
            'restricted_area': (7.5, 2.0),      # Center of restricted area (bounds: 6.2-8.8, 1.2-2.8)
            'key_area': (7.5, 4.5),             # Upper part of key area (bounds: 5.0-9.9, 0.0-5.8)

            # Mid-range zones (2-point) - using safe positions that don't overlap
            'short_mid_range': (10.5, 1.5),     # Right side of short mid-range, safe position
            'medium_mid_range': (7.5, 6.0),     # Center-upper part of medium mid-range, safe position
            'long_mid_range': (7.5, 7.8),       # Center-top of long mid-range, safe position

            # Three-point zones - positioned well inside each zone
            'left_corner_three': (0.45, 1.5),   # Center of left corner (bounds: 0.0-0.9, 0.0-3.0)
            'left_wing_three': (2.5, 8.5),      # Center of left wing (bounds: 0.0-5.0, 3.0-14.0)
            'center_three': (7.5, 10.5),        # Center three area (bounds: 5.0-9.9, 7.9-14.0)
            'right_wing_three': (12.5, 8.5),    # Center of right wing (bounds: 9.9-15.0, 3.0-14.0)
            'right_corner_three': (14.55, 1.5)  # Center of right corner (bounds: 14.1-15.0, 0.0-3.0)
        }

        label_positions = {}

        # Use manual positions that are guaranteed to be inside zones
        for zone_key, zone_data in self.zones.zones.items():
            if zone_key in manual_positions:
                # Use carefully positioned coordinates inside zone
                label_positions[zone_key] = manual_positions[zone_key]
            else:
                # Fall back to centroid (should be inside zone by definition)
                polygon = zone_data['polygon']
                centroid = polygon.centroid
                label_positions[zone_key] = (centroid.x, centroid.y)

        return label_positions


    def analyze_zone_performance(self, shots: List[Dict]) -> Dict:
        """
        Analyze shot performance by zones.

        Parameters:
        -----------
        shots : List[Dict]
            List of shot dictionaries

        Returns:
        --------
        Dict
            Zone performance statistics
        """
        zone_stats = {}

        # Initialize zone stats
        for zone_name in self.zones.zones.keys():
            zone_stats[zone_name] = {
                'made': 0,
                'missed': 0,
                'total': 0,
                'percentage': 0.0,
                'zone_info': self.zones.zones[zone_name]
            }

        # Classify shots by zones
        unclassified_shots = 0
        for shot in shots:
            x, y = shot['x'], shot['y']

            # Get zone for this shot
            zone_info = self.zones.get_zone_for_shot(x, y)

            if zone_info and 'name' in zone_info:
                # Find the zone key that matches this zone info
                zone_key = None
                for key, zone_data in self.zones.zones.items():
                    if zone_data['name'] == zone_info['name']:
                        zone_key = key
                        break

                if zone_key:
                    if shot['made']:
                        zone_stats[zone_key]['made'] += 1
                    else:
                        zone_stats[zone_key]['missed'] += 1
                    zone_stats[zone_key]['total'] += 1
                else:
                    unclassified_shots += 1
            else:
                unclassified_shots += 1

        # Calculate percentages
        for zone_key in zone_stats:
            total = zone_stats[zone_key]['total']
            if total > 0:
                made = zone_stats[zone_key]['made']
                zone_stats[zone_key]['percentage'] = (made / total) * 100

        # Store for later use
        self.shot_stats = zone_stats

        return {
            'zone_stats': zone_stats,
            'total_shots': len(shots),
            'unclassified_shots': unclassified_shots
        }

    def plot_zone_analysis(self, stats: Dict, title: str = "Zone Performance Analysis",
                          figsize: Tuple[int, int] = (12, 10)) -> plt.Figure:
        """
        Create visualization of zone performance with color coding and optimized label positioning.

        Parameters:
        -----------
        stats : Dict
            Zone performance statistics
        title : str
            Plot title
        figsize : Tuple[int, int]
            Figure size

        Returns:
        --------
        plt.Figure
            The created figure
        """
        # Create figure and axis first
        fig, ax = plt.subplots(figsize=figsize)

        # Set court dimensions and background
        ax.set_xlim(0, 15)  # FIBA court width
        ax.set_ylim(0, 14)  # FIBA half-court length
        ax.set_facecolor('#f8f8f8')  # Light court background
        ax.set_aspect('equal')

        zone_stats = stats['zone_stats']

        # Calculate optimal label positions to avoid overlaps
        label_positions = self.calculate_optimal_label_positions(zone_stats)

        # Plot zones FIRST with high visibility
        for zone_key, zone_data in self.zones.zones.items():
            polygon = zone_data['polygon']
            zone_points = zone_data['points']

            # Get performance data
            stats_data = zone_stats.get(zone_key, {'total': 0, 'percentage': 0, 'made': 0})

            if stats_data['total'] > 0:
                # Zone has shots - color by basketball-realistic performance
                percentage = stats_data['percentage']
                color, alpha = self.get_performance_color(percentage, zone_points)

                # Get optimized label position
                label_x, label_y = label_positions[zone_key]
                label_text = f"{stats_data['made']}/{stats_data['total']}\n{percentage:.1f}%"
            else:
                # Zone has no shots - show in light gray
                color = '#E0E0E0'
                alpha = 0.5

                # Get optimized label position
                label_x, label_y = label_positions[zone_key]
                label_text = f"0/0\n0%"

            # Plot zone polygon with HIGH visibility
            if hasattr(polygon, 'exterior'):
                # Single polygon
                x_coords, y_coords = polygon.exterior.xy
                ax.fill(x_coords, y_coords, color=color, alpha=alpha,
                       edgecolor='darkgray', linewidth=1.5, zorder=5)
            elif hasattr(polygon, 'geoms'):
                # Multi-polygon
                for geom in polygon.geoms:
                    if hasattr(geom, 'exterior'):
                        x_coords, y_coords = geom.exterior.xy
                        ax.fill(x_coords, y_coords, color=color, alpha=alpha,
                               edgecolor='darkgray', linewidth=1.5, zorder=5)

            # Add text label with optimized position and HIGH z-order
            ax.text(label_x, label_y, label_text,
                   ha='center', va='center', fontsize=8, fontweight='bold',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                            alpha=0.95, edgecolor='black', linewidth=1),
                   zorder=15)

        # Draw court elements using unified renderer
        self.court_renderer.draw_court_elements(ax, line_color='black', line_width=2, zorder=10)

        # Set title only
        if title:
            ax.set_title(title, fontsize=16, fontweight='bold', pad=20)

        # Remove axes scales and labels for cleaner visualization
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xlabel('')
        ax.set_ylabel('')

        # Remove axis spines for even cleaner look
        for spine in ax.spines.values():
            spine.set_visible(False)

        plt.tight_layout()
        return fig

    def print_zone_summary(self, stats: Dict):
        """Print detailed zone performance summary with basketball context."""
        print("\\n" + "="*70)
        print("ZONE PERFORMANCE ANALYSIS SUMMARY")
        print("="*70)

        zone_stats = stats['zone_stats']

        # Sort zones by total shots
        sorted_zones = sorted(zone_stats.items(), key=lambda x: x[1]['total'], reverse=True)

        print(f"{'Zone':<20} {'Made':<6} {'Total':<6} {'%':<8} {'Points':<7} {'Performance'}")
        print("-" * 70)

        total_made = 0
        total_shots = 0

        for zone_key, data in sorted_zones:
            if data['total'] > 0:
                zone_name = data['zone_info']['name']
                made = data['made']
                total = data['total']
                percentage = data['percentage']
                points = data['zone_info']['points']

                # Get performance rating using the gradient system
                color, _ = self.get_performance_color(percentage, points)

                # Determine performance category based on thresholds
                thresholds = self.performance_thresholds.get(points, self.performance_thresholds[2])
                if percentage > thresholds['excellent']:
                    performance = "🟢 Excellent"
                elif percentage >= thresholds['poor']:
                    performance = "🟡 Average"
                else:
                    performance = "🔴 Poor"

                print(f"{zone_name:<20} {made:<6} {total:<6} {percentage:<8.1f} {points:<7} {performance}")

                total_made += made
                total_shots += total

        print("-" * 70)
        overall_percentage = (total_made / total_shots * 100) if total_shots > 0 else 0
        print(f"{'TOTAL':<20} {total_made:<6} {total_shots:<6} {overall_percentage:<8.1f}")

        print(f"\\nUnclassified shots: {stats['unclassified_shots']}")
        print(f"Total shots in game: {stats['total_shots']}")

        # Basketball insights
        print(f"\\n🏀 BASKETBALL INSIGHTS:")
        print(f"   📊 Overall efficiency: {overall_percentage:.1f}%")

        # Analyze 2PT vs 3PT performance
        two_pt_made = sum(data['made'] for data in zone_stats.values()
                         if data['total'] > 0 and data['zone_info']['points'] == 2)
        two_pt_total = sum(data['total'] for data in zone_stats.values()
                          if data['total'] > 0 and data['zone_info']['points'] == 2)
        three_pt_made = sum(data['made'] for data in zone_stats.values()
                           if data['total'] > 0 and data['zone_info']['points'] == 3)
        three_pt_total = sum(data['total'] for data in zone_stats.values()
                            if data['total'] > 0 and data['zone_info']['points'] == 3)

        if two_pt_total > 0:
            two_pt_pct = (two_pt_made / two_pt_total) * 100
            print(f"   🏀 2PT shooting: {two_pt_made}/{two_pt_total} ({two_pt_pct:.1f}%)")

        if three_pt_total > 0:
            three_pt_pct = (three_pt_made / three_pt_total) * 100
            print(f"   🎯 3PT shooting: {three_pt_made}/{three_pt_total} ({three_pt_pct:.1f}%)")


def main():
    """Main execution function."""
    # Initialize analyzer
    analyzer = ZoneAnalyzer(detail_level='detailed')

    # Load FEB game data using new data loader
    json_path = "src/JSON_samples/feb_game.json"

    if not Path(json_path).exists():
        print(f"Error: Could not find {json_path}")
        return

    print("Loading FEB game data...")
    shots = load_feb_game_data(json_path)
    print(f"Loaded {len(shots)} shots from game data")

    # Analyze zone performance
    print("\\nAnalyzing zone performance...")
    stats = analyzer.analyze_zone_performance(shots)

    # Print summary
    analyzer.print_zone_summary(stats)

    # Create visualization
    print("\\nCreating zone performance visualization...")
    fig = analyzer.plot_zone_analysis(stats, title="FEB Game - Zone Performance Analysis")

    # Save the plot
    output_path = "zone_performance_analysis.png"
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Visualization saved as: {output_path}")

    # Show the plot
    plt.show()


if __name__ == "__main__":
    main()