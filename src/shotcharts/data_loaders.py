"""
Data loading utilities for FEB game data.

This module provides standardized functions for loading and processing
basketball shot data from FEB JSON files and other sources.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from .coordinate_utils import convert_shot_to_fiba


def load_feb_json(json_path: str, encoding: str = 'utf-8') -> Dict:
    """
    Load FEB game JSON file with automatic encoding fallback.

    Parameters:
    -----------
    json_path : str
        Path to FEB game JSON file
    encoding : str
        Initial encoding to try (default: 'utf-8')

    Returns:
    --------
    Dict
        Parsed JSON data

    Raises:
    -------
    FileNotFoundError
        If the JSON file doesn't exist
    json.JSONDecodeError
        If the file is not valid JSON
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    # Try primary encoding
    try:
        with open(json_path, 'r', encoding=encoding) as f:
            return json.load(f)
    except UnicodeDecodeError:
        # Fallback to latin1 encoding
        with open(json_path, 'r', encoding='latin1') as f:
            return json.load(f)


def extract_shots_from_feb_json(data: Dict) -> List[Dict]:
    """
    Extract shot data from FEB game JSON structure.

    FEB JSON structure: SHOTCHART -> SHOTS (array)

    Parameters:
    -----------
    data : Dict
        Parsed FEB game JSON data

    Returns:
    --------
    List[Dict]
        List of raw shot dictionaries from FEB format
    """
    shotchart = data.get('SHOTCHART', {})
    return shotchart.get('SHOTS', [])


def load_feb_game_shots(json_path: str,
                        convert_coordinates: bool = True,
                        include_metadata: bool = True) -> List[Dict]:
    """
    Load and process FEB game shots from JSON file.

    This is the main high-level function for loading FEB game data.
    Handles file loading, data extraction, and optional coordinate conversion.

    Parameters:
    -----------
    json_path : str
        Path to FEB game JSON file
    convert_coordinates : bool
        If True, converts FEB coordinates to FIBA meters (default: True)
    include_metadata : bool
        If True, includes player, quarter, time info (default: True)

    Returns:
    --------
    List[Dict]
        List of processed shot dictionaries with structure:
        {
            'x': float,              # FIBA x coordinate (meters) or FEB if not converted
            'y': float,              # FIBA y coordinate (meters) or FEB if not converted
            'made': bool,            # True if shot was made
            'team': int,             # Team ID
            'player': str,           # Player name (if include_metadata)
            'quarter': int,          # Quarter number (if include_metadata)
            'time': str,             # Time stamp (if include_metadata)
            'original_x': float,     # Original FEB x (if converted)
            'original_y': float      # Original FEB y (if converted)
        }

    Raises:
    -------
    FileNotFoundError
        If the JSON file doesn't exist
    ValueError
        If the JSON structure is invalid
    """
    # Load JSON data
    data = load_feb_json(json_path)

    # Extract shots from structure
    raw_shots = extract_shots_from_feb_json(data)

    if not raw_shots:
        raise ValueError(f"No shots found in {json_path}")

    # Process each shot
    processed_shots = []
    for shot in raw_shots:
        try:
            x_feb = float(shot['x'])
            y_feb = float(shot['y'])
            team = int(shot['team'])
            made = int(shot['m']) == 1  # Convert to boolean

            processed_shot = {
                'made': made,
                'team': team
            }

            # Convert coordinates if requested
            if convert_coordinates:
                fiba_x, fiba_y = convert_shot_to_fiba(x_feb, y_feb, team)
                processed_shot['x'] = fiba_x
                processed_shot['y'] = fiba_y
                processed_shot['original_x'] = x_feb
                processed_shot['original_y'] = y_feb
            else:
                processed_shot['x'] = x_feb
                processed_shot['y'] = y_feb

            # Add metadata if requested
            if include_metadata:
                processed_shot['player'] = shot.get('player', '')
                processed_shot['quarter'] = int(shot.get('quarter', 0))
                processed_shot['time'] = shot.get('t', '')

            processed_shots.append(processed_shot)

        except (KeyError, ValueError, TypeError) as e:
            # Skip malformed shots but log the issue
            print(f"Warning: Skipping malformed shot: {e}")
            continue

    return processed_shots


def load_feb_game_data(json_path: str) -> List[Dict]:
    """
    Load FEB game data with full metadata (backwards compatible).

    This function provides backwards compatibility with the old
    zone_analysis.load_feb_game_data() method.

    Parameters:
    -----------
    json_path : str
        Path to FEB game JSON file

    Returns:
    --------
    List[Dict]
        List of shot dictionaries with FIBA coordinates and full metadata
    """
    return load_feb_game_shots(
        json_path,
        convert_coordinates=True,
        include_metadata=True
    )


def extract_game_metadata(data: Dict) -> Dict:
    """
    Extract game metadata from FEB JSON structure.

    Parameters:
    -----------
    data : Dict
        Parsed FEB game JSON data

    Returns:
    --------
    Dict
        Game metadata with keys like 'home_team', 'away_team', 'date', etc.
    """
    metadata = {}

    # Extract from SHOTCHART or root level
    shotchart = data.get('SHOTCHART', {})

    # Try to extract common fields
    metadata['home_team'] = shotchart.get('home', data.get('home', ''))
    metadata['away_team'] = shotchart.get('away', data.get('away', ''))
    metadata['date'] = shotchart.get('date', data.get('date', ''))
    metadata['competition'] = shotchart.get('competition', data.get('competition', ''))

    return metadata


def validate_feb_json_structure(data: Dict) -> bool:
    """
    Validate FEB JSON structure has required fields.

    Parameters:
    -----------
    data : Dict
        Parsed FEB game JSON data

    Returns:
    --------
    bool
        True if structure is valid, False otherwise
    """
    if not isinstance(data, dict):
        return False

    if 'SHOTCHART' not in data:
        return False

    shotchart = data['SHOTCHART']
    if not isinstance(shotchart, dict):
        return False

    if 'SHOTS' not in shotchart:
        return False

    shots = shotchart['SHOTS']
    if not isinstance(shots, list):
        return False

    # Validate at least one shot has required fields
    if shots:
        required_fields = ['x', 'y', 'team', 'm']
        first_shot = shots[0]
        if not all(field in first_shot for field in required_fields):
            return False

    return True
