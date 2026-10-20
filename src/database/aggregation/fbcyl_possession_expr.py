"""Possessions of an FBCYL team and game for the season pipeline (#432): the exact count stored in ``DERIVED`` or, without it, the box estimate.

``DERIVED.TEAM`` has the teams in the order of ``stats.teams`` (``src.pbp.game_derived``), so the index of the unwound team picks its entry.
A game that is not reliable (#390) already stores the estimate there (``possessions_source``), as in FEB.
"""
from typing import Any, Dict

from src.live_core.four_factors import FT_POSSESSION_COST


def box_estimate(team: str) -> Dict[str, Any]:
    """FGA - ORB + TOV + 0.44 * FTA of the team box ``team`` (an expression such as ``"$teams"``)."""
    data = f"{team}.data"
    return {"$add": [f"{data}.shotsOfTwoAttempted", f"{data}.shotsOfThreeAttempted", {"$multiply": [FT_POSSESSION_COST, f"{data}.shotsOfOneAttempted"]},
                     f"{data}.lost", {"$multiply": [-1, f"{data}.offensiveRebound"]}]}


def team_possessions(index: Any, team: str) -> Dict[str, Any]:
    """The stored possessions of the team at ``index`` of the game, or the estimate of its box ``team`` when the game has no ``DERIVED``."""
    return {"$ifNull": [{"$arrayElemAt": ["$DERIVED.TEAM.possessions", index]}, box_estimate(team)]}
