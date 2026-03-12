"""Utility functions for MongoDB collection metadata.

Centralises collection-name inspection logic that was previously
scattered across 5+ call sites as:
    ``collection_name.startswith('FBCYL_')``
"""


def is_fbcyl(collection_name: str) -> bool:
    """Return True if the collection belongs to the FBCYL (Castilla y León) league.

    FBCYL collections always start with the prefix ``FBCYL_``, whereas
    FEB collections start with ``FEB_``.

    Args:
        collection_name: MongoDB collection name, e.g. ``"FBCYL_SE_2025_A"``.

    Returns:
        ``True`` for FBCYL collections, ``False`` for FEB or any other type.

    Examples:
        >>> is_fbcyl("FBCYL_SE_2025_A")
        True
        >>> is_fbcyl("FEB_LF2_2025_A")
        False
        >>> is_fbcyl("")
        False
    """
    return bool(collection_name) and collection_name.startswith("FBCYL_")
