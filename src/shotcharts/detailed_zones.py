"""
Enhanced FIBA Basketball Court Zone Division
Provides multiple levels of zone granularity for detailed shot analysis.

This module extends the basic 4-zone system to provide more detailed breakdowns:
- Basic: 4 zones (inherited from CourtZones)
- Detailed: 10 zones with break-based corner/wing divisions and distance-based mid-range zones
- Advanced: 15+ zones with court position specificity (future implementation)

The 10-zone system provides tactical precision:
- 2 interior zones (restricted area, key)
- 3 mid-range zones (short/medium/long distance-based)
- 5 three-point zones (corners, wings, center - divided at break points)

All zones maintain non-overlapping properties and proper geometric division.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.collections import PatchCollection
from typing import Dict, List, Tuple, Optional
from shapely.geometry import Polygon as ShapelyPolygon, Point
from shapely.ops import unary_union
import matplotlib.patches as mpatches

from .court_zones import CourtZones
from .fiba_court import FIBACourt


class DetailedCourtZones(CourtZones):
    """Extended class for detailed basketball court zone analysis."""

    # Distance thresholds for mid-range zone division (in meters)
    SHORT_MID_RANGE_MAX = 3.5
    MEDIUM_MID_RANGE_MAX = 5.0

    def __init__(self, detail_level: str = 'basic'):
        """
        Initialize detailed court zones.

        Parameters:
        -----------
        detail_level : str
            Level of detail: 'basic', 'detailed', or 'advanced'
        """
        super().__init__()
        self.detail_level = detail_level
        self._create_detailed_zones()

    def _create_detailed_zones(self) -> None:
        """Create zones based on the specified detail level."""
        if self.detail_level == 'basic':
            # Use the original 4-zone system
            return
        elif self.detail_level == 'detailed':
            self._create_10_zone_system()
        elif self.detail_level == 'advanced':
            self._create_15_zone_system()
        else:
            raise ValueError("detail_level must be 'basic', 'detailed', or 'advanced'")

    def _create_10_zone_system(self) -> None:
        """
        Create a 10-zone detailed system with break-based corner/wing division.

        The 10-zone system provides tactical precision by dividing the court into:

        Interior zones (2 points):
        1. Restricted area - Under the basket
        2. Key area - Paint area minus restricted area

        Mid-range zones (2 points, distance-based):
        3. Short mid-range - Close shots (< 3.5m from basket)
        4. Medium mid-range - Medium distance (3.5-5.0m from basket)
        5. Long mid-range - Far two-point shots (> 5.0m from basket)

        Three-point zones (3 points, break-based division):
        6. Left corner - Below break line, tight corner shots
        7. Left wing - Above break line, 45-degree angle shots
        8. Center - Top of arc, aligned with key width (4.9m)
        9. Right wing - Above break line, 45-degree angle shots
        10. Right corner - Below break line, tight corner shots

        Break-based division ensures tactical relevance, as corner vs wing
        three-pointers have different difficulty levels and strategic values.
        """
        # Clear existing zones
        self.zones = {}

        # Get base geometries
        court_boundary = ShapelyPolygon([
            (0, 0), (0, self.court.height),
            (self.court.width, self.court.height), (self.court.width, 0), (0, 0)
        ])

        # Base areas
        three_point_points = self._create_closed_three_point_polygon()
        two_point_area = ShapelyPolygon(three_point_points)

        key_points = self._create_closed_key_polygon()
        key_poly = ShapelyPolygon(key_points)

        restricted_points = self._create_closed_restricted_area_polygon()
        restricted_poly = ShapelyPolygon(restricted_points)

        # Zone 1: Restricted area (unchanged)
        zone_restricted = restricted_poly

        # Zone 2: Key area minus restricted (unchanged)
        zone_key = key_poly.difference(restricted_poly)

        # Divide close 2-point area into 3 zones based on distance from basket
        close_two_base = two_point_area.difference(key_poly)

        # Create distance-based circles from basket center
        basket_center = (self.court.court_center_x, self.court.hoop_center_y)

        # Zone 3: Short mid-range (inside key but outside restricted to ~3.5m from basket)
        short_mid_circle = Point(basket_center).buffer(self.SHORT_MID_RANGE_MAX)
        zone_short_mid = close_two_base.intersection(short_mid_circle)

        # Zone 4: Medium mid-range (3.5m to 5.0m from basket)
        medium_mid_circle = Point(basket_center).buffer(self.MEDIUM_MID_RANGE_MAX)
        zone_medium_mid = close_two_base.intersection(medium_mid_circle).difference(short_mid_circle)

        # Zone 5: Long mid-range (remaining close two point area)
        zone_long_mid = close_two_base.difference(medium_mid_circle)

        # Divide three-point area into zones based on break position
        three_point_base = court_boundary.difference(two_point_area)

        # Get the break point coordinates from the FIBA court
        # The break occurs where the straight corner lines meet the curved arc
        break_y = self.court.three_point_corner_to_break

        # Use the actual three-point side offset for more accurate division
        side_offset = self.court.three_point_side_offset

        # Zone 6: Left corner three (below break line, within side offset)
        left_corner = ShapelyPolygon([
            (0, 0), (side_offset, 0),
            (side_offset, break_y), (0, break_y), (0, 0)
        ])
        zone_left_corner = three_point_base.intersection(left_corner)

        # Zone 8: Center three (top of arc, aligned with key width) - Define first
        key_width = self.court.key_width  # 4.9m - ancho oficial de la zona
        center_three = ShapelyPolygon([
            (self.court.court_center_x - key_width/2, break_y),
            (self.court.court_center_x + key_width/2, break_y),
            (self.court.court_center_x + key_width/2, self.court.height),
            (self.court.court_center_x - key_width/2, self.court.height),
            (self.court.court_center_x - key_width/2, break_y)
        ])
        zone_center_three = three_point_base.intersection(center_three)

        # Zone 7: Left wing/45° three (above break line, left half, minus center)
        left_wing_full = ShapelyPolygon([
            (0, break_y), (self.court.court_center_x, break_y),
            (self.court.court_center_x, self.court.height), (0, self.court.height), (0, break_y)
        ])
        zone_left_wing = three_point_base.intersection(left_wing_full).difference(center_three)

        # Zone 9: Right wing/45° three (above break line, right half, minus center)
        right_wing_full = ShapelyPolygon([
            (self.court.court_center_x, break_y), (self.court.width, break_y),
            (self.court.width, self.court.height), (self.court.court_center_x, self.court.height),
            (self.court.court_center_x, break_y)
        ])
        zone_right_wing = three_point_base.intersection(right_wing_full).difference(center_three)

        # Zone 10: Right corner three (below break line, within side offset)
        right_corner = ShapelyPolygon([
            (self.court.width - side_offset, 0), (self.court.width, 0),
            (self.court.width, break_y), (self.court.width - side_offset, break_y),
            (self.court.width - side_offset, 0)
        ])
        zone_right_corner = three_point_base.intersection(right_corner)

        # Store the 10 zones (now with subdivided corners and wings)
        self.zones = {
            'restricted_area': {
                'polygon': zone_restricted,
                'points': 2,
                'color': '#FF4444',  # Bright red
                'name': 'Área Restringida',
                'description': '2 pts - Bajo la canasta'
            },
            'key_area': {
                'polygon': zone_key,
                'points': 2,
                'color': '#FF8844',  # Orange-red
                'name': 'Zona',
                'description': '2 pts - Zona de pintura'
            },
            'short_mid_range': {
                'polygon': zone_short_mid,
                'points': 2,
                'color': '#4488FF',  # Light blue
                'name': 'Tiro Corto',
                'description': f'2 pts - Corta distancia (< {self.SHORT_MID_RANGE_MAX}m)'
            },
            'medium_mid_range': {
                'polygon': zone_medium_mid,
                'points': 2,
                'color': '#44AAFF',  # Medium blue
                'name': 'Tiro Medio',
                'description': f'2 pts - Media distancia ({self.SHORT_MID_RANGE_MAX}-{self.MEDIUM_MID_RANGE_MAX}m)'
            },
            'long_mid_range': {
                'polygon': zone_long_mid,
                'points': 2,
                'color': '#44CCFF',  # Light cyan
                'name': 'Tiro Largo',
                'description': '2 pts - Larga distancia'
            },
            'left_corner_three': {
                'polygon': zone_left_corner,
                'points': 3,
                'color': '#44FF44',  # Bright green
                'name': 'Esquina Izq.',
                'description': '3 pts - Esquina izquierda (bajo break)'
            },
            'left_wing_three': {
                'polygon': zone_left_wing,
                'points': 3,
                'color': '#66FF66',  # Light green
                'name': '45° Izq.',
                'description': '3 pts - Ala izquierda (sobre break)'
            },
            'center_three': {
                'polygon': zone_center_three,
                'points': 3,
                'color': '#88FF44',  # Yellow-green
                'name': 'Centro Tres',
                'description': '3 pts - Centro del arco'
            },
            'right_wing_three': {
                'polygon': zone_right_wing,
                'points': 3,
                'color': '#AAFF66',  # Light yellow-green
                'name': '45° Der.',
                'description': '3 pts - Ala derecha (sobre break)'
            },
            'right_corner_three': {
                'polygon': zone_right_corner,
                'points': 3,
                'color': '#CCFF44',  # Light green-yellow
                'name': 'Esquina Der.',
                'description': '3 pts - Esquina derecha (bajo break)'
            }
        }

    def _create_15_zone_system(self) -> None:
        """Create a 15-zone advanced system with even more detail."""
        # Start with the 10-zone system
        self._create_10_zone_system()

        # Further subdivide some zones for 15 total zones
        # This would involve splitting the mid-range zones by left/right
        # and potentially adding elbow zones, etc.

        # For now, we'll implement this as an extension of the 10-zone system
        # You can expand this based on specific analytical needs

        # TODO: Implement 15-zone system with:
        # - Left/Right elbow zones
        # - Baseline vs wing three-point shots
        # - Paint vs non-paint interior shots
        pass

    def get_zone_for_shot(self, x: float, y: float) -> Dict:
        """
        Determine which detailed zone a shot belongs to.

        Parameters:
        -----------
        x : float
            X-coordinate of the shot
        y : float
            Y-coordinate of the shot

        Returns:
        --------
        Dict containing zone information
        """
        if self.detail_level == 'basic':
            return super().get_zone_for_shot(x, y)

        point = Point(x, y)

        # For detailed zones, check in order of specificity
        if self.detail_level == 'detailed':
            priority_order = [
                'restricted_area',      # Smallest, highest priority
                'key_area',            # Second smallest
                'short_mid_range',     # Short distance
                'medium_mid_range',    # Medium distance
                'long_mid_range',      # Long 2-point
                'left_corner_three',   # Corner threes (below break)
                'right_corner_three',
                'left_wing_three',     # Wing threes (above break)
                'right_wing_three',
                'center_three'         # Center three
            ]
        else:  # advanced
            priority_order = list(self.zones.keys())

        for zone_name in priority_order:
            if zone_name in self.zones:
                zone_data = self.zones[zone_name]
                if zone_data['polygon'].contains(point):
                    return {
                        'zone': zone_name,
                        'points': zone_data['points'],
                        'name': zone_data['name'],
                        'description': zone_data['description']
                    }

        # Default fallback
        return {
            'zone': 'center_three',
            'points': 3,
            'name': 'Centro Tres',
            'description': '3 pts - Área por defecto'
        }

    def validate_no_overlaps(self) -> Dict:
        """
        Validate that there are no overlaps between zones.

        Returns:
        --------
        Dict containing validation results
        """
        overlaps = []
        total_area = 0

        zone_names = list(self.zones.keys())

        # Check for overlaps between each pair of zones
        for i, zone1_name in enumerate(zone_names):
            zone1 = self.zones[zone1_name]['polygon']
            total_area += zone1.area

            for zone2_name in zone_names[i+1:]:
                zone2 = self.zones[zone2_name]['polygon']

                intersection = zone1.intersection(zone2)
                if not intersection.is_empty and intersection.area > 1e-10:
                    overlaps.append(f"{zone1_name} ∩ {zone2_name}: {intersection.area:.6f} m²")

        court_area = self.court.width * self.court.height

        return {
            'valid': len(overlaps) == 0,
            'overlaps': overlaps,
            'total_coverage': total_area,
            'court_area': court_area,
            'coverage_percentage': (total_area / court_area) * 100
        }

    def export_to_json(self, filename: str) -> None:
        """
        Export zone definitions to JSON file.

        Parameters:
        -----------
        filename : str
            Output filename for JSON export
        """
        import json
        from shapely.geometry import mapping

        export_data = {
            'detail_level': self.detail_level,
            'total_zones': len(self.zones),
            'court_dimensions': {
                'width': self.court.width,
                'height': self.court.height,
                'area': self.court.width * self.court.height
            },
            'zones': {}
        }

        for zone_name, zone_data in self.zones.items():
            export_data['zones'][zone_name] = {
                'name': zone_data['name'],
                'description': zone_data['description'],
                'points': zone_data['points'],
                'color': zone_data['color'],
                'area': zone_data['polygon'].area,
                'geometry': mapping(zone_data['polygon'])
            }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        print(f"Zone data exported to: {filename}")

    def get_zone_statistics(self) -> Dict:
        """
        Get comprehensive statistics for all zones.

        Returns:
        --------
        Dict containing zone statistics
        """
        stats = {}
        for zone_name, zone_data in self.zones.items():
            stats[zone_name] = {
                'name': zone_data['name'],
                'description': zone_data['description'],
                'points': zone_data['points'],
                'area': round(zone_data['polygon'].area, 1),
                'color': zone_data['color']
            }
        return stats

    def plot_detailed_zones(self,
                           figsize: Tuple[int, int] = (16, 12),
                           title: Optional[str] = None,
                           show_legend: bool = True,
                           alpha: float = 0.7,
                           save_path: Optional[str] = None,
                           dpi: int = 300) -> plt.Figure:
        """
        Plot the detailed court zones.

        Parameters:
        -----------
        figsize : tuple
            Figure size (width, height)
        title : str, optional
            Title for the plot
        show_legend : bool
            Whether to show the legend
        alpha : float
            Transparency level for zone colors
        save_path : str, optional
            If provided, save the figure to this path
        dpi : int
            DPI for saved figure

        Returns:
        --------
        fig : matplotlib.figure.Figure
            The generated figure
        """
        if title is None:
            title = f"Pista FIBA - Sistema de {len(self.zones)} Zonas Detalladas"

        return self.plot_zones(figsize=figsize, title=title, show_legend=show_legend,
                             alpha=alpha, save_path=save_path, dpi=dpi)

    def compare_zone_systems(self, save_path: Optional[str] = None) -> plt.Figure:
        """
        Create a comparison visualization of different zone systems.

        Parameters:
        -----------
        save_path : str, optional
            If provided, save the figure to this path

        Returns:
        --------
        fig : matplotlib.figure.Figure
            The generated comparison figure
        """
        fig, axes = plt.subplots(1, 3, figsize=(24, 8))

        # Basic system (4 zones)
        basic_zones = CourtZones()
        ax1 = axes[0]
        self._plot_zones_on_axis(basic_zones, ax1, "Sistema Básico (4 Zonas)")

        # Detailed system (8 zones)
        detailed_zones = DetailedCourtZones('detailed')
        ax2 = axes[1]
        self._plot_zones_on_axis(detailed_zones, ax2, "Sistema Detallado (8 Zonas)")

        # Advanced system (when implemented)
        ax3 = axes[2]
        ax3.text(0.5, 0.5, "Sistema Avanzado\n(12+ Zonas)\n\nPróximamente...",
                ha='center', va='center', transform=ax3.transAxes,
                fontsize=14, bbox=dict(boxstyle='round', facecolor='lightgray'))
        ax3.set_xlim(0, self.court.width)
        ax3.set_ylim(0, self.court.height)
        ax3.set_aspect('equal')
        ax3.axis('off')
        ax3.set_title("Sistema Avanzado (Futuro)")

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
            print(f"Comparación guardada como: {save_path}")

        return fig

    def _plot_zones_on_axis(self, zones_obj, ax, title):
        """Helper method to plot zones on a specific axis."""
        ax.set_title(title, fontsize=14, pad=20)
        ax.set_xlim(0, self.court.width)
        ax.set_ylim(0, self.court.height)
        ax.set_aspect('equal')
        ax.axis('off')

        # Plot zones with consistent z-ordering
        zone_zorder = {
            'restricted_area': 8, 'key_area': 7,
            'short_mid_range': 6, 'medium_mid_range': 5, 'long_mid_range': 4,
            'close_two_point': 4, 'left_corner_three': 3, 'center_three': 2,
            'right_corner_three': 3, 'three_point': 1
        }

        for zone_name, zone_data in zones_obj.zones.items():
            polygon = zone_data['polygon']
            color = zone_data['color']
            zorder = zone_zorder.get(zone_name, 1)

            self._add_polygon_to_axis(ax, polygon, color, 0.7, zorder)

        # Add court lines
        zones_obj._draw_court_lines_only(ax)

    def _add_polygon_to_axis(self, ax, polygon, color, alpha, zorder):
        """Helper method to add a polygon to an axis."""
        if polygon.geom_type == 'Polygon':
            coords = list(polygon.exterior.coords)
            patch = mpatches.Polygon(coords, facecolor=color, alpha=alpha,
                                   edgecolor='darkgray', linewidth=0.5, zorder=zorder)
            ax.add_patch(patch)
        elif polygon.geom_type == 'GeometryCollection':
            for geom in polygon.geoms:
                if geom.geom_type == 'Polygon':
                    coords = list(geom.exterior.coords)
                    patch = mpatches.Polygon(coords, facecolor=color, alpha=alpha,
                                           edgecolor='darkgray', linewidth=0.5, zorder=zorder)
                    ax.add_patch(patch)

    def validate_zones(self) -> Dict[str, bool]:
        """
        Validate zone system for common geometric issues.

        Returns:
        --------
        Dict[str, bool]
            Dictionary with validation results:
            - 'no_overlaps': True if no zones overlap
            - 'complete_coverage': True if zones cover the full court
            - 'all_valid_polygons': True if all zones are valid polygons
        """
        from shapely.geometry import Polygon as ShapelyPolygon

        # Create court boundary for coverage check
        court_boundary = ShapelyPolygon([
            (0, 0), (0, self.court.height),
            (self.court.width, self.court.height), (self.court.width, 0), (0, 0)
        ])

        zones_list = [zone_data['polygon'] for zone_data in self.zones.values()]

        # Check for overlaps
        no_overlaps = True
        for i, zone1 in enumerate(zones_list):
            for j, zone2 in enumerate(zones_list[i+1:], i+1):
                if zone1.intersects(zone2) and not zone1.touches(zone2):
                    no_overlaps = False
                    break
            if not no_overlaps:
                break

        # Check coverage (union of all zones should equal court area)
        total_union = unary_union(zones_list)
        coverage_ratio = total_union.area / court_boundary.area
        complete_coverage = abs(coverage_ratio - 1.0) < 0.01  # 1% tolerance

        # Check if all polygons are valid
        all_valid_polygons = all(zone.is_valid and not zone.is_empty for zone in zones_list)

        return {
            'no_overlaps': no_overlaps,
            'complete_coverage': complete_coverage,
            'all_valid_polygons': all_valid_polygons,
            'coverage_ratio': coverage_ratio,
            'total_zones': len(self.zones)
        }


def create_detailed_zones(detail_level: str = 'detailed') -> DetailedCourtZones:
    """
    Convenience function to create detailed zones.

    Parameters:
    -----------
    detail_level : str
        Level of detail: 'basic', 'detailed', or 'advanced'

    Returns:
    --------
    DetailedCourtZones instance
    """
    return DetailedCourtZones(detail_level)


if __name__ == "__main__":
    print("Creating detailed court zone systems...")

    # Create detailed zones
    detailed_zones = create_detailed_zones('detailed')

    # Show zone statistics
    stats = detailed_zones.get_zone_statistics()
    print(f"\nDetailed system has {len(stats)} zones:")
    for zone_name, zone_stats in stats.items():
        print(f"  {zone_stats['name']}: {zone_stats['area']:.1f} m² ({zone_stats['points']} pts)")

    # Create comparison visualization
    fig = detailed_zones.compare_zone_systems("zone_systems_comparison.png")

    # Create detailed visualization
    fig2 = detailed_zones.plot_detailed_zones(
        title="Sistema de 8 Zonas Detalladas - FIBA",
        save_path="detailed_zones_8.png"
    )

    plt.show()
    print("Done!")