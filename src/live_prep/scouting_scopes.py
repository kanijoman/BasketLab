"""Where the scouting of a team gets its games from besides its league (issue #638): the cups of the season, and the category of every team.

A team plays its league and the cup in different collections. ``cup_games`` finds the games of the team in the cups of the season of its collection
(by the team id, never by name) and ``team_levels`` maps the teams of the season's leagues to their category (the ``level`` of the competition in the
catalog of the publisher), so that a cup game against a team of another category can be marked. Both are what ``ScoutingRivalService`` uses by default.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, Iterable, List, Optional

from .eval_source import games_from_mongo

COPA = "copa"
_CUP = re.compile(r"COPA", re.IGNORECASE)
_SEASON = re.compile(r"(\d{4}_\d{4})")


def is_cup(collection: str) -> bool:
    return bool(_CUP.search(collection))


def season_of(collection: str) -> Optional[str]:
    found = _SEASON.search(collection)
    return found.group(1) if found else None


def _database(handler: Any) -> Any:
    return handler.connection.client["BASKETBALL"]


def _feb_collections(handler: Any) -> List[str]:
    from src.services.derived_backfill import feb_collection_names

    return sorted(feb_collection_names(_database(handler)))


def cup_collections(names: Iterable[str], collection: str) -> List[str]:
    """The cups of the season of ``collection`` (FEB), other than ``collection`` itself; none when its season cannot be read."""
    season = season_of(collection)
    return [n for n in names if season and n != collection and is_cup(n) and season_of(n) == season]


def cup_games(handler: Any, collection: str, team_id: str, reader: Callable[..., Iterable[Dict[str, Any]]] = games_from_mongo) -> Dict[str, List[Dict[str, Any]]]:
    """``{"copa": games}`` of the team in the cups of the season (with play-by-play, any order: the scouting sorts them), or ``{}`` if it has none.
    A scouting of a cup collection itself has no other cup scope: its own games are the league ones of that call."""
    if is_cup(collection):
        return {}
    games = [g for name in cup_collections(_feb_collections(handler), collection) for g in reader(handler, name, team_id=str(team_id))]
    return {COPA: games} if games else {}


def team_levels(handler: Any, collection: str, catalog: Optional[List[Dict[str, Any]]] = None) -> Dict[str, int]:
    """``{team id: category}`` of the teams of the leagues of the season of ``collection`` that have a ``level`` in the catalog (cups have none).

    A team found in several leagues keeps the highest category (the lowest number). Empty when the season cannot be read or nothing has a level."""
    from .competition_info import competition_infos

    season = season_of(collection)
    if not season:
        return {}
    if catalog is None:
        from .publisher import load_config

        catalog = load_config()["competitions"]
    names = [n for n in _feb_collections(handler) if season_of(n) == season and not is_cup(n)]
    infos = competition_infos(handler, names, catalog, [])
    levels: Dict[str, int] = {}
    database = _database(handler)
    for name in names:
        level = infos[name].get("level")
        if level is None:
            continue
        for team in database[name].distinct("HEADER.TEAM.id"):
            levels[str(team)] = min(levels.get(str(team), level), level)
    return levels
