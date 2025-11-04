"""
Coordinate conversion utilities for basketball court visualizations.

This module provides utilities for converting between different coordinate systems:
- FEB coordinates (0-100 percentage scale, full court)
- FIBA coordinates (meters, half-court)
"""

from typing import Tuple, List, Dict


# Court dimensions constants
FEB_COURT_LENGTH = 28.0  # Full court length in meters
FEB_COURT_WIDTH = 15.0   # Court width in meters
FIBA_HALF_COURT_LENGTH = 14.0  # Half court length in meters


def convert_feb_to_fiba(x_feb: float, y_feb: float, team: int) -> Tuple[float, float]:
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
    Tuple[float, float]
        (x_fiba, y_fiba) in meters, always in offensive half (0-14m)
    """
    # Convert percentage to meters
    x_meters = (x_feb / 100.0) * FEB_COURT_LENGTH  # 0-28m along court length
    y_meters = (y_feb / 100.0) * FEB_COURT_WIDTH   # 0-15m along court width

    # Determine distance from attacking basket
    # Team 0 attacks x=0, Team 1 attacks x=100 (x=28m)
    if team == 0:
        # Distance from team 0's basket (at x=0)
        distance_from_basket = x_meters
    else:
        # Distance from team 1's basket (at x=28m)
        distance_from_basket = FEB_COURT_LENGTH - x_meters

    # Mirror shots from defensive half to offensive half
    # If shot is beyond half court (>14m), reflect it specularly
    if distance_from_basket > FEB_COURT_LENGTH / 2:
        # Mirror: if shot is at 20m, it becomes 28-20 = 8m (mirrored)
        y_fiba = FEB_COURT_LENGTH - distance_from_basket
        # Also mirror the x-coordinate (width)
        x_fiba = FEB_COURT_WIDTH - y_meters
    else:
        # Shot is in offensive half, keep as is
        y_fiba = distance_from_basket
        x_fiba = y_meters

    return x_fiba, y_fiba


def convert_shot_to_fiba(shot: Dict) -> Dict:
    """
    Convert a single FEB shot dictionary to FIBA coordinates.

    Parameters:
    -----------
    shot : Dict
        Shot dictionary with 'x', 'y', and 'team' keys

    Returns:
    --------
    Dict
        Updated shot dictionary with FIBA coordinates
    """
    x_feb = float(shot.get('x', 0))
    y_feb = float(shot.get('y', 0))
    team = int(shot.get('team', 0))

    fiba_x, fiba_y = convert_feb_to_fiba(x_feb, y_feb, team)

    # Create new dict with FIBA coordinates
    fiba_shot = shot.copy()
    fiba_shot['x_fiba'] = fiba_x
    fiba_shot['y_fiba'] = fiba_y
    fiba_shot['x_feb'] = x_feb
    fiba_shot['y_feb'] = y_feb

    return fiba_shot


def convert_shots_to_fiba(shots: List[Dict]) -> List[Dict]:
    """
    Convert a list of FEB shots to FIBA coordinates.

    Parameters:
    -----------
    shots : List[Dict]
        List of shot dictionaries

    Returns:
    --------
    List[Dict]
        List of shots with FIBA coordinates added
    """
    return [convert_shot_to_fiba(shot) for shot in shots]


def convert_shots_for_zone_analysis(shots: List[Dict]) -> List[Dict]:
    """
    Convert FEB shot format to zone analysis format with FIBA coordinates.

    This function is specifically designed for zone analysis which expects
    a particular data structure.

    Parameters:
    -----------
    shots : List[Dict]
        List of shots in FEB format with keys: x, y, m, team, player, quarter, t

    Returns:
    --------
    List[Dict]
        List of shots in zone analysis format with FIBA coordinates
    """
    processed_shots = []

    for shot in shots:
        # Get FEB coordinates
        x_feb = float(shot.get('x', 0))
        y_feb = float(shot.get('y', 0))
        team = int(shot.get('team', 0))

        # Convert to FIBA coordinates
        fiba_x, fiba_y = convert_feb_to_fiba(x_feb, y_feb, team)

        # Create processed shot in zone analysis format
        processed_shot = {
            'x': fiba_x,
            'y': fiba_y,
            'made': int(shot.get('m', 0)) == 1,
            'team': team,
            'player': shot.get('player', ''),
            'quarter': int(shot.get('quarter', 0)),
            'time': shot.get('t', ''),
            'original_x': x_feb,
            'original_y': y_feb
        }
        processed_shots.append(processed_shot)

    return processed_shots
