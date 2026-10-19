"""Derived per-game fields stored in the match document (#372, #352, #353).

The season pipelines only read aggregated box-score fields, so the exact possessions and the validated rebounds and
turnovers of ``team_game_possessions`` are computed once, when the game is ingested, and stored in ``DERIVED.TEAM``
(same order as ``BOXSCORE.TEAM``). The pipelines read them with a box-score fallback for games that do not have them.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .game_events import game_events
from .game_possessions import analyse_game
from .period_stats import team_periods
from .points_by_origin import paint_points, starters, team_points_by_origin

DERIVED_VERSION = 3
_FIELDS = ("pts", "possessions", "possessions_source", "quality_level",
           "orb", "orb_source", "drb", "drb_source", "tov", "tov_source")


def derive_game_fields(game_doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """``{"v": n, "TEAM": [...]}`` for a FEB game with play-by-play, ``None`` when it cannot be read (FBCYL included)."""
    analysis = analyse_game(game_doc)
    if analysis is None:
        return None
    shots = (game_doc.get("SHOTCHART") or {}).get("SHOTS")
    technical = analysis.quality.technical_by_player
    ids = [str(t.get("id")) for t in game_doc["BOXSCORE"]["TEAM"]]
    events = sorted(game_events(game_doc, False), key=lambda e: (e.elapsed, e.num))
    periods = team_periods(events, analysis.possessions, ids)
    teams = []
    for index, team in enumerate(game_doc["BOXSCORE"]["TEAM"]):
        tid = str(team.get("id"))
        paint = paint_points(shots, index) if shots else None
        figures = team_points_by_origin(analysis.possessions, tid, starters(team), technical.get(tid, {}), paint)
        teams.append({"id": tid, **{key: analysis.teams[tid][key] for key in _FIELDS}, **figures, "periods": periods[tid]})
    return {"v": DERIVED_VERSION, "TEAM": teams}
