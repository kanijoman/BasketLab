"""Read stored games from MongoDB (through the repository) and build a package."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.live_core.package import PreparationPackage
from src.utils.collection_utils import is_fbcyl

from .package_builder import build_package

# What the builder replays: header, roster ids, play-by-play and the shot chart. The
# repository's own PBP cursor omits SHOTCHART, hence this dedicated projection.
GAME_PROJECTION: Dict[str, int] = {
    "HEADER": 1,
    "BOXSCORE.TEAM.id": 1,
    "BOXSCORE.TEAM.PLAYER.id": 1,
    "BOXSCORE.TEAM.PLAYER.name": 1,
    "PLAYBYPLAY.LINES": 1,
    "SHOTCHART.SHOTS": 1,
}


def build_package_from_db(
    handler: Any,
    collection: str,
    team_id: str,
    rival_id: str,
    season: str,
    competition_meta: Optional[Dict[str, Any]] = None,
) -> PreparationPackage:
    """``handler`` is a MongoDBHandler. FEB only for now (FBCYL has a different feed)."""
    if is_fbcyl(collection):
        raise NotImplementedError("Live packages are FEB-only for now (FBCYL has a different feed).")
    mongo_collection = handler.repository.connection.get_collection(collection)
    games = mongo_collection.find({"PLAYBYPLAY.LINES": {"$exists": True, "$ne": None}}, GAME_PROJECTION)
    return build_package(games, collection, season, team_id, rival_id, competition_meta)
