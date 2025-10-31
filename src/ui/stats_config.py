"""Configuration for statistics columns and data mapping."""

from typing import List, Dict, Tuple
from PyQt6.QtGui import QColor
import numpy as np


# Column definitions for basic stats table
BASIC_COLUMNS = [
    "Equipo", "Total Partidos", "Local", "Visitante",
    "Puntos a Favor", "Puntos en Contra", "Puntos/Partido", "Puntos Contra/Partido",
    "% T2", "% T3", "% TL", "Reb. Tot.", "Reb. Def.", "Reb. Of.",
    "Asistencias", "Robos", "Pérdidas", "Tapones"
]

# Column definitions for advanced stats table
ADVANCED_COLUMNS = [
    "Equipo", "Total Partidos",
    "Ritmo", "OER", "DER", "Net Rate",
    "eFG%", "TS%", "3Pr", "FTr", "AST/FG", "AST%", "TOV%",
    "ROB%", "TAP%", "ORB%", "RD%"
]

# Fields that should display with percentage symbol
PERCENTAGE_FIELDS = {
    'fg2_percentage', 'fg3_percentage', 'ft_percentage'
}

# Advanced stats fields that should display with percentage symbol
ADVANCED_PERCENTAGE_FIELDS = {
    'efg_percentage', 'turnover_rate', 'offensive_rebound_rate',
    'free_throw_rate', 'three_point_rate', 'true_shooting',
    'assist_fg_rate', 'assist_rate', 'steal_rate', 'block_rate', 'defensive_rebound_rate'
}

# Fields that should NOT display with percentage (possessions and ratings)
NON_PERCENTAGE_FIELDS = {
    'possessions_per_game', 'offensive_rating', 'defensive_rating', 'net_rating'
}


def get_basic_stats_config(team: Dict) -> List[Tuple[int, str, any]]:
    """
    Get configuration for basic stats columns.

    Args:
        team: Team statistics dictionary

    Returns:
        List of tuples (column_index, field_key, field_value)
    """
    return [
        (4, 'points_scored', team["points_scored"]),
        (5, 'points_received', team["points_received"]),
        (6, 'points_per_game', team['points_per_game']),
        (7, 'points_against_per_game', team['points_against_per_game']),
        (8, 'fg2_percentage', team['fg2_percentage']),
        (9, 'fg3_percentage', team['fg3_percentage']),
        (10, 'ft_percentage', team['ft_percentage']),
        (11, 'total_rebounds', team["total_rebounds"]),
        (12, 'rebounds_def', team["rebounds_def"]),
        (13, 'rebounds_off', team["rebounds_off"]),
        (14, 'assists', team["assists"]),
        (15, 'steals', team["steals"]),
        (16, 'turnovers', team["turnovers"]),
        (17, 'blocks', team["blocks"])
    ]


def get_advanced_stats_config(team: Dict) -> List[Tuple[int, str, any]]:
    """
    Get configuration for advanced stats columns.

    Args:
        team: Team statistics dictionary

    Returns:
        List of tuples (column_index, field_key, field_value)
    """
    return [
        (2, 'possessions_per_game', team['possessions_per_game']),
        (3, 'offensive_rating', team['offensive_rating']),
        (4, 'defensive_rating', team['defensive_rating']),
        (5, 'net_rating', team['net_rating']),
        (6, 'efg_percentage', team['efg_percentage']),
        (7, 'true_shooting', team['true_shooting']),
        (8, 'three_point_rate', team['three_point_rate']),
        (9, 'free_throw_rate', team['free_throw_rate']),
        (10, 'assist_fg_rate', team['assist_fg_rate']),
        (11, 'assist_rate', team['assist_rate']),
        (12, 'turnover_rate', team['turnover_rate']),
        (13, 'steal_rate', team['steal_rate']),
        (14, 'block_rate', team['block_rate']),
        (15, 'offensive_rebound_rate', team['offensive_rebound_rate']),
        (16, 'defensive_rebound_rate', team['defensive_rebound_rate'])
    ]


