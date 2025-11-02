"""
Shot Chart Visualizer for FIBA Basketball Courts
Visualizes shot data from FEB games on a FIBA half-court.

The FEB JSON format uses coordinates 0-100 for a full horizontal court.
This module converts those coordinates to FIBA half-court dimensions.
"""

import json
import matplotlib.pyplot as plt
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path
import numpy as np

from .fiba_court import FIBACourt, plot_court


class ShotChartVisualizer:
    """
    Visualize basketball shots on a FIBA half-court.
    
    Converts FEB JSON coordinate system (0-100 for full horizontal court)
    to FIBA half-court coordinates (meters, vertical orientation).
    """
    
    # FEB court dimensions (assumed based on FIBA standard)
    FEB_COURT_LENGTH = 28.0  # meters (full court)
    FEB_COURT_WIDTH = 15.0   # meters
    
    # Shot markers configuration
    MADE_SHOT_COLOR = 'green'
    MISSED_SHOT_COLOR = 'red'
    MADE_SHOT_MARKER = 'o'
    MISSED_SHOT_MARKER = 'x'
    SHOT_SIZE = 100
    SHOT_ALPHA = 0.7
    SHOT_EDGE_WIDTH = 2
    MADE_EDGE_COLOR = 'darkgreen'
    
    # Legend configuration
    LEGEND_FONTSIZE = 11
    LEGEND_FRAMEALPHA = 0.95
    LEGEND_BBOX_ANCHOR = (0.5, -0.05)
    LEGEND_NCOL = 2
    
    def __init__(self):
        """Initialize the shot chart visualizer."""
        self.court = FIBACourt()
    
    @staticmethod
    def _validate_shot_data(shot: Dict) -> bool:
        """
        Validate that a shot dictionary contains required fields.
        
        Parameters:
        -----------
        shot : dict
            Shot data dictionary
            
        Returns:
        --------
        bool
            True if valid, False otherwise
        """
        required_fields = ['m', 'x', 'y', 'team', 'player', 'quarter']
        return all(field in shot for field in required_fields)
    
    @staticmethod
    def _filter_shots(shots: List[Dict],
                     team: Optional[int] = None,
                     quarter: Optional[int] = None,
                     player: Optional[Union[int, str]] = None) -> List[Dict]:
        """
        Filter shots by team, quarter, and/or player.
        
        Parameters:
        -----------
        shots : list
            List of shot dictionaries
        team : int, optional
            Filter by team (0=home, 1=away)
        quarter : int, optional
            Filter by quarter (1-4)
        player : int or str, optional
            Filter by player number/dorsal
            
        Returns:
        --------
        list
            Filtered list of shots
        """
        filtered = shots
        
        if team is not None:
            filtered = [s for s in filtered if int(s['team']) == team]
        
        if quarter is not None:
            filtered = [s for s in filtered if int(s['quarter']) == quarter]
        
        if player is not None:
            player_str = str(player)
            filtered = [s for s in filtered if str(s['player']) == player_str]
        
        return filtered
    
    def _convert_feb_to_fiba(self, x_feb: float, y_feb: float, 
                            team: int) -> Tuple[float, float]:
        """
        Convert FEB coordinates (0-100, full horizontal court) 
        to FIBA half-court coordinates (meters, vertical).
        
        All shots are mirrored to show on the offensive half-court,
        so shots from the defensive half are reflected specularly.
        
        FEB coordinate system:
        - Full court, horizontal orientation (28m length x 15m width)
        - x: 0-100 along court length (28m), 0 at one basket, 100 at the other
        - y: 0-100 along court width (15m), 0 at bottom, 100 at top
        - Team 0 attacks basket at x=0, Team 1 attacks basket at x=100
        
        FIBA half-court system (this visualization):
        - Half court, vertical orientation
        - x: 0-15m (court width, horizontal in display)
        - y: 0-14m (half court length, vertical in display, 0 at baseline/basket)
        - Single basket at y=0
        
        Conversion strategy:
        1. Convert percentages to meters
        2. Calculate distance from attacking basket
        3. If shot is from defensive half (>14m), mirror it to offensive half
        4. Mirror across center line: reflected_distance = 28m - distance
        5. Rotate coordinates: FEB's y becomes FIBA's x, FEB's x becomes FIBA's y
        
        Parameters:
        -----------
        x_feb : float
            X coordinate from FEB JSON (0-100), along court length
        y_feb : float
            Y coordinate from FEB JSON (0-100), along court width
        team : int
            Team identifier (0=home, 1=away)
            
        Returns:
        --------
        tuple
            (x_fiba, y_fiba) in meters, always in offensive half (0-14m)
        """
        # Convert percentage to meters
        x_meters = (x_feb / 100.0) * self.FEB_COURT_LENGTH  # 0-28m along court length
        y_meters = (y_feb / 100.0) * self.FEB_COURT_WIDTH   # 0-15m along court width
        
        # Determine distance from attacking basket
        # Team 0 attacks x=0, Team 1 attacks x=100 (x=28m)
        if team == 0:
            # Distance from team 0's basket (at x=0)
            distance_from_basket = x_meters
        else:
            # Distance from team 1's basket (at x=28m)
            distance_from_basket = self.FEB_COURT_LENGTH - x_meters
        
        # Mirror shots from defensive half to offensive half
        # If shot is beyond half court (>14m), reflect it specularly
        if distance_from_basket > self.FEB_COURT_LENGTH / 2:
            # Mirror: if shot is at 20m, it becomes 28-20 = 8m (mirrored)
            y_fiba = self.FEB_COURT_LENGTH - distance_from_basket
            # Also mirror the x-coordinate (width)
            x_fiba = self.FEB_COURT_WIDTH - y_meters
        else:
            # Shot is in offensive half, keep as is
            y_fiba = distance_from_basket
            x_fiba = y_meters
        
        return x_fiba, y_fiba
    
    def _convert_and_classify_shots(self, shots: List[Dict]) -> Tuple[Tuple[List[float], List[float]], 
                                                                        Tuple[List[float], List[float]]]:
        """
        Convert shot coordinates from FEB to FIBA and classify as made/missed.
        
        Parameters:
        -----------
        shots : list
            List of shot dictionaries
            
        Returns:
        --------
        tuple
            ((made_x, made_y), (missed_x, missed_y)) - coordinates in FIBA meters
        """
        made_shots_x = []
        made_shots_y = []
        missed_shots_x = []
        missed_shots_y = []
        
        for shot in shots:
            x_feb = float(shot['x'])
            y_feb = float(shot['y'])
            shot_team = int(shot['team'])
            made = int(shot['m']) == 1
            
            # Convert coordinates (automatically mirrors defensive shots)
            x_fiba, y_fiba = self._convert_feb_to_fiba(x_feb, y_feb, shot_team)
            
            # Classify shot
            if made:
                made_shots_x.append(x_fiba)
                made_shots_y.append(y_fiba)
            else:
                missed_shots_x.append(x_fiba)
                missed_shots_y.append(y_fiba)
        
        return (made_shots_x, made_shots_y), (missed_shots_x, missed_shots_y)
    
    def _plot_shot_scatter(self, ax: plt.Axes, x_coords: List[float], y_coords: List[float],
                          is_made: bool) -> None:
        """
        Plot a scatter of shots (made or missed).
        
        Parameters:
        -----------
        ax : matplotlib.axes.Axes
            The axes to plot on
        x_coords : list
            X coordinates of shots
        y_coords : list
            Y coordinates of shots
        is_made : bool
            True for made shots, False for missed shots
        """
        if not x_coords:
            return
        
        if is_made:
            ax.scatter(x_coords, y_coords,
                      c=self.MADE_SHOT_COLOR,
                      s=self.SHOT_SIZE,
                      marker=self.MADE_SHOT_MARKER,
                      alpha=self.SHOT_ALPHA,
                      edgecolors=self.MADE_EDGE_COLOR,
                      linewidth=self.SHOT_EDGE_WIDTH,
                      zorder=10,
                      label=f'Made ({len(x_coords)})')
        else:
            ax.scatter(x_coords, y_coords,
                      c=self.MISSED_SHOT_COLOR,
                      s=self.SHOT_SIZE,
                      marker=self.MISSED_SHOT_MARKER,
                      alpha=self.SHOT_ALPHA,
                      linewidth=self.SHOT_EDGE_WIDTH,
                      zorder=10,
                      label=f'Missed ({len(x_coords)})')
    
    def _add_legend(self, ax: plt.Axes, legend_loc: str, has_shots: bool) -> None:
        """
        Add legend to the plot.
        
        Parameters:
        -----------
        ax : matplotlib.axes.Axes
            The axes to add legend to
        legend_loc : str
            Legend location
        has_shots : bool
            Whether there are shots to show in legend
        """
        if not has_shots:
            return
        
        if legend_loc == 'lower center':
            # Place below the court, outside the plot area
            ax.legend(loc='upper center', bbox_to_anchor=self.LEGEND_BBOX_ANCHOR,
                     ncol=self.LEGEND_NCOL, fontsize=self.LEGEND_FONTSIZE, 
                     framealpha=self.LEGEND_FRAMEALPHA, edgecolor='black', 
                     fancybox=True, shadow=True)
        else:
            # Use standard matplotlib location
            ax.legend(loc=legend_loc, fontsize=10, framealpha=self.LEGEND_FRAMEALPHA,
                     edgecolor='black', fancybox=True, shadow=True)
    
    def _add_default_title(self, ax: plt.Axes, made_count: int, total_count: int,
                          line_color: str) -> None:
        """
        Add default title with shot statistics if no title provided.
        
        Parameters:
        -----------
        ax : matplotlib.axes.Axes
            The axes to add title to
        made_count : int
            Number of made shots
        total_count : int
            Total number of shots
        line_color : str
            Color for the title text
        """
        if total_count > 0:
            accuracy = (made_count / total_count) * 100
            title = f'Shot Chart - {made_count}/{total_count} ({accuracy:.1f}%)'
            ax.set_title(title, fontsize=16, color=line_color, pad=20)
    
    def load_shots_from_json(self, json_path: Union[str, Path]) -> List[Dict]:
        """
        Load shot data from FEB JSON file.
        
        Parameters:
        -----------
        json_path : str or Path
            Path to the JSON file
            
        Returns:
        --------
        list
            List of shot dictionaries
            
        Raises:
        -------
        FileNotFoundError
            If JSON file doesn't exist
        ValueError
            If JSON structure is invalid
        """
        json_path = Path(json_path)
        if not json_path.exists():
            raise FileNotFoundError(f"JSON file not found: {json_path}")
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'SHOTCHART' not in data:
                raise ValueError("JSON file doesn't contain SHOTCHART node")
            
            if 'SHOTS' not in data['SHOTCHART']:
                raise ValueError("SHOTCHART doesn't contain SHOTS array")
            
            shots = data['SHOTCHART']['SHOTS']
            
            # Validate shots
            valid_shots = [s for s in shots if self._validate_shot_data(s)]
            
            if len(valid_shots) < len(shots):
                print(f"Warning: {len(shots) - len(valid_shots)} shots have invalid data and were skipped")
            
            return valid_shots
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON file: {e}")
    
    def plot_shots(self,
                   shots: List[Dict],
                   team: Optional[int] = None,
                   quarter: Optional[int] = None,
                   player: Optional[Union[int, str]] = None,
                   court_color: str = '#FFFFFF',
                   line_color: str = '#000000',
                   figsize: Tuple[int, int] = (12, 12),
                   title: Optional[str] = None,
                   show_legend: bool = True,
                   legend_loc: str = 'lower center',
                   save_path: Optional[str] = None,
                   dpi: int = 150) -> plt.Figure:
        """
        Plot shots on a FIBA half-court.
        
        All shots are automatically mirrored to show on the offensive half,
        so shots from the defensive half are reflected specularly.
        
        Parameters:
        -----------
        shots : list
            List of shot dictionaries from JSON
        team : int, optional
            Filter by team (0=home, 1=away). If None, show all teams
        quarter : int, optional
            Filter by quarter (1-4). If None, show all quarters
        player : int or str, optional
            Filter by player number/dorsal. If None, show all players
        court_color : str
            Color of the court background
        line_color : str
            Color of the court lines
        figsize : tuple
            Figure size (width, height)
        title : str, optional
            Title for the plot
        show_legend : bool
            Whether to show the legend
        legend_loc : str
            Location for the legend. Options: 'lower center' (default, below court),
            'upper left', 'upper right', 'lower left', 'lower right'
        save_path : str, optional
            If provided, save the figure to this path
        dpi : int
            DPI for saved figure
            
        Returns:
        --------
        fig : matplotlib.figure.Figure
            The generated figure
        """
        # Filter shots based on criteria
        filtered_shots = self._filter_shots(shots, team, quarter, player)
        
        if not filtered_shots:
            print("Warning: No shots match the specified filters")
        
        # Create court
        fig = self.court.plot_court(
            court_color=court_color,
            line_color=line_color,
            figsize=figsize,
            title=title,
            save_path=None  # We'll save after adding shots
        )
        
        ax = fig.axes[0]
        
        # Convert coordinates and classify shots
        (made_x, made_y), (missed_x, missed_y) = self._convert_and_classify_shots(filtered_shots)
        
        # Plot shots
        self._plot_shot_scatter(ax, made_x, made_y, is_made=True)
        self._plot_shot_scatter(ax, missed_x, missed_y, is_made=False)
        
        # Add legend if requested
        has_shots = bool(made_x or missed_x)
        if show_legend:
            self._add_legend(ax, legend_loc, has_shots)
        
        # Add default title if not provided
        if not title:
            self._add_default_title(ax, len(made_x), len(made_x) + len(missed_x), line_color)
        
        plt.tight_layout()
        
        # Save if path provided
        if save_path:
            plt.savefig(save_path, dpi=dpi, facecolor=court_color,
                       edgecolor='none', bbox_inches='tight')
            print(f"Shot chart saved to: {save_path}")
        
        return fig
    
    def plot_shots_from_json(self,
                            json_path: Union[str, Path],
                            **kwargs) -> plt.Figure:
        """
        Convenience method to load and plot shots from JSON in one step.
        
        Parameters:
        -----------
        json_path : str or Path
            Path to the JSON file
        **kwargs
            Additional arguments passed to plot_shots()
            
        Returns:
        --------
        fig : matplotlib.figure.Figure
            The generated figure
        """
        shots = self.load_shots_from_json(json_path)
        return self.plot_shots(shots, **kwargs)


