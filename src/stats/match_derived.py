"""The exact figures of one game (``DERIVED``, #372) applied to the box-score totals of its two teams (#379).

``with_derived`` gives copies of the totals whose rebounds (``ro`` / ``rd``) and turnovers (``to``) are the validated ones (the play-by-play
ones, team rebounds and turnovers included) and the exact possessions of each team; a game without ``DERIVED`` (older data, FBCYL, no
play-by-play) is returned as it is with no possessions, so the caller keeps its estimate. The stored document is never modified.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

_OVERRIDES = (("ro", "orb"), ("rd", "drb"), ("to", "tov"))


def _derived_team(game: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
    teams = (game.get("DERIVED") or {}).get("TEAM") or []
    box = (game.get("BOXSCORE") or {}).get("TEAM") or []
    if len(teams) != 2 or index >= len(box):
        return None
    mine = teams[index]
    return mine if str(mine.get("id")) == str(box[index].get("id")) else None


def _apply(total: Dict[str, Any], derived: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(total)
    for box_key, derived_key in _OVERRIDES:
        if derived.get(derived_key) is not None:
            out[box_key] = derived[derived_key]
    return out


def with_derived(team_total: Dict[str, Any], opp_total: Dict[str, Any], game: Dict[str, Any],
                 team_index: int) -> Tuple[Dict[str, Any], Dict[str, Any], Optional[float], Optional[float]]:
    """``(team_total, opp_total, team_possessions, opp_possessions)`` with the game's exact figures when it has them."""
    mine, theirs = _derived_team(game, team_index), _derived_team(game, 1 - team_index)
    if mine is None or theirs is None:
        return team_total, opp_total, None, None
    return _apply(team_total, mine), _apply(opp_total, theirs), mine.get("possessions"), theirs.get("possessions")