def get_basic_numeric_data(team_stats: List[Dict]) -> Dict[str, Tuple[List[float], bool]]:
    """
    Get numeric data for basic stats with reverse flags.

    Args:
        team_stats: List of team statistics

    Returns:
        Dictionary mapping field names to (values_list, reverse_flag) tuples.
        reverse_flag is True when lower values are better.
    """
    from .table_items import safe_float

    return {
        'points_scored': ([safe_float(team['points_scored']) for team in team_stats], False),
        'points_received': ([safe_float(team['points_received']) for team in team_stats], True),
        'points_per_game': ([safe_float(team['points_per_game']) for team in team_stats], False),
        'points_against_per_game': ([safe_float(team['points_against_per_game']) for team in team_stats], True),
        'fg2_percentage': ([safe_float(team['fg2_percentage']) for team in team_stats], False),
        'fg3_percentage': ([safe_float(team['fg3_percentage']) for team in team_stats], False),
        'ft_percentage': ([safe_float(team['ft_percentage']) for team in team_stats], False),
        'total_rebounds': ([safe_float(team['total_rebounds']) for team in team_stats], False),
        'rebounds_def': ([safe_float(team['rebounds_def']) for team in team_stats], False),
        'rebounds_off': ([safe_float(team['rebounds_off']) for team in team_stats], False),
        'assists': ([safe_float(team['assists']) for team in team_stats], False),
        'steals': ([safe_float(team['steals']) for team in team_stats], False),
        'turnovers': ([safe_float(team['turnovers']) for team in team_stats], True),
        'blocks': ([safe_float(team['blocks']) for team in team_stats], False)
    }


def get_advanced_numeric_data(team_stats: List[Dict]) -> Dict[str, Tuple[List[float], bool]]:
    """
    Get numeric data for advanced stats with reverse flags.

    Args:
        team_stats: List of team statistics

    Returns:
        Dictionary mapping field names to (values_list, reverse_flag) tuples.
        reverse_flag is True when lower values are better.
    """
    from .table_items import safe_float

    return {
        'possessions_per_game': ([safe_float(team['possessions_per_game']) for team in team_stats], False),
        'efg_percentage': ([safe_float(team['efg_percentage']) for team in team_stats], False),
        'turnover_rate': ([safe_float(team['turnover_rate']) for team in team_stats], True),
        'offensive_rebound_rate': ([safe_float(team['offensive_rebound_rate']) for team in team_stats], False),
        'free_throw_rate': ([safe_float(team['free_throw_rate']) for team in team_stats], False),
        'three_point_rate': ([safe_float(team['three_point_rate']) for team in team_stats], False),
        'true_shooting': ([safe_float(team['true_shooting']) for team in team_stats], False),
        'assist_fg_rate': ([safe_float(team['assist_fg_rate']) for team in team_stats], False),
        'assist_rate': ([safe_float(team['assist_rate']) for team in team_stats], False),
        'steal_rate': ([safe_float(team['steal_rate']) for team in team_stats], False),
        'block_rate': ([safe_float(team['block_rate']) for team in team_stats], False),
        'defensive_rebound_rate': ([safe_float(team['defensive_rebound_rate']) for team in team_stats], False),
        'offensive_rating': ([safe_float(team['offensive_rating']) for team in team_stats], False),
        'defensive_rating': ([safe_float(team['defensive_rating']) for team in team_stats], True),
        'net_rating': ([safe_float(team['net_rating']) for team in team_stats], False)
    }


def calculate_quartiles(values: List[float]) -> List[float]:
    """
    Calculate quartiles for a list of values.

    Args:
        values: List of numeric values

    Returns:
        List of [Q1, Q2, Q3] quartile values
    """
    return [np.percentile(values, q) for q in [25, 50, 75]]


def get_quartile_color(value: float, quartiles: List[float], reverse: bool = False) -> QColor:
    """
    Get color based on quartile value.

    Args:
        value: The value to color
        quartiles: List of [Q1, Q2, Q3] quartile values
        reverse: If True, lower values get better colors

    Returns:
        QColor object for the cell background
    """
    if reverse:
        if value <= quartiles[0]:
            return QColor(144, 238, 144)  # Light green
        elif value <= quartiles[1]:
            return QColor(255, 255, 153)  # Light yellow
        elif value <= quartiles[2]:
            return QColor(255, 200, 87)   # Light orange
        else:
            return QColor(255, 153, 153)  # Light red
    else:
        if value >= quartiles[2]:
            return QColor(144, 238, 144)  # Light green
        elif value >= quartiles[1]:
            return QColor(255, 255, 153)  # Light yellow
        elif value >= quartiles[0]:
            return QColor(255, 200, 87)   # Light orange
        else:
            return QColor(255, 153, 153)  # Light red
