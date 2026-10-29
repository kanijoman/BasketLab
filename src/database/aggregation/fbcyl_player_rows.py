"""One document per (player, game) of an FBCYL collection: the rows of the local-first player tables (#644).

The contract of the device: it sums these rows by ``(player_uuid, team_id)``. What FBCYL's season pipeline does in Mongo with ``$substrCP``,
``$max`` and ``$reduce`` (the normalised name, the uuid completed from the player's other games, the plus-minus from ``inOutsList``) is done by
the exporter in Python, over the whole season (``export.fbcyl_player_rows``), so this pipeline only projects what is in the box score: the
players that count (``PLAYED_PLAYER_STAGE``, shared with the season pipeline), the venue, the result and the date of the game they played.
"""
from __future__ import annotations

from typing import Dict, List

from .fbcyl_pipeline import PLAYED_PLAYER_STAGE

_PLAYER = "$stats.teams.players"


def _stat(field: str) -> Dict:
    return {"$ifNull": [f"{_PLAYER}.data.{field}", 0]}


def build_fbcyl_season_player_rows_pipeline() -> List[Dict]:
    """The pipeline; ``uuid`` is the raw one (``None`` when FBCYL left it out) and ``in_out_diffs`` the ``pointDiff`` of ``inOutsList`` in order."""
    return [
        {"$match": {"stats.teams": {"$exists": True, "$ne": None}}},
        {"$addFields": {"all_teams": "$stats.teams"}},
        {"$unwind": {"path": "$stats.teams", "includeArrayIndex": "teamIndex"}},
        {"$addFields": {"opponent": {"$arrayElemAt": ["$all_teams", {"$cond": [{"$eq": ["$teamIndex", 0]}, 1, 0]}]}}},
        {"$unwind": {"path": _PLAYER, "preserveNullAndEmptyArrays": False}},
        PLAYED_PLAYER_STAGE,
        {"$project": {
            "_id": 0, "match_id": "$_id", "starttime": "$stats.time", "is_local": {"$eq": ["$teamIndex", 0]},
            "won": {"$gt": ["$stats.teams.data.score", "$opponent.data.score"]}, "tied": {"$eq": ["$stats.teams.data.score", "$opponent.data.score"]},
            "team_id": "$stats.teams.teamIdExtern", "team_name": "$stats.teams.name",
            "uuid": f"{_PLAYER}.uuid", "player_id": f"{_PLAYER}.actorId", "player_name": f"{_PLAYER}.name",
            "minutes": {"$ifNull": [f"{_PLAYER}.timePlayed", 0]}, "pts": _stat("score"), "val": _stat("valoration"),
            "p1a": _stat("shotsOfOneAttempted"), "p1m": _stat("shotsOfOneSuccessful"), "p2a": _stat("shotsOfTwoAttempted"),
            "p2m": _stat("shotsOfTwoSuccessful"), "p3a": _stat("shotsOfThreeAttempted"), "p3m": _stat("shotsOfThreeSuccessful"),
            "ro": _stat("offensiveRebound"), "rd": _stat("defensiveRebound"),
            "rt": {"$add": [_stat("offensiveRebound"), _stat("defensiveRebound")]},
            "assist": _stat("assists"), "to": _stat("lost"), "bs": _stat("block"), "st": _stat("steals"), "pf": _stat("faults"),
            "rf": _stat("faultReceived"),
            "in_out_diffs": {"$map": {"input": {"$ifNull": [f"{_PLAYER}.inOutsList", []]}, "as": "e", "in": "$$e.pointDiff"}},
        }},
    ]
