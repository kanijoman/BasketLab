"""Shared PBP time helper used by PlayByPlayAnalyzer (IN/OUT, Combinaciones, Rotaciones depend on it).

The event classification and the possession logic live in ``src.live_core`` (``events``, ``events_fbcyl``,
``possessions``); this module only keeps the timestamp.
"""
from __future__ import annotations

from typing import Dict

from src.live_core.clock import FEB_SCHEME, Scheme, period_length, period_start


def _elapsed_from_remaining(period: int, remaining: int, scheme: Scheme = FEB_SCHEME) -> int:
    """Game seconds elapsed for a period number and the time remaining in it (OT periods last 5 minutes; ``scheme``: the regulation periods)."""
    return period_start(period, scheme) + max(0, period_length(period, scheme) - remaining)


def get_timestamp(move: Dict, is_fbcyl: bool, scheme: Scheme = FEB_SCHEME) -> int:
    """Seconds since the start of the game for a move (both feeds count the clock down, so it is converted)."""
    if is_fbcyl:
        period = int(move.get("period") or 1)
        return _elapsed_from_remaining(period, int(move.get("min") or 0) * 60 + int(move.get("sec") or 0), scheme)
    try:
        q = int(move.get("quarter") or 1)
        parts = str(move.get("time") or "10:00").split(":")
        return _elapsed_from_remaining(q, int(parts[0]) * 60 + int(parts[1]), scheme)
    except (ValueError, TypeError, IndexError):
        return 0
