"""How many games of a collection carry the ``DERIVED`` the pbp tables need, and which do not (issue #630).

«Análisis pbp» sums the ``DERIVED`` of each game; a game without it (never computed, or of an older version) is left out of those tables while the other tabs, which
read the box score, count it: a team showed 3 games in one place and 4 in the rest, and nothing said why. ``run_backfill_derived.py`` (and now every refresh) fills them.
"""
from __future__ import annotations

from typing import Any, Dict, List

from src.services.pbp_extended_stats_service import ORIGIN_MIN_VERSION

_LISTED = 50      # the games named in the answer; the count is always the whole


def _team_names(game: Dict[str, Any]) -> List[str]:
    feb = [t.get("name") for t in (game.get("HEADER") or {}).get("TEAM") or []]
    fbcyl = [t.get("name") for t in (game.get("stats") or {}).get("teams") or []]
    return [n for n in feb or fbcyl if n]


class DerivedCoverageService:
    def __init__(self, db_handler: Any) -> None:
        self._db = db_handler

    def get(self, collection_name: str) -> Dict[str, Any]:
        collection = self._db.repository.connection.get_collection(collection_name)
        missing = {"$or": [{"DERIVED.v": {"$exists": False}}, {"DERIVED.v": {"$lt": ORIGIN_MIN_VERSION}}]}
        pending = collection.count_documents(missing)
        games = collection.find(missing, {"HEADER.TEAM.name": 1, "stats.teams.name": 1}).sort("_id", 1).limit(_LISTED) if pending else []
        return {"collection": collection_name, "min_version": ORIGIN_MIN_VERSION, "total": collection.count_documents({}), "pending": pending,
                "pending_games": [{"code": str(g["_id"]), "teams": _team_names(g)} for g in games]}
