"""Utility functions for database operations."""

import re

_WHITESPACE_RE = re.compile(r'\s+')
_INVALID_CHARS_RE = re.compile(r'[\\/:*?"<>|.$\x00-\x1F\x7F]')
_MULTI_UNDERSCORE_RE = re.compile(r'_+')


def _sanitize_component(value: str) -> str:
    """Sanitize a single collection-name component.

    Steps applied in order:
    1. Strip surrounding whitespace and replace internal whitespace with ``_``.
    2. Remove MongoDB-invalid characters (replace with ``_``).
    3. Collapse runs of underscores into a single one.
    4. Strip leading/trailing underscores.
    """
    result = _WHITESPACE_RE.sub('_', value.strip())
    result = _INVALID_CHARS_RE.sub('_', result)
    result = _MULTI_UNDERSCORE_RE.sub('_', result)
    return result.strip('_')


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
    safe_parts = [_sanitize_component(p) for p in (competition, season, group)]
    collection_name = "_".join(safe_parts)

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
