"""
FIBA Basketball Court Generator
Generates a half-court basketball court with official FIBA dimensions.

Official FIBA court dimensions from:
- https://www.fiba.basketball/documents/official-basketball-rules/2020.pdf
- https://www.fiba.basketball/documents/BasketballEquipment.pdf

All lengths are in meters.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon, Arc, Wedge
from matplotlib.collections import PatchCollection
from typing import Dict, Tuple, Optional, List
import re


class FIBACourt:
    """Class to generate and plot a FIBA half-court basketball court."""
    
    # Constants for arc smoothness
    THREE_POINT_ARC_POINTS = 100
    RESTRICTED_AREA_ARC_POINTS = 50
    KEY_CIRCLE_ARC_POINTS = 50
    
    # Default colors
    DEFAULT_COURT_COLOR = '#FFFFFF'
    DEFAULT_LINE_COLOR = '#000000'
    
    def __init__(self):
        """Initialize FIBA court dimensions (all in meters)."""
        # Court dimensions
        self.line_thick = 0.05
        self.width = 15
        self.height = 28 / 2  # Half court
        
        # Key (paint) dimensions
        self.key_height = 5.8
        self.key_width = 4.9
        self.key_radius = 1.8
        
        # Backboard dimensions
        self.backboard_width = 1.8
        self.backboard_thick = 0.1
        self.backboard_offset = 1.2
        
        # Hoop dimensions
        self.hoop_radius = 0.45 / 2
        self.hoop_center_y = 1.575
        self.rim_thick = 0.02
        
        # Three-point line dimensions
        self.three_point_radius = 6.75
        self.three_point_side_offset = 0.9
        
        # Restricted area
        self.restricted_area_radius = 1.25
    
    @property
    def neck_length(self) -> float:
        """Calculate the neck length connecting backboard to hoop."""
        return (self.hoop_center_y - 
                (self.backboard_offset + self.hoop_radius + self.rim_thick))
    
    @property
    def three_point_side_height(self) -> float:
        """Calculate the height where three-point arc meets vertical lines."""
        return (np.sqrt(self.three_point_radius**2 - 
                       (self.three_point_side_offset - self.width/2)**2) + 
                self.hoop_center_y)
    
    @property
    def court_center_x(self) -> float:
        """Get the x-coordinate of the court center."""
        return self.width / 2
        
    @staticmethod
    def _validate_color(color: str, param_name: str) -> None:
        """Validate color format (hex or named color)."""
        if not isinstance(color, str):
            raise ValueError(f"{param_name} must be a string")
        
        # Check for hex color
        if color.startswith('#'):
            if not re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', color):
                raise ValueError(f"{param_name} must be a valid hex color (e.g., '#FFFFFF' or '#FFF')")
        else:
            # For named colors, validate against matplotlib's color list
            from matplotlib import colors as mcolors
            if color.lower() not in mcolors.CSS4_COLORS and color.lower() not in mcolors.BASE_COLORS:
                raise ValueError(f"{param_name} '{color}' is not a valid color name. "
                               f"Use a hex color like '#FFFFFF' or a valid CSS color name.")
    
    @staticmethod
    def _validate_positive_int(value: int, param_name: str, min_value: int = 1) -> None:
        """Validate that a value is a positive integer."""
        if not isinstance(value, int) or value < min_value:
            raise ValueError(f"{param_name} must be an integer >= {min_value}")
    
    @staticmethod
    def _validate_figsize(figsize: Tuple[int, int]) -> None:
        """Validate figure size tuple."""
        if not isinstance(figsize, tuple) or len(figsize) != 2:
            raise ValueError("figsize must be a tuple of two integers (width, height)")
        if not all(isinstance(x, (int, float)) and x > 0 for x in figsize):
            raise ValueError("figsize values must be positive numbers")
    
    def _create_half_court_border(self) -> Polygon:
        """Create the half-court border."""
        outer = [
            [0 - self.line_thick, 0 - self.line_thick],
            [0 - self.line_thick, self.height + self.line_thick],
            [self.width + self.line_thick, self.height + self.line_thick],
            [self.width + self.line_thick, 0 - self.line_thick]
        ]
        inner = [
            [0, 0],
            [0, self.height],
            [self.width, self.height],
            [self.width, 0]
        ]
        # Return outer boundary as polygon (inner will be the court color)
        return Polygon(outer, closed=True)
    
    def _create_key(self) -> Polygon:
        """Create the key (paint area)."""
        key_points = [
            [self.court_center_x - self.key_width/2, 0],
            [self.court_center_x - self.key_width/2, self.key_height],
            [self.court_center_x + self.key_width/2, self.key_height],
            [self.court_center_x + self.key_width/2, 0]
        ]
        return Polygon(key_points, closed=True)
    
    def _create_backboard(self) -> Rectangle:
        """Create the backboard."""
        return Rectangle(
            (self.court_center_x - self.backboard_width/2, 
             self.backboard_offset - self.backboard_thick),
            self.backboard_width,
            self.backboard_thick
        )
    
    def _create_neck(self) -> Rectangle:
        """Create the neck connecting backboard to hoop."""
        return Rectangle(
            (self.court_center_x - self.line_thick/2, self.backboard_offset),
            self.line_thick,
            self.neck_length
        )
    
    def _create_hoop(self) -> Tuple[Circle, Circle]:
        """Create the hoop (rim)."""
        outer_circle = Circle(
            (self.court_center_x, self.hoop_center_y),
            self.hoop_radius + self.rim_thick
        )
        inner_circle = Circle(
            (self.court_center_x, self.hoop_center_y),
            self.hoop_radius
        )
        return outer_circle, inner_circle
    
    def _create_key_circle(self) -> Wedge:
        """Create the semi-circle at the top of the key."""
        return Wedge(
            (self.court_center_x, self.key_height),
            self.key_radius,
            0, 180
        )
    
    def _create_half_circle(self) -> Wedge:
        """Create the semi-circle at half court."""
        return Wedge(
            (self.court_center_x, self.height),
            self.key_radius,
            180, 360
        )
    
    def _create_three_point_line(self) -> Tuple[List[List[float]], List[List[float]], List[List[float]]]:
        """
        Create the three-point line.
        Returns separate lists for left line, arc, and right line.
        
        Returns:
        --------
        Tuple of (left_line, arc_points, right_line)
        """
        # Calculate the angle where the arc meets the vertical lines
        # At x = three_point_side_offset, we have:
        # (x - x_center)^2 + (y - hoop_center_y)^2 = three_point_radius^2
        # Solving for y:
        dx = self.three_point_side_offset - self.court_center_x
        y_at_break = self.hoop_center_y + np.sqrt(self.three_point_radius**2 - dx**2)
        
        # Calculate the angle at the break point (left side)
        angle_at_break = np.arctan2(y_at_break - self.hoop_center_y, 
                                     self.three_point_side_offset - self.court_center_x)
        
        # Create arc points from left break to right break
        # angle_at_break to (pi - angle_at_break)
        angles = np.linspace(angle_at_break, np.pi - angle_at_break, self.THREE_POINT_ARC_POINTS)
        arc_x = self.court_center_x + self.three_point_radius * np.cos(angles)
        arc_y = self.hoop_center_y + self.three_point_radius * np.sin(angles)
        
        # Arc points
        arc_points = [[x, y] for x, y in zip(arc_x, arc_y)]
        
        # Left side vertical line points - from baseline to arc start
        left_line = [
            [self.three_point_side_offset, 0],
            [self.three_point_side_offset, y_at_break]
        ]
        
        # Right side vertical line points - from arc end to baseline
        right_line = [
            [self.width - self.three_point_side_offset, y_at_break],
            [self.width - self.three_point_side_offset, 0]
        ]
        
        return left_line, arc_points, right_line
    
    def _create_restricted_area(self) -> Tuple[List[List[float]], List[List[float]], List[List[float]]]:
        """
        Create the restricted area (semi-circle under the basket).
        Returns separate lists for left line, arc, and right line.
        
        Returns:
        --------
        Tuple of (left_line, arc_points, right_line)
        """
        # Calculate the arc points (only upper half - from pi to 0 for left to right)
        angles = np.linspace(np.pi, 0, self.RESTRICTED_AREA_ARC_POINTS)  # Reversed: from pi (left) to 0 (right)
        arc_x = self.court_center_x + self.restricted_area_radius * np.cos(angles)
        arc_y = self.hoop_center_y + self.restricted_area_radius * np.sin(angles)
        
        # Arc points
        arc_points = [[x, y] for x, y in zip(arc_x, arc_y)]
        
        # Left vertical line - from backboard to start of arc
        left_line = [
            [self.court_center_x - self.restricted_area_radius, self.backboard_offset],
            [self.court_center_x - self.restricted_area_radius, self.hoop_center_y]
        ]
        
        # Right vertical line - from end of arc to backboard
        right_line = [
            [self.court_center_x + self.restricted_area_radius, self.hoop_center_y],
            [self.court_center_x + self.restricted_area_radius, self.backboard_offset]
        ]
        
        return left_line, arc_points, right_line
    
    def _draw_line_segments(self, ax: plt.Axes, segments: List[List[List[float]]], 
                           color: str, linewidth: float = 2, zorder: int = 3) -> None:
        """
        Helper method to draw multiple line segments.
        
        Parameters:
        -----------
        ax : matplotlib.axes.Axes
            The axes to draw on
        segments : List of line segments, where each segment is a list of [x, y] points
        color : str
            Line color
        linewidth : float
            Line width
        zorder : int
            Z-order for layering
        """
        for segment in segments:
            x_coords = [p[0] for p in segment]
            y_coords = [p[1] for p in segment]
            ax.plot(x_coords, y_coords, color=color, linewidth=linewidth, zorder=zorder)
    
    def _configure_patch(self, patch, facecolor: str, edgecolor: str, 
                        linewidth: float = 2, zorder: int = 3) -> None:
        """
        Helper method to configure patch properties.
        
        Parameters:
        -----------
        patch : matplotlib patch object
            The patch to configure
        facecolor : str
            Face color
        edgecolor : str
            Edge color
        linewidth : float
            Line width
        zorder : int
            Z-order for layering
        """
        patch.set_facecolor(facecolor)
        patch.set_edgecolor(edgecolor)
        patch.set_linewidth(linewidth)
        patch.set_zorder(zorder)
    
    def plot_court(self, 
                   court_color: str = '#FFFFFF',
                   line_color: str = '#000000',
                   figsize: Tuple[int, int] = (10, 10),
                   title: Optional[str] = None,
                   save_path: Optional[str] = None,
                   dpi: int = 150) -> plt.Figure:
        """
        Plot the FIBA half-court.
        
        Parameters:
        -----------
        court_color : str
            Color of the court background (default: white)
        line_color : str
            Color of the court lines (default: black)
        figsize : tuple
            Figure size (width, height)
        title : str, optional
            Title for the plot
        save_path : str, optional
            If provided, save the figure to this path
        dpi : int
            DPI for saved figure (default: 150)
            
        Returns:
        --------
        fig : matplotlib.figure.Figure
            The generated figure
            
        Raises:
        -------
        ValueError
            If any parameter is invalid
        """
        # Validate inputs
        self._validate_color(court_color, "court_color")
        self._validate_color(line_color, "line_color")
        self._validate_figsize(figsize)
        self._validate_positive_int(dpi, "dpi", min_value=50)
        
        fig, ax = plt.subplots(figsize=figsize, facecolor=court_color)
        ax.set_facecolor(court_color)
        
        # Set aspect ratio and limits
        ax.set_xlim(-0.5, self.width + 0.5)
        ax.set_ylim(-0.5, self.height + 0.5)
        ax.set_aspect('equal')
        
        # Remove axes
        ax.axis('off')
        
        # Add title if provided
        if title:
            ax.set_title(title, fontsize=16, color=line_color, pad=20)
        
        # Draw court elements
        self._draw_court_border(ax, court_color, line_color)
        self._draw_key_and_circles(ax, line_color)
        self._draw_three_point_line(ax, line_color)
        self._draw_restricted_area(ax, line_color)
        self._draw_backboard_and_hoop(ax, court_color, line_color)
        
        plt.tight_layout()
        
        # Save if path provided
        if save_path:
            plt.savefig(save_path, dpi=dpi, facecolor=court_color, 
                       edgecolor='none', bbox_inches='tight')
            print(f"Court saved to: {save_path}")
        
        return fig
    
    def _draw_court_border(self, ax: plt.Axes, court_color: str, line_color: str) -> None:
        """Draw the court border and background."""
        border = self._create_half_court_border()
        border_patch = plt.Polygon(border.get_xy(), 
                                   closed=True, 
                                   fill=True, 
                                   facecolor=line_color,
                                   edgecolor=line_color,
                                   linewidth=2,
                                   zorder=1)
        ax.add_patch(border_patch)
        
        # Add inner court (to create border effect)
        inner_court = Rectangle((0, 0), self.width, self.height,
                                facecolor=court_color,
                                edgecolor='none',
                                zorder=2)
        ax.add_patch(inner_court)
    
    def _draw_key_and_circles(self, ax: plt.Axes, line_color: str) -> None:
        """Draw the key and associated circles."""
        # The key
        key = self._create_key()
        key_patch = plt.Polygon(key.get_xy(), 
                               closed=True, 
                               fill=False,
                               edgecolor=line_color,
                               linewidth=2,
                               zorder=3)
        ax.add_patch(key_patch)
        
        # Key circle
        key_circle = self._create_key_circle()
        self._configure_patch(key_circle, 'none', line_color, linewidth=2, zorder=3)
        ax.add_patch(key_circle)
        
        # Half circle
        half_circle = self._create_half_circle()
        self._configure_patch(half_circle, 'none', line_color, linewidth=2, zorder=3)
        ax.add_patch(half_circle)
    
    def _draw_three_point_line(self, ax: plt.Axes, line_color: str) -> None:
        """Draw the three-point line."""
        left_line, arc_points, right_line = self._create_three_point_line()
        self._draw_line_segments(ax, [left_line, arc_points, right_line], 
                                line_color, linewidth=2, zorder=3)
    
    def _draw_restricted_area(self, ax: plt.Axes, line_color: str) -> None:
        """Draw the restricted area."""
        left_line, arc_points, right_line = self._create_restricted_area()
        self._draw_line_segments(ax, [left_line, arc_points, right_line], 
                                line_color, linewidth=2, zorder=3)
    
    def _draw_backboard_and_hoop(self, ax: plt.Axes, court_color: str, line_color: str) -> None:
        """Draw the backboard, neck, and hoop."""
        # Backboard
        backboard = self._create_backboard()
        self._configure_patch(backboard, line_color, line_color, linewidth=1, zorder=4)
        ax.add_patch(backboard)
        
        # Neck
        neck = self._create_neck()
        self._configure_patch(neck, line_color, line_color, linewidth=1, zorder=4)
        ax.add_patch(neck)
        
        # Hoop
        hoop_outer, hoop_inner = self._create_hoop()
        self._configure_patch(hoop_outer, line_color, line_color, linewidth=1, zorder=5)
        ax.add_patch(hoop_outer)
        
        self._configure_patch(hoop_inner, court_color, 'none', linewidth=1, zorder=6)
        ax.add_patch(hoop_inner)


def plot_court(court_color: str = '#FFFFFF',
               line_color: str = '#000000',
               figsize: Tuple[int, int] = (10, 10),
               title: Optional[str] = None,
               save_path: Optional[str] = None,
               dpi: int = 150) -> plt.Figure:
    """
    Convenience function to quickly plot a FIBA half-court.
    
    Parameters:
    -----------
    court_color : str
        Color of the court background (default: white)
    line_color : str
        Color of the court lines (default: black)
    figsize : tuple
        Figure size (width, height)
    title : str, optional
        Title for the plot
    save_path : str, optional
        If provided, save the figure to this path
    dpi : int
        DPI for saved figure (default: 150)
        
    Returns:
    --------
    fig : matplotlib.figure.Figure
        The generated figure
        
    Raises:
    -------
    ValueError
        If any parameter is invalid
    """
    court = FIBACourt()
    return court.plot_court(court_color=court_color,
                           line_color=line_color,
                           figsize=figsize,
                           title=title,
                           save_path=save_path,
                           dpi=dpi)


# Predefined court themes
COURT_THEMES = {
    'light': {
        'court': '#FFFFFF',  # White
        'lines': '#000000',   # Black
    },
    'wood': {
        'court': '#F4E9D8',  # Light wood
        'lines': '#000000',   # Black
    },
    'dark': {
        'court': '#2C2C2C',  # Dark gray
        'lines': '#FFFFFF',   # White
    },
    'classic': {
        'court': '#D2A679',  # Classic wood
        'lines': '#8B4513',   # Saddle brown
    },
    'modern': {
        'court': '#E8E8E8',  # Light gray
        'lines': '#1E3A8A',   # Royal blue
    }
}


def plot_court_with_theme(theme: str = 'light',
                          figsize: Tuple[int, int] = (10, 10),
                          title: Optional[str] = None,
                          save_path: Optional[str] = None,
                          dpi: int = 150) -> plt.Figure:
    """
    Plot a FIBA half-court with a predefined theme.
    
    Parameters:
    -----------
    theme : str
        Theme name: 'light', 'wood', 'dark', 'classic', or 'modern'
    figsize : tuple
        Figure size (width, height)
    title : str, optional
        Title for the plot
    save_path : str, optional
        If provided, save the figure to this path
    dpi : int
        DPI for saved figure (default: 150)
        
    Returns:
    --------
    fig : matplotlib.figure.Figure
        The generated figure
        
    Raises:
    -------
    ValueError
        If theme is not found or parameters are invalid
    """
    if theme not in COURT_THEMES:
        available_themes = ', '.join(COURT_THEMES.keys())
        raise ValueError(f"Theme '{theme}' not found. Available themes: {available_themes}")
    
    theme_colors = COURT_THEMES[theme]
    return plot_court(court_color=theme_colors['court'],
                     line_color=theme_colors['lines'],
                     figsize=figsize,
                     title=title,
                     save_path=save_path,
                     dpi=dpi)


if __name__ == "__main__":
    # Example usage
    print("Generating FIBA half-court...")
    
    # Create a court with light theme
    fig = plot_court_with_theme(
        theme='light',
        title='FIBA Half Court - Official Dimensions',
        save_path='fiba_half_court.png',
        figsize=(12, 12)
    )
    
    plt.show()
    print("Done!")
