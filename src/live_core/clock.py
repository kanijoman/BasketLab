"""Game clock helpers.

FEB reports the time REMAINING in the period as "mm:ss". Periods 1-4 last 10 minutes;
overtimes (period >= 5) last 5. "Elapsed" is seconds since tip-off.
"""

from __future__ import annotations

import re
from typing import Optional

REGULATION_PERIODS = 4
REGULATION_LENGTH = 600
OVERTIME_LENGTH = 300

_CLOCK_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def period_length(period: int) -> int:
    return REGULATION_LENGTH if period <= REGULATION_PERIODS else OVERTIME_LENGTH


def period_start(period: int) -> int:
    """Elapsed seconds at the start of ``period``."""
    if period <= REGULATION_PERIODS:
        return REGULATION_LENGTH * (period - 1)
    return REGULATION_LENGTH * REGULATION_PERIODS + OVERTIME_LENGTH * (period - REGULATION_PERIODS - 1)


def parse_clock(text: Optional[str]) -> Optional[int]:
    """"mm:ss" -> seconds, or None when it is not a clock (e.g. "FINAL")."""
    match = _CLOCK_RE.match((text or "").strip())
    return int(match.group(1)) * 60 + int(match.group(2)) if match else None


def elapsed_seconds(period: int, remaining: int) -> int:
    return period_start(period) + period_length(period) - remaining


def period_and_remaining(elapsed: int) -> "tuple[int, int]":
    """Inverse of :func:`elapsed_seconds`: (period, seconds remaining in it)."""
    period = 1
    while elapsed >= period_start(period) + period_length(period):
        period += 1
    return period, period_start(period) + period_length(period) - max(elapsed, 0)
