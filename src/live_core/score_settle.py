"""The play-by-play is behind the scoreboard (feedback 0.4.0, #564): the rules of recent actions wait.

FEB serves the header (the score the staff sees on the court) before the play-by-play lines. In that gap the log lacks the last baskets: a streak of misses «is
still there» although the make that broke it is already on the scoreboard, a run is longer than it is. It is the same pattern as ``lineup_settle``: a rule that
reads the last actions is held back while the log has fewer points than the header, and it speaks on the next poll if what it saw still holds.
A difference that does not go away (a correction of the table can leave the log with other points for the rest of the game) is not waited for: after
``log_lag_max_s`` game seconds with the same difference it becomes the normal state and only a NEW gap holds the rules again. Standard library only.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

# the rules whose message depends on the last actions of the log (windows of seconds or minutes, last N attempts)
RECENT_ACTION_RULES = frozenset({
    "rival_run", "turnover_streak", "cold_shooting", "rival_hot_shooting", "scoring_drought", "long_run", "game_flow_windows",
    "after_timeout_scoring", "timeout_review", "timeout_followup",
})


def _log_points(log: Any, team: str) -> int:
    return sum(e[3] for e in log if e[1] == team and e[2] == "pts")


def log_lags(snapshot: Dict[str, Any], own: str, rival: str, state: Dict[str, Any], max_wait_s: int) -> bool:
    """True while the header has points the log does not have yet. ``state`` is the memory of the engine between polls."""
    header, log, now = snapshot.get("score") or {}, snapshot.get("log", []), snapshot["elapsed"]
    if own not in header or rival not in header:
        return False
    permanent: Tuple[int, int] = state.get("permanent", (0, 0))
    behind = (max(0, int(header[own]) - _log_points(log, own)), max(0, int(header[rival]) - _log_points(log, rival)))
    gap = (max(0, behind[0] - permanent[0]), max(0, behind[1] - permanent[1]))
    if gap == (0, 0):
        state.pop("gap", None)
        return False
    if state.get("gap") != gap:
        state["gap"], state["since"] = gap, now
        return True
    if now - state["since"] >= max_wait_s:
        state["permanent"] = behind          # it has not gone away: it is the way this game's log is, not a delay
        state.pop("gap", None)
        return False
    return True
