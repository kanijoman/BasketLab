"""Shared PBP time helper used by PlayByPlayAnalyzer (IN/OUT, Combinaciones, Rotaciones depend on it).

The event classification and the possession logic live in ``src.live_core`` (``events``, ``events_fbcyl``,
``possessions``); this module only keeps the timestamp.
"""
from __future__ import annotations

from typing import Dict


def get_timestamp(move: Dict, is_fbcyl: bool) -> int:
    """Seconds since the start of the game for a move (the FEB clock counts down, so it is converted).

    NOTE (#370): for FBCYL ``min``/``sec`` is also time REMAINING, but this reads it as elapsed; the possession
    tracker (``events_fbcyl``) reads it correctly. Fix here with its regression tests, then the consumers.
    """
    if is_fbcyl:
        period = int(move.get("period") or 1)
        elapsed = int(move.get("min") or 0) * 60 + int(move.get("sec") or 0)
        if period > 4:
            return 4 * 600 + (period - 5) * 300 + elapsed
        return (period - 1) * 600 + elapsed
    try:
        q = int(move.get("quarter") or 1)
        parts = str(move.get("time") or "10:00").split(":")
        m, s = int(parts[0]), int(parts[1])
        if q > 4:
            return 4 * 600 + (q - 5) * 300 + max(0, 300 - (m * 60 + s))
        return (q - 1) * 600 + max(0, 600 - (m * 60 + s))
    except (ValueError, TypeError, IndexError):
        return 0
