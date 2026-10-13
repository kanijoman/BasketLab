"""FIBA timeout budget and "since the last timeout" helpers.

FIBA: 2 timeouts in the first half, 3 in the second (at most 2 of them in the last 2:00 of the 4th period) and 1 per
overtime; unused timeouts are not carried over. The snapshot keeps only the game-seconds of each timeout
(``teams[id]["timeouts"]``), so the period of each is derived from the clock: a timeout at the very second a period
opens counts for the new period. Timeouts after the snapshot's own clock are ignored.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .clock import REGULATION_PERIODS, period_and_remaining, period_length, period_start

FIRST_HALF = 2
SECOND_HALF = 3
OVERTIME = 1
LAST_WINDOW_S = 120       # the last 2:00 of the 4th period...
LAST_WINDOW_MAX = 2       # ...allow at most this many timeouts


def _times(snap: Dict[str, Any], team_id: Optional[str]) -> List[int]:
    """The team's timeouts that already happened at the snapshot's clock, in game order."""
    team = (snap.get("teams") or {}).get(team_id) if team_id is not None else None
    return sorted(t for t in (team or {}).get("timeouts", []) if t <= snap["elapsed"])


def _period(elapsed: int) -> int:
    return period_and_remaining(elapsed)[0]


def timeouts_left(snap: Dict[str, Any], team_id: Optional[str]) -> int:
    """Timeouts ``team_id`` can still call now (never negative; a team the snapshot does not know has them all)."""
    times, period = _times(snap, team_id), snap["period"]
    if period > REGULATION_PERIODS:
        return max(0, OVERTIME - sum(1 for t in times if _period(t) == period))
    if period <= 2:
        return max(0, FIRST_HALF - sum(1 for t in times if _period(t) <= 2))
    left = SECOND_HALF - sum(1 for t in times if _period(t) >= 3 and _period(t) <= REGULATION_PERIODS)
    if period == REGULATION_PERIODS and snap["remaining"] <= LAST_WINDOW_S:
        closing_from = period_start(REGULATION_PERIODS) + period_length(REGULATION_PERIODS) - LAST_WINDOW_S
        left = min(left, LAST_WINDOW_MAX - sum(1 for t in times if t >= closing_from))
    return max(0, left)


def last_timeout(snap: Dict[str, Any], team_id: Optional[str]) -> Optional[int]:
    """Game-second of the team's latest timeout, or None."""
    times = _times(snap, team_id)
    return times[-1] if times else None


def timeout_within(snap: Dict[str, Any], team_id: Optional[str], seconds: int) -> bool:
    """True when the team called a timeout at most ``seconds`` game-seconds ago ("just called")."""
    last = last_timeout(snap, team_id)
    return last is not None and snap["elapsed"] - last <= seconds


def episode(snap: Dict[str, Any], team_id: Optional[str]) -> str:
    """Identity of the stretch since the team's last timeout of this period (or the period's start): ``period:second``.

    A new timeout starts a new episode, so a key built with it lets an alert about the same problem fire again after
    the coach has reacted, and not before.
    """
    period = snap["period"]
    start = period_start(period)
    last = last_timeout(snap, team_id)
    if last is not None and _period(last) == period:
        start = max(start, last)
    return f"{period}:{start}"
