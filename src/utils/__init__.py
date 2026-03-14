"""Shared utility functions for the BasketLab project.

This package supersedes the top-level ``src/utils.py`` module (which is now
shadowed by this package directory).  Legacy functions previously defined in
``src/utils.py`` are re-exported from here so that existing imports such as
``from utils import normalize_year`` continue to work unchanged.
"""

import re


# ---------------------------------------------------------------------------
# Legacy helpers (previously in src/utils.py)
# ---------------------------------------------------------------------------

def normalize_year(year: str) -> str:
    """Normalize year input to a 4-digit year string (e.g. '2024/25' -> '2024')."""
    y = str(year).strip()
    if "/" in y:
        try:
            start = int(y.split("/")[0])
            return str(start)
        except Exception:
            pass
    if len(y) == 2 and y.isdigit():
        return "20" + y
    if len(y) == 4 and y.isdigit():
        return y
    m = re.search(r"(\d{4}|\d{2})", y)
    if m:
        val = m.group(1)
        if len(val) == 2:
            return "20" + val
        return val
    return y


def get_form_field_name(id_str: str) -> str:
    """Get the form field name by replacing _ with : after _ctl0."""
    return '_ctl0:' + id_str[6:].replace("_", ":")


def get_event_target(id_str: str) -> str:
    """Get the event target for postback by replacing _ with $ after _ctl0."""
    return '_ctl0$' + id_str[6:].replace("_", "$")
