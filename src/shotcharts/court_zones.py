"""
FIBA Basketball Court Zone Division
Manages court zones with proper geometric division to avoid overlapping areas.

This module creates non-overlapping zones for different shot point values:
- Zone 1: Inside restricted area (2 points)
- Zone 2: Key area excluding restricted area (2 points)
- Zone 3: Close 2-point area (2 points)
- Zone 4: Three-point area (3 points)

All zones are properly closed polygons with no overlaps.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
from typing import Dict, List, Tuple, Optional
from shapely.geometry import Polygon as ShapelyPolygon, Point
from shapely.ops import unary_union
import matplotlib.patches as mpatches

from .fiba_court import FIBACourt
from .court_renderer import CourtRenderer


class CourtZones:
    """Class to manage basketball court zones with proper geometric division."""

    def __init__(self):
        """Initialize court zones based on FIBA dimensions."""
        self.court = FIBACourt()
        self.court_renderer = CourtRenderer(self.court)
        self.zones = {}
        self._create_zones()

    def _create_closed_three_point_polygon(self) -> List[Tuple[float, float]]:
        """
        Create a closed polygon for the TWO-POINT area (inside the three-point line).

        Returns:
        --------
        List of (x, y) coordinates forming a closed polygon for the 2-point area
        """
        left_line, arc_points, right_line = self.court._create_three_point_line()

        # Start building the polygon that represents the 2-point area
        points = []

        # Start from baseline at left three-point line
        points.append((self.court.three_point_side_offset, 0))

        # Go up left three-point line to arc start
        points.extend([(x, y) for x, y in left_line])

        # Follow the three-point arc (this separates 2pt from 3pt)
        points.extend([(x, y) for x, y in arc_points])

        # Go down right three-point line to baseline
        points.extend([(x, y) for x, y in right_line])

        # Go along baseline back to start to close the polygon
        points.append((self.court.three_point_side_offset, 0))

        return points

    def _create_closed_restricted_area_polygon(self) -> List[Tuple[float, float]]:
        """
        Create a closed polygon for the restricted area.

        Returns:
        --------
        List of (x, y) coordinates forming a closed polygon
        """
        left_line, arc_points, right_line = self.court._create_restricted_area()

        points = []

        # Start from backboard left corner
        left_x = self.court.court_center_x - self.court.restricted_area_radius
        right_x = self.court.court_center_x + self.court.restricted_area_radius
        backboard_y = self.court.backboard_offset

        # Start from left bottom corner
        points.append((left_x, backboard_y))

        # Go up left line
        points.extend([(x, y) for x, y in left_line])

        # Follow the arc (from left to right)
        points.extend([(x, y) for x, y in arc_points])

        # Go down right line
        points.extend([(x, y) for x, y in right_line])

        # Go across backboard to close polygon (right to left)
        points.append((right_x, backboard_y))
        points.append((left_x, backboard_y))  # Close the polygon

        return points

    def _create_closed_key_polygon(self) -> List[Tuple[float, float]]:
        """
        Create a closed polygon for the key area.

        Returns:
        --------
        List of (x, y) coordinates forming a closed polygon
        """
        # Key rectangle coordinates
        points = [
            (self.court.court_center_x - self.court.key_width/2, 0),
            (self.court.court_center_x - self.court.key_width/2, self.court.key_height),
            (self.court.court_center_x + self.court.key_width/2, self.court.key_height),
            (self.court.court_center_x + self.court.key_width/2, 0),
            (self.court.court_center_x - self.court.key_width/2, 0)  # Close polygon
        ]

        return points

    def _create_zones(self) -> None:
        """Create all court zones as non-overlapping polygons."""

        # Create court boundary
        court_boundary = ShapelyPolygon([
            (0, 0),
            (0, self.court.height),
            (self.court.width, self.court.height),
            (self.court.width, 0),
            (0, 0)
        ])

        # Create the inner three-point area (2-point zone)
        three_point_points = self._create_closed_three_point_polygon()
        two_point_area = ShapelyPolygon(three_point_points)

        # Create key area
        key_points = self._create_closed_key_polygon()
        key_poly = ShapelyPolygon(key_points)

        # Create restricted area
        restricted_points = self._create_closed_restricted_area_polygon()
        restricted_poly = ShapelyPolygon(restricted_points)

        # Zone 1: Restricted area (2 points) - highest priority
        zone_restricted = restricted_poly

        # Zone 2: Key area minus restricted area (2 points)
        zone_key = key_poly.difference(restricted_poly)

        # Zone 3: Close 2-point area (inside three-point line but outside key)
        zone_close_two = two_point_area.difference(key_poly)

        # Zone 4: Three-point area (outside three-point line)
        zone_three_point = court_boundary.difference(two_point_area)

        # Store zones
        self.zones = {
            'restricted_area': {
                'polygon': zone_restricted,
                'points': 2,
                'color': '#FF6B6B',  # Light red
                'name': 'Área Restringida',
                'description': '2 puntos - Área bajo la canasta'
            },
            'key_area': {
                'polygon': zone_key,
                'points': 2,
                'color': '#4ECDC4',  # Teal
                'name': 'Zona',
                'description': '2 puntos - Zona menos área restringida'
            },
            'close_two_point': {
                'polygon': zone_close_two,
                'points': 2,
                'color': '#45B7D1',  # Light blue
                'name': 'Tiro Cercano',
                'description': '2 puntos - Fuera de la zona'
            },
            'three_point': {
                'polygon': zone_three_point,
                'points': 3,
                'color': '#96CEB4',  # Light green
                'name': 'Línea de Tres',
                'description': '3 puntos - Fuera de la línea de tres'
            }
        }

    def get_zone_for_shot(self, x: float, y: float) -> Dict:
        """
        Determine which zone a shot belongs to.

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
        point = Point(x, y)

        # Check zones in order of priority (most specific/smallest first)
        # This order is critical to avoid classification errors
        priority_order = [
            'restricted_area',  # Smallest, highest priority
            'key_area',         # Second smallest
            'close_two_point',  # Medium size
            'three_point'       # Largest, lowest priority
        ]

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

        # If no zone found, default to three-point
        return {
            'zone': 'three_point',
            'points': 3,
            'name': 'Línea de Tres',
            'description': '3 puntos - Fuera de la línea de tres'
        }

    def plot_zones(self,
                   figsize: Tuple[int, int] = (12, 10),
                   title: Optional[str] = None,
                   show_legend: bool = True,
                   alpha: float = 0.6,
                   save_path: Optional[str] = None,
                   dpi: int = 150) -> plt.Figure:
        """
        Plot the court with colored zones.

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
        # Create figure and axis
        fig, ax = plt.subplots(figsize=figsize, facecolor='white')
        ax.set_facecolor('white')

        # Set aspect ratio and limits
        ax.set_xlim(-0.5, self.court.width + 0.5)
        ax.set_ylim(-0.5, self.court.height + 0.5)
        ax.set_aspect('equal')

        # Remove axes
        ax.axis('off')

        # Add title if provided
        if title:
            ax.set_title(title, fontsize=16, color='black', pad=20)

        # First, add zone polygons in order of priority (largest first, so smallest appears on top)
        legend_elements = []

        # Define z-order: higher number = appears on top
        zone_zorder = {
            'three_point': 1,      # Largest area, bottom layer
            'close_two_point': 2,  # Second largest
            'key_area': 3,         # Third largest
            'restricted_area': 4   # Smallest area, top layer
        }

        for zone_name, zone_data in self.zones.items():
            polygon = zone_data['polygon']
            color = zone_data['color']
            name = zone_data['name']
            points = zone_data['points']
            zorder = zone_zorder.get(zone_name, 1)

            # Skip empty polygons
            if polygon.is_empty:
                continue

            # Convert Shapely polygon to matplotlib patches
            if polygon.geom_type == 'Polygon':
                # Single polygon
                coords = list(polygon.exterior.coords)
                if len(coords) > 2:  # Verificar que hay suficientes coordenadas
                    patch = mpatches.Polygon(coords,
                                           facecolor=color,
                                           alpha=alpha,
                                           edgecolor='darkgray',
                                           linewidth=1.0,
                                           zorder=zorder)
                    ax.add_patch(patch)

                # Handle holes if any
                for interior in polygon.interiors:
                    hole_coords = list(interior.coords)
                    if len(hole_coords) > 2:
                        hole_patch = mpatches.Polygon(hole_coords,
                                                    facecolor='white',
                                                    alpha=1.0,
                                                    edgecolor='darkgray',
                                                    linewidth=1.0,
                                                    zorder=zorder+0.1)
                        ax.add_patch(hole_patch)

            elif polygon.geom_type == 'MultiPolygon':
                # Multiple polygons
                for poly in polygon.geoms:
                    if not poly.is_empty:
                        coords = list(poly.exterior.coords)
                        if len(coords) > 2:
                            patch = mpatches.Polygon(coords,
                                                   facecolor=color,
                                                   alpha=alpha,
                                           edgecolor='darkgray',
                                           linewidth=1.0,
                                           zorder=zorder)
                            ax.add_patch(patch)

                            # Handle holes
                            for interior in poly.interiors:
                                hole_coords = list(interior.coords)
                                if len(hole_coords) > 2:
                                    hole_patch = mpatches.Polygon(hole_coords,
                                                                facecolor='white',
                                                                alpha=1.0,
                                                                edgecolor='darkgray',
                                                                linewidth=1.0,
                                                                zorder=zorder+0.1)
                                    ax.add_patch(hole_patch)

            elif polygon.geom_type == 'GeometryCollection':
                # Handle GeometryCollection (contains multiple geometry types)
                for geom in polygon.geoms:
                    if geom.geom_type == 'Polygon' and not geom.is_empty:
                        coords = list(geom.exterior.coords)
                        if len(coords) > 2:
                            patch = mpatches.Polygon(coords,
                                                   facecolor=color,
                                                   alpha=alpha,
                                                   edgecolor='darkgray',
                                                   linewidth=1.0,
                                                   zorder=zorder)
                            ax.add_patch(patch)

                            # Handle holes
                            for interior in geom.interiors:
                                hole_coords = list(interior.coords)
                                if len(hole_coords) > 2:
                                    hole_patch = mpatches.Polygon(hole_coords,
                                                                facecolor='white',
                                                                alpha=1.0,
                                                                edgecolor='darkgray',
                                                                linewidth=1.0,
                                                                zorder=zorder+0.1)
                                    ax.add_patch(hole_patch)
                    elif geom.geom_type == 'MultiPolygon':
                        # Handle MultiPolygon within GeometryCollection
                        for poly in geom.geoms:
                            coords = list(poly.exterior.coords)
                            patch = mpatches.Polygon(coords,
                                                   facecolor=color,
                                                   alpha=alpha,
                                                   edgecolor='darkgray',
                                                   linewidth=1.0,
                                                   zorder=zorder)
                            ax.add_patch(patch)

                            # Handle holes
                            for interior in poly.interiors:
                                hole_coords = list(interior.coords)
                                hole_patch = mpatches.Polygon(hole_coords,
                                                            facecolor='white',
                                                            alpha=1.0,
                                                            edgecolor='darkgray',
                                                            linewidth=1.0,
                                                            zorder=zorder+0.1)
                                ax.add_patch(hole_patch)

            # Add to legend
            legend_elements.append(
                mpatches.Patch(color=color,
                             label=f'{name} ({points} pts)',
                             alpha=alpha)
            )

        # Now draw court lines on top with higher zorder
        self._draw_court_lines_only(ax)

        # Add legend
        if show_legend:
            ax.legend(handles=legend_elements,
                     loc='upper left',
                     bbox_to_anchor=(1.02, 1),
                     frameon=True,
                     fancybox=True,
                     shadow=True)

        plt.tight_layout()

        # Save if path provided
        if save_path:
            plt.savefig(save_path, dpi=dpi, bbox_inches='tight', facecolor='white')
            print(f"Zones plot saved to: {save_path}")

        return fig

    def _draw_court_lines_only(self, ax: plt.Axes) -> None:
        """Draw only the court lines without background using unified renderer."""
        self.court_renderer.draw_court_elements(
            ax,
            line_color='#000000',
            line_width=2,
            zorder=10
        )

    def validate_zones(self) -> Dict[str, bool]:
        """
        Validate that zones don't overlap and cover the court properly.
        Also validates that three-point line and restricted area form proper closed polygons.

        Returns:
        --------
        Dict with validation results
        """
        results = {
            'no_overlaps': True,
            'covers_court': True,
            'zones_closed': True,
            'three_point_closed': True,
            'restricted_area_closed': True,
            'details': []
        }

        zone_polygons = [zone_data['polygon'] for zone_data in self.zones.values()]

        # Check for overlaps
        for i, poly1 in enumerate(zone_polygons):
            for j, poly2 in enumerate(zone_polygons[i+1:], i+1):
                if poly1.intersects(poly2) and not poly1.touches(poly2):
                    overlap_area = poly1.intersection(poly2).area
                    if overlap_area > 1e-10:  # Small tolerance for floating point
                        results['no_overlaps'] = False
                        zone_names = list(self.zones.keys())
                        results['details'].append(
                            f"Overlap detected between {zone_names[i]} and {zone_names[j]}: "
                            f"area = {overlap_area:.6f}"
                        )

        # Check if zones are closed (valid polygons)
        for zone_name, zone_data in self.zones.items():
            if not zone_data['polygon'].is_valid:
                results['zones_closed'] = False
                results['details'].append(f"Zone {zone_name} is not a valid polygon")

        # Validate three-point line closure
        three_point_points = self._create_closed_three_point_polygon()
        if len(three_point_points) < 4:  # Need at least 4 points for a polygon
            results['three_point_closed'] = False
            results['details'].append("Three-point line does not form a closed polygon")
        else:
            # Check if first and last points are the same (or very close)
            first_point = three_point_points[0]
            last_point = three_point_points[-1]
            distance = np.sqrt((first_point[0] - last_point[0])**2 +
                             (first_point[1] - last_point[1])**2)
            if distance > 1e-6:
                results['three_point_closed'] = False
                results['details'].append(
                    f"Three-point line not properly closed: distance = {distance:.8f}"
                )

        # Validate restricted area closure
        restricted_points = self._create_closed_restricted_area_polygon()
        if len(restricted_points) < 4:
            results['restricted_area_closed'] = False
            results['details'].append("Restricted area does not form a closed polygon")
        else:
            # Check if first and last points are the same (or very close)
            first_point = restricted_points[0]
            last_point = restricted_points[-1]
            distance = np.sqrt((first_point[0] - last_point[0])**2 +
                             (first_point[1] - last_point[1])**2)
            if distance > 1e-6:
                results['restricted_area_closed'] = False
                results['details'].append(
                    f"Restricted area not properly closed: distance = {distance:.8f}"
                )

        return results

    def get_zone_statistics(self) -> Dict[str, Dict]:
        """
        Get statistics for each zone.

        Returns:
        --------
        Dict with zone statistics
        """
        stats = {}

        for zone_name, zone_data in self.zones.items():
            polygon = zone_data['polygon']
            stats[zone_name] = {
                'area': polygon.area,
                'perimeter': polygon.length,
                'points': zone_data['points'],
                'name': zone_data['name'],
                'centroid': (polygon.centroid.x, polygon.centroid.y) if polygon.centroid else (0, 0)
            }

        return stats

    def validate_break_points(self) -> Dict[str, any]:
        """
        Validate that break points in three-point line and restricted area are properly handled.

        Returns:
        --------
        Dict with break point validation results
        """
        results = {
            'three_point_breaks_valid': True,
            'restricted_area_breaks_valid': True,
            'break_point_details': {},
            'details': []
        }

        # Get three-point line components
        left_line, arc_points, right_line = self.court._create_three_point_line()

        # Check three-point line break points
        if len(left_line) >= 2 and len(arc_points) >= 2:
            # Left break point: last point of left line should match first point of arc
            left_end = left_line[-1]
            arc_start = arc_points[0]
            left_break_distance = np.sqrt((left_end[0] - arc_start[0])**2 +
                                        (left_end[1] - arc_start[1])**2)

            results['break_point_details']['left_three_point_break'] = {
                'distance': left_break_distance,
                'left_end': left_end,
                'arc_start': arc_start
            }

            if left_break_distance > 1e-6:
                results['three_point_breaks_valid'] = False
                results['details'].append(
                    f"Left three-point break point mismatch: distance = {left_break_distance:.8f}"
                )

        if len(right_line) >= 2 and len(arc_points) >= 2:
            # Right break point: last point of arc should match first point of right line
            arc_end = arc_points[-1]
            right_start = right_line[0]
            right_break_distance = np.sqrt((arc_end[0] - right_start[0])**2 +
                                         (arc_end[1] - right_start[1])**2)

            results['break_point_details']['right_three_point_break'] = {
                'distance': right_break_distance,
                'arc_end': arc_end,
                'right_start': right_start
            }

            if right_break_distance > 1e-6:
                results['three_point_breaks_valid'] = False
                results['details'].append(
                    f"Right three-point break point mismatch: distance = {right_break_distance:.8f}"
                )

        # Get restricted area components
        rest_left_line, rest_arc_points, rest_right_line = self.court._create_restricted_area()

        # Check restricted area break points
        if len(rest_left_line) >= 2 and len(rest_arc_points) >= 2:
            # Left break point
            rest_left_end = rest_left_line[-1]
            rest_arc_start = rest_arc_points[0]
            rest_left_break_distance = np.sqrt((rest_left_end[0] - rest_arc_start[0])**2 +
                                             (rest_left_end[1] - rest_arc_start[1])**2)

            results['break_point_details']['left_restricted_break'] = {
                'distance': rest_left_break_distance,
                'left_end': rest_left_end,
                'arc_start': rest_arc_start
            }

            if rest_left_break_distance > 1e-6:
                results['restricted_area_breaks_valid'] = False
                results['details'].append(
                    f"Left restricted area break point mismatch: distance = {rest_left_break_distance:.8f}"
                )

        if len(rest_right_line) >= 2 and len(rest_arc_points) >= 2:
            # Right break point
            rest_arc_end = rest_arc_points[-1]
            rest_right_start = rest_right_line[0]
            rest_right_break_distance = np.sqrt((rest_arc_end[0] - rest_right_start[0])**2 +
                                               (rest_arc_end[1] - rest_right_start[1])**2)

            results['break_point_details']['right_restricted_break'] = {
                'distance': rest_right_break_distance,
                'arc_end': rest_arc_end,
                'right_start': rest_right_start
            }

            if rest_right_break_distance > 1e-6:
                results['restricted_area_breaks_valid'] = False
                results['details'].append(
                    f"Right restricted area break point mismatch: distance = {rest_right_break_distance:.8f}"
                )

        return results

    def export_zone_definitions(self, file_path: Optional[str] = None) -> Dict:
        """
        Export zone definitions to JSON format for use in other systems.

        Parameters:
        -----------
        file_path : str, optional
            If provided, save the definitions to this JSON file

        Returns:
        --------
        Dict with zone definitions
        """
        import json
        from datetime import datetime

        zone_definitions = {
            'metadata': {
                'created': datetime.now().isoformat(),
                'court_type': 'FIBA_half_court',
                'dimensions': {
                    'width': self.court.width,
                    'height': self.court.height,
                    'units': 'meters'
                },
                'validation': self.validate_zones(),
                'break_points': self.validate_break_points()
            },
            'zones': {}
        }

        for zone_name, zone_data in self.zones.items():
            polygon = zone_data['polygon']

            # Extract coordinates
            if polygon.geom_type == 'Polygon':
                coordinates = [list(polygon.exterior.coords)]
                # Add holes if any
                for interior in polygon.interiors:
                    coordinates.append(list(interior.coords))
            elif polygon.geom_type == 'MultiPolygon':
                coordinates = []
                for poly in polygon.geoms:
                    poly_coords = [list(poly.exterior.coords)]
                    for interior in poly.interiors:
                        poly_coords.append(list(interior.coords))
                    coordinates.append(poly_coords)
            elif polygon.geom_type == 'GeometryCollection':
                coordinates = []
                for geom in polygon.geoms:
                    if geom.geom_type == 'Polygon':
                        geom_coords = [list(geom.exterior.coords)]
                        for interior in geom.interiors:
                            geom_coords.append(list(interior.coords))
                        coordinates.append(geom_coords)
                    elif geom.geom_type == 'MultiPolygon':
                        for poly in geom.geoms:
                            poly_coords = [list(poly.exterior.coords)]
                            for interior in poly.interiors:
                                poly_coords.append(list(interior.coords))
                            coordinates.append(poly_coords)
            else:
                coordinates = []

            zone_definitions['zones'][zone_name] = {
                'name': zone_data['name'],
                'description': zone_data['description'],
                'points': zone_data['points'],
                'color': zone_data['color'],
                'geometry': {
                    'type': polygon.geom_type,
                    'coordinates': coordinates
                },
                'statistics': {
                    'area': polygon.area,
                    'perimeter': polygon.length,
                    'centroid': [polygon.centroid.x, polygon.centroid.y] if polygon.centroid else [0, 0]
                }
            }

        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(zone_definitions, f, indent=2, ensure_ascii=False)
            print(f"Zone definitions exported to: {file_path}")

        return zone_definitions


def plot_court_zones(figsize: Tuple[int, int] = (12, 10),
                     title: str = "FIBA Court - Zonas de Puntuación",
                     save_path: Optional[str] = None) -> plt.Figure:
    """
    Convenience function to plot court zones.

    Parameters:
    -----------
    figsize : tuple
        Figure size
    title : str
        Plot title
    save_path : str, optional
        Path to save the figure

    Returns:
    --------
    matplotlib.figure.Figure
    """
    zones = CourtZones()
    return zones.plot_zones(figsize=figsize, title=title, save_path=save_path)


if __name__ == "__main__":
    # Example usage
    print("Creating court zones...")

    zones = CourtZones()

    # Validate zones
    validation = zones.validate_zones()
    print(f"Validation results: {validation}")

    # Get statistics
    stats = zones.get_zone_statistics()
    print("\nZone Statistics:")
    for zone_name, zone_stats in stats.items():
        print(f"{zone_name}:")
        print(f"  - Area: {zone_stats['area']:.2f} m²")
        print(f"  - Points: {zone_stats['points']}")
        print(f"  - Name: {zone_stats['name']}")

    # Plot zones
    fig = zones.plot_zones(
        title="FIBA Court - Zonas de Puntuación sin Solapamiento",
        save_path="court_zones.png"
    )

    plt.show()
    print("Done!")