"""Where the games of a package come from: the match's collection plus every other game of its two teams in the season (issue #456).

A knockout tie has 0-1 games per team in its own collection and a rival of another division has none, so the games of both teams in the other
competitions and phases of the season (the group stage of the Copa, the league of each team, 1ª FEB for a 1ª FEB rival) feed THEIR tables. The
league baselines (league rates, spread, zones, ``sample_games.league``) still come from the match's own collection only, as before. A game
stored in two collections counts once. FEB only; any failure listing the collections leaves just the own collection.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Iterator, List, Sequence, Tuple

LEAGUE_KEY = "_league_game"   # set on the games that are NOT of the own collection: they feed the teams, not the league baselines


def _same_season(service: Any, a: str, b: str) -> bool:
    pa, pb = service._parse_components(a, "FEB"), service._parse_components(b, "FEB")
    return bool(pa["season"]) and service._season_year(pa["season"]) == service._season_year(pb["season"])


def source_collections(handler: Any, collection: str, team_ids: Sequence[str]) -> List[Tuple[str, bool]]:
    """``[(collection, is_league_source)]``: the own collection first, then every FEB collection of the same season with a game of the teams."""
    from src.services.collection_service import CollectionService

    sources: List[Tuple[str, bool]] = [(collection, True)]
    service = CollectionService(handler)
    try:
        connection = handler.repository.connection
        wanted = {"HEADER.TEAM.id": {"$in": [str(t) for t in team_ids]}}
        for name in sorted(connection.get_database().list_collection_names()):
            if name == collection or service._FBCYL_PREFIX.match(name) or service._SKIP_PREFIXES.match(name) or name in service._SKIP_NAMES:
                continue
            if _same_season(service, collection, name) and connection.get_collection(name).find_one(wanted, {"_id": 1}) is not None:
                sources.append((name, False))
    except Exception:  # noqa: BLE001 - the extra sources only enrich the package: the own collection always works
        return [(collection, True)]
    return sources


def games_of_sources(handler: Any, sources: Sequence[Tuple[str, bool]], team_ids: Sequence[str], query: Dict[str, Any],
                     projection: Dict[str, int]) -> Iterator[Dict[str, Any]]:
    """The games of every source, one at a time: all of the own collection, only those of ``team_ids`` in the others; each game once."""
    seen = set()
    wanted = [str(t) for t in team_ids]
    for name, league in sources:
        collection = handler.repository.connection.get_collection(name)
        cursor = collection.find(query if league else {**query, "HEADER.TEAM.id": {"$in": wanted}}, {**projection, "_id": 1})
        for game in cursor:
            key = game.get("_id")
            if key is not None and key in seen:
                continue
            seen.add(key)
            if not league:
                game[LEAGUE_KEY] = False
            yield game
