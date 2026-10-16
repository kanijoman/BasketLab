"""Derived per-game fields stored in the match document (#372).

The season pipelines only read aggregated box-score fields, so the exact possessions and the validated rebounds and
turnovers of ``team_game_possessions`` are computed once, when the game is ingested, and stored in ``DERIVED.TEAM``
(same order as ``BOXSCORE.TEAM``). The pipelines read them with a box-score fallback for games that do not have them.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .game_possessions import team_game_possessions

DERIVED_VERSION = 1
_FIELDS = ("possessions", "possessions_source", "quality_level",
           "orb", "orb_source", "drb", "drb_source", "tov", "tov_source")


def derive_game_fields(game_doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """``{"v": n, "TEAM": [...]}`` for a FEB game with play-by-play, ``None`` when it cannot be read (FBCYL included)."""
    per_team = team_game_possessions(game_doc)
    if per_team is None:
        return None
    teams = []
    for team in game_doc["BOXSCORE"]["TEAM"]:
        tid = str(team.get("id"))
        teams.append({"id": tid, **{key: per_team[tid][key] for key in _FIELDS}})
    return {"v": DERIVED_VERSION, "TEAM": teams}
