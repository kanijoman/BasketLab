"""Derived per-game fields stored in the match document (#372, #352, #353, #354, #355).

The season pipelines only read aggregated box-score fields, so the exact possessions and the validated rebounds and
turnovers of ``team_game_possessions`` are computed once, when the game is ingested, and stored in ``DERIVED.TEAM``
(same order as ``BOXSCORE.TEAM``). The pipelines read them with a box-score fallback for games that do not have them.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .game_events import game_events
from .game_possessions import analyse_game, game_teams
from .period_stats import team_periods
from .situation_stats import situation_figures
from .timeout_effects import timeout_effects
from .points_by_origin import fbcyl_starters, paint_points, starters, team_points_by_origin

DERIVED_VERSION = 6
_FIELDS = ("pts", "possessions", "possessions_source", "quality_level", "reliable", "unknown_pts_pct",
           "orb", "orb_source", "drb", "drb_source", "tov", "tov_source")


def derive_game_fields(game_doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """``{"v": n, "TEAM": [...]}`` for a FEB or FBCYL game with play-by-play, ``None`` when it cannot be read.

    FBCYL (#373): the team ``id`` is the ``teamIdIntern`` of the moves and ``ext_id`` the stable ``teamIdExtern``; there is no shot chart
    (``pts_paint`` is None) and no starters flag, so the bench is whoever did not start by the moves (``fbcyl_starters``).
    """
    analysis = analyse_game(game_doc)
    if analysis is None:
        return None
    is_fbcyl, ids, _totals = game_teams(game_doc)
    shots = (game_doc.get("SHOTCHART") or {}).get("SHOTS")
    technical = analysis.quality.technical_by_player
    events = sorted(game_events(game_doc, is_fbcyl), key=lambda e: (e.elapsed, e.num))
    periods = team_periods(events, analysis.possessions, ids)
    situations = situation_figures(events, analysis.possessions, ids)
    timeouts = timeout_effects(analysis.possessions, ids)
    box_teams = game_doc["stats"]["teams"] if is_fbcyl else game_doc["BOXSCORE"]["TEAM"]
    started = fbcyl_starters(events) if is_fbcyl else None
    teams = []
    for index, (team, tid) in enumerate(zip(box_teams, ids)):
        paint = paint_points(shots, index) if shots and not is_fbcyl else None
        starting = started.get(tid, set()) if is_fbcyl else starters(team)
        figures = team_points_by_origin(analysis.possessions, tid, starting, technical.get(tid, {}), paint)
        extra = {"ext_id": str(team.get("teamIdExtern"))} if is_fbcyl else {}
        teams.append({"id": tid, **extra, **{key: analysis.teams[tid][key] for key in _FIELDS}, **figures, "periods": periods[tid], **situations[tid], "timeouts": timeouts[tid]})
    return {"v": DERIVED_VERSION, "TEAM": teams}
