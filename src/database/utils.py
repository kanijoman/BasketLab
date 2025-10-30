"""Utility functions for database operations."""

import re


def get_collection_name(competition: str, season: str, group: str) -> str:
    """
    Generate collection name in the format {competicion}_{temporada}_{Grupo}.

    Removes or replaces invalid MongoDB characters and whitespace:
    - Replaces spaces, tabs, newlines with underscores
    - Removes $ and other special MongoDB characters
    - Ensures name doesn't start with 'system.' or contain null character

    Args:
        competition: Competition name
        season: Season identifier
        group: Group identifier

    Returns:
        Safe collection name for MongoDB
    """
    # First, replace all whitespace characters with underscore
    safe_competition = re.sub(r'\s+', '_', competition.strip())
    safe_season = re.sub(r'\s+', '_', season.strip())
    safe_group = re.sub(r'\s+', '_', group.strip())

    # Replace invalid MongoDB characters and common problematic characters
    pattern = r'[\\/:*?"<>|.$\x00-\x1F\x7F]'
    safe_competition = re.sub(pattern, '_', safe_competition)
    safe_season = re.sub(pattern, '_', safe_season)
    safe_group = re.sub(pattern, '_', safe_group)

    # Collapse multiple underscores into one
    safe_competition = re.sub(r'_+', '_', safe_competition)
    safe_season = re.sub(r'_+', '_', safe_season)
    safe_group = re.sub(r'_+', '_', safe_group)

    # Remove leading/trailing underscores
    safe_competition = safe_competition.strip('_')
    safe_season = safe_season.strip('_')
    safe_group = safe_group.strip('_')

    collection_name = f"{safe_competition}_{safe_season}_{safe_group}"

    # Ensure the name doesn't start with 'system.'
    if collection_name.lower().startswith('system.'):
        collection_name = 'col_' + collection_name

    return collection_name


def safe_divide(numerator_expr: dict, denominator_expr: dict, default: float = 0) -> dict:
    """
    Create a safe division expression for MongoDB aggregation.

    Args:
        numerator_expr: MongoDB expression for numerator
        denominator_expr: MongoDB expression for denominator
        default: Default value if denominator is 0

    Returns:
        MongoDB conditional expression for safe division
    """
    return {
        "$cond": [
            {"$eq": [denominator_expr, 0]},
            default,
            {"$divide": [numerator_expr, denominator_expr]}
        ]
    }
