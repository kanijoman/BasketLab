"""Mongo expressions for possessions, rebounds and turnovers per team and match (#372).

The exact figures are stored in ``DERIVED.TEAM`` (same order as ``BOXSCORE.TEAM``, see ``src.pbp.game_derived``); a game
without them falls back to the box score, with the same free-throw cost as ``estimate_possessions``.
"""
from typing import Dict

from src.live_core.four_factors import FT_POSSESSION_COST

# Per team index, the box-score field of the validated figure that DERIVED may replace.
DERIVED_OR_BOX = {"off_reb": ("orb", "ro"), "def_reb": ("drb", "rd"), "turnovers": ("tov", "to")}


def derived_or_box(derived_field: str, box_field: str, index: int) -> Dict:
    """The stored figure of team ``index`` or, if the game has none, its box-score total (before the unwind)."""
    return {"$ifNull": [
        {"$arrayElemAt": [f"$DERIVED.TEAM.{derived_field}", index]},
        {"$toInt": {"$arrayElemAt": [f"$BOXSCORE.TEAM.TOTAL.{box_field}", index]}},
    ]}


def game_minutes() -> Dict:
    """40 minutes plus 5 per overtime period, from the quarters of the header."""
    return {"$add": [40, {"$multiply": [{"$subtract": [{"$size": "$HEADER.QUARTERS.QUARTER"}, 4]}, 5]}]}


def possessions_per_40(index: int, fga: Dict, fta: Dict, orb: Dict, tov: Dict) -> Dict:
    """Possessions of team ``index`` scaled to 40 minutes: the stored exact count, else the box-score estimate.

    ``orb`` and ``tov`` are the (already validated) expressions of that team; only used by the fallback.
    """
    estimate = {"$add": [fga, {"$multiply": [FT_POSSESSION_COST, fta]}, tov, {"$multiply": [-1, orb]}]}
    raw = {"$ifNull": [{"$arrayElemAt": ["$DERIVED.TEAM.possessions", index]}, estimate]}
    return {"$multiply": [raw, {"$divide": [40, game_minutes()]}]}


# Who a ``DERIVED.TEAM`` entry is and how it is called (#432). FEB: the team id and the header name. FBCYL: the ``id`` is the ``teamIdIntern`` of
# the moves, which changes in every game, so a season is grouped by the stable ``ext_id`` (``teamIdExtern``) and the name is in ``stats.teams``.
TEAM_NAMES = {"$ifNull": ["$HEADER.TEAM.name", "$stats.teams.name"]}


def team_key(entry: str) -> Dict:
    """The stable id of the ``DERIVED.TEAM`` entry that the expression ``entry`` (e.g. ``"$all"``) points to."""
    return {"$ifNull": [f"{entry}.ext_id", f"{entry}.id"]}


# A game whose possession figures can be trusted (``DERIVED.TEAM[].reliable``, #390): a game is left out of the figures that depend on the
# possessions when more than 10 % of its points have an unknown origin or its possession count is 10 % off the estimate.
RELIABLE_GAME = {"$eq": ["$all.reliable", True]}

# A game that is used but whose feed has alternation breaks (``quality_level`` is not ``ok``): how much a team's figures lean on inferred or
# repaired data (#392, stored, not shown). Needs the ``used`` flag the pipelines add.
DOUBTFUL_USED = {"$and": ["$used", {"$ne": ["$all.quality_level", "ok"]}]}
