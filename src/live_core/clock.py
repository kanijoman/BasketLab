"""Game clock helpers.

FEB reports the time REMAINING in the period as "mm:ss". Periods 1-4 last 10 minutes;
overtimes (period >= 5) last 5. "Elapsed" is seconds since tip-off.
"""

from __future__ import annotations

import re
from typing import NamedTuple, Optional

REGULATION_PERIODS = 4
REGULATION_LENGTH = 600
OVERTIME_LENGTH = 300
GAME_SECONDS = REGULATION_LENGTH * REGULATION_PERIODS      # a game of four quarters: the length every per-40 rate and fraction of the game is measured against

class Scheme(NamedTuple):
    """The regulation of a game: ``periods`` of ``minutes`` each; every overtime lasts ``OVERTIME_LENGTH`` (#1131: NCAA men play two halves of 20)."""

    periods: int
    minutes: int


FEB_SCHEME = Scheme(REGULATION_PERIODS, REGULATION_LENGTH // 60)

_CLOCK_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def period_length(period: int, scheme: Scheme = FEB_SCHEME) -> int:
    return scheme.minutes * 60 if period <= scheme.periods else OVERTIME_LENGTH


def regulation_seconds(scheme: Scheme = FEB_SCHEME) -> int:
    """The seconds of a game without overtimes."""
    return scheme.periods * scheme.minutes * 60


def game_length(last_period: int, scheme: Scheme = FEB_SCHEME) -> int:
    """The seconds of a game whose last period was ``last_period`` (its regulation plus each overtime played)."""
    return regulation_seconds(scheme) + max(0, last_period - scheme.periods) * OVERTIME_LENGTH


def game_seconds_left(period: int, remaining: int) -> int:
    """Seconds of play left in the game: what is left of ``period`` plus the regulation periods still to play."""
    later = sum(period_length(p) for p in range(period + 1, REGULATION_PERIODS + 1))
    return max(0, remaining) + later


def period_start(period: int, scheme: Scheme = FEB_SCHEME) -> int:
    """Elapsed seconds at the start of ``period``."""
    if period <= scheme.periods:
        return scheme.minutes * 60 * (period - 1)
    return regulation_seconds(scheme) + OVERTIME_LENGTH * (period - scheme.periods - 1)


def parse_clock(text: Optional[str]) -> Optional[int]:
    """"mm:ss" -> seconds, or None when it is not a clock (e.g. "FINAL")."""
    match = _CLOCK_RE.match((text or "").strip())
    return int(match.group(1)) * 60 + int(match.group(2)) if match else None


def elapsed_seconds(period: int, remaining: int, scheme: Scheme = FEB_SCHEME) -> int:
    return period_start(period, scheme) + period_length(period, scheme) - remaining


def period_and_remaining(elapsed: int) -> "tuple[int, int]":
    """Inverse of :func:`elapsed_seconds`: (period, seconds remaining in it)."""
    period = 1
    while elapsed >= period_start(period) + period_length(period):
        period += 1
    return period, period_start(period) + period_length(period) - max(elapsed, 0)


def clock_text(seconds: int) -> str:
    """``125`` -> ``2:05``: a clock or a length of time as the staff read it (minutes and two-digit seconds)."""
    return f"{seconds // 60}:{seconds % 60:02d}"
