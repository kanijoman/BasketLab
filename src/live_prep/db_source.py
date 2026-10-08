"""Read stored games from MongoDB (through the repository) and build a package."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.live_core.package import PreparationPackage
from src.utils.collection_utils import is_fbcyl

from .package_builder import build_package


def build_package_from_db(
    handler: Any,
    collection: str,
    team_id: str,
    rival_id: str,
    season: str,
    competition_meta: Optional[Dict[str, Any]] = None,
) -> PreparationPackage:
    """``handler`` is a MongoDBHandler (uses its repository's lazy PBP cursor). FEB only for now."""
    if is_fbcyl(collection):
        raise NotImplementedError("Live packages are FEB-only for now (FBCYL has a different feed).")
    games = handler.repository.get_games_with_playbyplay(collection)
    return build_package(games, collection, season, team_id, rival_id, competition_meta)
