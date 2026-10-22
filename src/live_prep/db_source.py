"""Read stored games from MongoDB (through the repository) and build a package."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Iterator, Optional, Sequence

from src.live_core.package import PreparationPackage
from .game_sources import FEB, FEB_PROJECTION, feed_of, games_of_sources, source_collections
from .package_builder import build_package

# What the builder replays (see game_sources): FEB documents, and FBCYL games adapted to them.
GAME_PROJECTION: Dict[str, int] = FEB_PROJECTION
_WITH_PBP = FEB.with_pbp


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


def catalog_level_of(handler: Any) -> Callable[[str], Optional[int]]:
    """The division (catalog ``level``) of a collection, read once per collection; ``None`` for a cup, an unknown competition or any failure (issue #464)."""
    cache: Dict[str, Optional[int]] = {}

    def level_of(collection: str) -> Optional[int]:
        if collection not in cache:
            try:
                from .competition_info import competition_infos
                from .publisher import load_config

                cache[collection] = competition_infos(handler, [collection], load_config()["competitions"], [])[collection].get("level")
            except Exception:  # noqa: BLE001 - the division only refines the prior: a package never depends on it
                cache[collection] = None
        return cache[collection]

    return level_of


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
    level_of: Optional[Callable[[str], Optional[int]]] = None,
) -> PreparationPackage:
    """``handler`` is a MongoDBHandler. FEB and FBCYL (its games are adapted to the FEB document, ``fbcyl_adapter``; no shot chart, no roster of "formación").

    ``progress(done, total)`` is called after each replayed game (the replay is CPU heavy). ``roster_source(team ids)``
    (``roster_fetcher.fetch_rosters`` in production; no request is made without it) gives the roster of both teams
    for ``tables.roster``; if it fails or answers nothing the package is built without roster (issue #271).
    """
    mongo_collection = handler.repository.connection.get_collection(collection)
    total = mongo_collection.count_documents(feed_of(collection).with_pbp)
    sources = source_collections(handler, collection, [team_id, rival_id])    # the own collection + the other games of both teams (#456)
    games = _counted(games_of_sources(handler, sources, [team_id, rival_id], level_of or catalog_level_of(handler)), total, progress)
    return build_package(games, collection, season or season_of(mongo_collection, collection),
                         team_id, rival_id, competition_meta, roster=_roster(roster_source, team_id, rival_id), rule_config=rule_config)


def _roster(source: Optional[Callable[..., Any]], team_id: str, rival_id: str) -> Optional[Dict[str, Dict[str, Any]]]:
    if source is None:
        return None
    try:
        return source([team_id, rival_id]) or None
    except Exception:  # noqa: BLE001 - FEB's website must never stop a package
        return None
