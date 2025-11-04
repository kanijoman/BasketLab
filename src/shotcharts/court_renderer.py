"""
Court rendering utilities for FIBA basketball court visualizations.

This module provides a unified interface for rendering court elements,
eliminating code duplication across different visualizers.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from typing import Optional

from .fiba_court import FIBACourt


class CourtRenderer:
    """
    Unified court rendering utility.

    Provides a single source of truth for drawing FIBA court elements
    with consistent styling and proper z-order management.
    """

    def __init__(self, court: Optional[FIBACourt] = None):
        """
        Initialize court renderer.

        Parameters:
        -----------
        court : FIBACourt, optional
            FIBA court instance. If None, creates a new one.
        """
        self.court = court if court is not None else FIBACourt()

    def draw_court_elements(self,
                          ax: plt.Axes,
                          line_color: str = 'black',
                          line_width: float = 2,
                          zorder: int = 10) -> None:
        """
        Draw all court elements on the given axes with proper z-order.

        This is the main method for rendering a complete court with all elements.

        Parameters:
        -----------
        ax : plt.Axes
            Matplotlib axes to draw on
        line_color : str
            Color for court lines (default: 'black')
        line_width : float
            Width of court lines (default: 2)
        zorder : int
            Z-order for court elements (default: 10)
        """
        # Backboard
        backboard_x = [
            self.court.court_center_x - self.court.backboard_width / 2,
            self.court.court_center_x + self.court.backboard_width / 2
        ]
        backboard_y = [self.court.backboard_offset, self.court.backboard_offset]
        ax.plot(backboard_x, backboard_y, color=line_color,
               linewidth=line_width * 2, zorder=zorder)

        # Hoop
        hoop = plt.Circle(
            (self.court.court_center_x, self.court.hoop_center_y),
            self.court.hoop_radius,
            fill=False,
            color=line_color,
            linewidth=line_width * 1.5,
            zorder=zorder
        )
        ax.add_patch(hoop)

        # Key rectangle
        key_rect = plt.Rectangle(
            (self.court.court_center_x - self.court.key_width / 2, 0),
            self.court.key_width,
            self.court.key_height,
            fill=False,
            edgecolor=line_color,
            linewidth=line_width,
            zorder=zorder
        )
        ax.add_patch(key_rect)

        # Key circle (free throw circle)
        key_circle = plt.Circle(
            (self.court.court_center_x, self.court.key_height),
            self.court.key_radius,
            fill=False,
            color=line_color,
            linewidth=line_width,
            zorder=zorder
        )
        ax.add_patch(key_circle)

        # Restricted area
        restricted_area = plt.Circle(
            (self.court.court_center_x, self.court.hoop_center_y),
            self.court.restricted_area_radius,
            fill=False,
            color=line_color,
            linewidth=line_width,
            zorder=zorder
        )
        ax.add_patch(restricted_area)

        # Three-point line components
        self._draw_three_point_line(ax, line_color, line_width, zorder)

        # Court boundary
        court_boundary = plt.Rectangle(
            (0, 0),
            self.court.width,
            self.court.height,
            fill=False,
            edgecolor=line_color,
            linewidth=line_width * 1.5,
            zorder=zorder
        )
        ax.add_patch(court_boundary)

    def _draw_three_point_line(self,
                               ax: plt.Axes,
                               line_color: str,
                               line_width: float,
                               zorder: int) -> None:
        """
        Draw the three-point line (arc and sides).

        Parameters:
        -----------
        ax : plt.Axes
            Matplotlib axes to draw on
        line_color : str
            Color for the line
        line_width : float
            Width of the line
        zorder : int
            Z-order for the line
        """
        three_point_left_x = self.court.three_point_side_offset
        three_point_right_x = self.court.width - self.court.three_point_side_offset
        three_point_height = self.court.three_point_side_height

        # Left and right three-point lines
        ax.plot(
            [three_point_left_x, three_point_left_x],
            [0, three_point_height],
            color=line_color,
            linewidth=line_width,
            zorder=zorder
        )
        ax.plot(
            [three_point_right_x, three_point_right_x],
            [0, three_point_height],
            color=line_color,
            linewidth=line_width,
            zorder=zorder
        )

        # Three-point arc
        theta_start = np.arcsin(
            (three_point_left_x - self.court.court_center_x) / self.court.three_point_radius
        )
        theta_end = np.arcsin(
            (three_point_right_x - self.court.court_center_x) / self.court.three_point_radius
        )
        theta = np.linspace(theta_start, theta_end, 100)
        arc_x = self.court.court_center_x + self.court.three_point_radius * np.sin(theta)
        arc_y = self.court.hoop_center_y + self.court.three_point_radius * np.cos(theta)
        ax.plot(arc_x, arc_y, color=line_color, linewidth=line_width, zorder=zorder)

    def draw_court_lines_only(self,
                              ax: plt.Axes,
                              line_color: str = 'black',
                              line_width: float = 2,
                              zorder: int = 10) -> None:
        """
        Draw court lines without filling or background.

        Alias for draw_court_elements for backwards compatibility.

        Parameters:
        -----------
        ax : plt.Axes
            Matplotlib axes to draw on
        line_color : str
            Color for court lines (default: 'black')
        line_width : float
            Width of court lines (default: 2)
        zorder : int
            Z-order for court elements (default: 10)
        """
        self.draw_court_elements(ax, line_color, line_width, zorder)

    def setup_court_axes(self,
                        ax: plt.Axes,
                        background_color: str = '#f8f8f8',
                        remove_ticks: bool = True,
                        remove_spines: bool = False) -> None:
        """
        Set up axes for court visualization with proper limits and styling.

        Parameters:
        -----------
        ax : plt.Axes
            Matplotlib axes to set up
        background_color : str
            Background color for the court (default: '#f8f8f8')
        remove_ticks : bool
            Whether to remove axis ticks (default: True)
        remove_spines : bool
            Whether to remove axis spines (default: False)
        """
        # Set court dimensions and background
        ax.set_xlim(0, self.court.width)  # FIBA court width (15m)
        ax.set_ylim(0, self.court.height)  # FIBA half-court length (14m)
        ax.set_facecolor(background_color)
        ax.set_aspect('equal')

        if remove_ticks:
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_xlabel('')
            ax.set_ylabel('')

        if remove_spines:
            for spine in ax.spines.values():
                spine.set_visible(False)


def create_court_renderer(court: Optional[FIBACourt] = None) -> CourtRenderer:
    """
    Factory function to create a CourtRenderer instance.

    Parameters:
    -----------
    court : FIBACourt, optional
        FIBA court instance. If None, creates a new one.

    Returns:
    --------
    CourtRenderer
        Configured court renderer instance
    """
    return CourtRenderer(court)