def plot_shot_chart(json_path: Union[str, Path],
                    team: Optional[int] = None,
                    quarter: Optional[int] = None,
                    player: Optional[Union[int, str]] = None,
                    **kwargs) -> plt.Figure:
    """
    Convenience function to quickly create a shot chart from JSON.
    
    Parameters:
    -----------
    json_path : str or Path
        Path to the FEB JSON file
    team : int, optional
        Filter by team (0=home, 1=away)
    quarter : int, optional
        Filter by quarter (1-4)
    player : int or str, optional
        Filter by player number/dorsal
    **kwargs
        Additional arguments passed to plot_shots()
        
    Returns:
    --------
    fig : matplotlib.figure.Figure
        The generated figure
    """
    visualizer = ShotChartVisualizer()
    return visualizer.plot_shots_from_json(
        json_path,
        team=team,
        quarter=quarter,
        player=player,
        **kwargs
    )


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        json_file = "src/JSON_samples/feb_game.json"
    
    print(f"Loading shots from: {json_file}")
    
    visualizer = ShotChartVisualizer()
    shots = visualizer.load_shots_from_json(json_file)
    
    print(f"Loaded {len(shots)} shots")
    
    # Plot all shots from home team (team 0)
    fig = visualizer.plot_shots(
        shots,
        team=0,
        title="Home Team Shot Chart",
        save_path="shot_chart_home.png"
    )
    
    plt.show()
