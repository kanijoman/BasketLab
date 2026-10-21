"""Read stored games from MongoDB (through the repository) and build a package."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Iterator, Optional, Sequence

from src.live_core.package import PreparationPackage
from src.utils.collection_utils import is_fbcyl

from .game_sources import games_of_sources, source_collections
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
    "DERIVED": 1,      # exact possessions and points by origin, stored per game (scouting reads them: no box score totals here)
}

_WITH_PBP = {"PLAYBYPLAY.LINES": {"$exists": True, "$ne": None}}


def _counted(games: Iterable[Dict[str, Any]], total: int,
             progress: Optional[Callable[[int, int], None]]) -> Iterator[Dict[str, Any]]:
    """Yield the games lazily (one at a time in memory), reporting (done, total) after each."""
    for done, game in enumerate(games, 1):
        yield game
        if progress:
            progress(done, total)


def season_of(mongo_collection: Any, collection: str) -> str:
    """Season label: the scraper's ``_season`` field of the first game, else the collection name."""
    first = mongo_collection.find_one({"_season": {"$exists": True}}, {"_season": 1})
    return str(first["_season"]) if first and first.get("_season") else collection


def build_package_from_db(
    handler: Any,
    collection: str,
    team_id: str,
    rival_id: str,
    season: Optional[str] = None,
    competition_meta: Optional[Dict[str, Any]] = None,
    progress: Optional[Callable[[int, int], None]] = None,
    roster_source: Optional[Callable[[Sequence[str]], Optional[Dict[str, Dict[str, Any]]]]] = None,
    rule_config: Optional[Dict[str, Any]] = None,
) -> PreparationPackage:
    """``handler`` is a MongoDBHandler. FEB only for now (FBCYL has a different feed).

    ``progress(done, total)`` is called after each replayed game (the replay is CPU heavy). ``roster_source(team ids)``
    (``roster_fetcher.fetch_rosters`` in production; no request is made without it) gives the roster of both teams
    for ``tables.roster``; if it fails or answers nothing the package is built without roster (issue #271).
    """
    if is_fbcyl(collection):
        raise NotImplementedError("Live packages are FEB-only for now (FBCYL has a different feed).")
    mongo_collection = handler.repository.connection.get_collection(collection)
    total = mongo_collection.count_documents(_WITH_PBP)
    sources = source_collections(handler, collection, [team_id, rival_id])    # the own collection + the other games of both teams (#456)
    games = _counted(games_of_sources(handler, sources, [team_id, rival_id], _WITH_PBP, GAME_PROJECTION), total, progress)
    return build_package(games, collection, season or season_of(mongo_collection, collection),
                         team_id, rival_id, competition_meta, roster=_roster(roster_source, team_id, rival_id), rule_config=rule_config)


def _roster(source: Optional[Callable[..., Any]], team_id: str, rival_id: str) -> Optional[Dict[str, Dict[str, Any]]]:
    if source is None:
        return None
    try:
        return source([team_id, rival_id]) or None
    except Exception:  # noqa: BLE001 - FEB's website must never stop a package
        return None
