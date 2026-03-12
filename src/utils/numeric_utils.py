"""Numeric utility functions for safe type conversions.

Canonical implementation shared across all project layers (UI, database, services).
"""


def safe_int(value, default: int = 0) -> int:
    """
    Safely convert a value to int.

    Args:
        value: Value to convert (can be int, float, str, or None)
        default: Default value to return if conversion fails

    Returns:
        Integer value or default if conversion fails

    Examples:
        >>> safe_int("123")
        123
        >>> safe_int(None)
        0
        >>> safe_int("abc", -1)
        -1
        >>> safe_int(45.7)
        45
    """
    try:
        return int(value) if value else default
    except (ValueError, TypeError):
        return default


def safe_float(value, default: float = 0.0) -> float:
    """
    Safely convert a value to float.

    Args:
        value: Value to convert (can be int, float, str, or None)
        default: Default value to return if conversion fails

    Returns:
        Float value or default if conversion fails

    Examples:
        >>> safe_float("123.45")
        123.45
        >>> safe_float(None)
        0.0
        >>> safe_float("abc", -1.0)
        -1.0
        >>> safe_float(45)
        45.0
    """
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default
