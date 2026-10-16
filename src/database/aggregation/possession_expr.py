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
