"""Where the games of a package come from: the match's collection plus every other game of its two teams in the season (issues #456, #445).

A knockout tie has 0-1 games per team in its own collection and a rival of another division has none, so the games of both teams in the other
competitions and phases of the season (the group stage of the Copa, the league of each team, 1ª FEB for a 1ª FEB rival) feed THEIR tables. The
league baselines (league rates, spread, zones, ``sample_games.league``) still come from the match's own collection only, as before. A game
stored in two collections counts once. Any failure listing the collections leaves just the own collection.

FEB and FBCYL are two ``Feed``s: how to read a stored game (projection, which ones have play-by-play, how to find the games of some teams) and how
to turn it into the FEB document the engine reads (FBCYL: ``fbcyl_adapter``). A collection only mixes with collections of its own league.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, Iterator, List, NamedTuple, Optional, Sequence, Tuple

from src.utils.collection_utils import is_fbcyl

LEVEL_KEY = "_level"           # the division (catalog ``level``) of the collection a game was read from, when it has one (issue #464)
LEAGUE_KEY = "_league_game"   # set on the games that are NOT of the own collection: they feed the teams, not the league baselines

# What the builder replays: header, roster ids, play-by-play and the shot chart. The repository's own PBP cursor omits SHOTCHART, hence this
# dedicated projection.
FEB_PROJECTION: Dict[str, int] = {
    "HEADER": 1,
    "BOXSCORE.TEAM.id": 1,
    "BOXSCORE.TEAM.PLAYER.id": 1,
    "BOXSCORE.TEAM.PLAYER.name": 1,
    "PLAYBYPLAY.LINES": 1,
    "SHOTCHART.SHOTS": 1,
    "DERIVED": 1,      # exact possessions and points by origin, stored per game (scouting reads them: no box score totals here)
}
FBCYL_PROJECTION: Dict[str, int] = {
    "uuid": 1, "moves": 1, "_season": 1, "_league": 1, "_competition": 1,
    "stats.idMatchExtern": 1, "stats.time": 1, "stats.localId": 1, "stats.visitId": 1, "stats.periodDurationList": 1,
    "stats.teams.teamIdIntern": 1, "stats.teams.teamIdExtern": 1, "stats.teams.name": 1, "stats.teams.data.score": 1,
    "stats.teams.players.actorId": 1, "stats.teams.players.name": 1, "stats.teams.players.dorsal": 1, "stats.teams.players.captain": 1,
}


class Feed(NamedTuple):
    projection: Dict[str, int]
    with_pbp: Dict[str, Any]
    teams_filter: Callable[[Sequence[str]], Dict[str, Any]]
    adapt: Callable[[Dict[str, Any]], Dict[str, Any]]


def _fbcyl_ids(team_ids: Sequence[str]) -> List[Any]:
    """The stable team ids of FBCYL are numbers in the database and strings everywhere else."""
    return [v for t in team_ids for v in ((str(t), int(t)) if str(t).isdigit() else (str(t),))]


def _fbcyl_adapt(game: Dict[str, Any]) -> Dict[str, Any]:
    from .fbcyl_adapter import to_feb_document

    return to_feb_document(game)


FEB = Feed(FEB_PROJECTION, {"PLAYBYPLAY.LINES": {"$exists": True, "$ne": None}},
           lambda ids: {"HEADER.TEAM.id": {"$in": [str(t) for t in ids]}}, lambda game: game)
FBCYL = Feed(FBCYL_PROJECTION, {"moves.0": {"$exists": True}}, lambda ids: {"stats.teams.teamIdExtern": {"$in": _fbcyl_ids(ids)}}, _fbcyl_adapt)


def feed_of(collection: str) -> Feed:
    return FBCYL if is_fbcyl(collection) else FEB


def _season_token(name: str) -> str:
    """FBCYL names end with the year of the season (``FBCYL_1ª_FASE-GRUPO_A-1_2026_``)."""
    years = re.findall(r"(?<!\d)(20\d\d)(?!\d)", name)
    return years[-1] if years else ""


def _same_season(service: Any, a: str, b: str) -> bool:
    if is_fbcyl(a) or is_fbcyl(b):
        competition = lambda n: n.split("_")[1] if n.count("_") else n
        return is_fbcyl(a) and is_fbcyl(b) and competition(a) == competition(b) and bool(_season_token(a)) and _season_token(a) == _season_token(b)
    pa, pb = service._parse_components(a, "FEB"), service._parse_components(b, "FEB")
    return bool(pa["season"]) and service._season_year(pa["season"]) == service._season_year(pb["season"])


# the last part of a FEB collection name says the phase: «Play-offs_1_16_Final», «FASE_DE_GRUPOS_A», «Eliminatorias_de_Ascenso» (a regular league says «Liga_Regular_…»)
_PHASE = re.compile(r"(play-?offs?|eliminatoria|fase|octavos|cuartos|semifinal|final)", re.IGNORECASE)


def is_knockout(collection: str) -> bool:
    """A knockout or play-off collection: a tie has 0-1 games per team there, so its league cannot be only its own games (issue #464)."""
    return not is_fbcyl(collection) and "Liga_Regular" not in collection and "FASE_DE_GRUPOS" not in collection.upper() and bool(_PHASE.search(collection))


def _same_competition(service: Any, a: str, b: str) -> bool:
    return service._parse_components(a, "FEB")["competition"] == service._parse_components(b, "FEB")["competition"]


def source_collections(handler: Any, collection: str, team_ids: Sequence[str]) -> List[Tuple[str, bool]]:
    """``[(collection, is_league_source)]``: the own collection first, then every collection of the same league and season with a game of the teams.

    A knockout (``is_knockout``) pools its league with the other phases of its competition and season (the group stage of the Copa, the
    regular groups of a league before its play-offs): they are league sources even without a game of the teams. A regular group is its own league
    (the groups of 2ª FEB are different leagues) and the games of other competitions only feed the tables of the teams."""
    from src.services.collection_service import CollectionService

    sources: List[Tuple[str, bool]] = [(collection, True)]
    service = CollectionService(handler)
    feed = feed_of(collection)
    pools = is_knockout(collection)
    try:
        connection = handler.repository.connection
        wanted = feed.teams_filter(team_ids)
        for name in sorted(connection.get_database().list_collection_names()):
            if name == collection or is_fbcyl(name) != is_fbcyl(collection) or service._SKIP_PREFIXES.match(name) or name in service._SKIP_NAMES:
                continue
            if not _same_season(service, collection, name):
                continue
            league = pools and _same_competition(service, collection, name) and connection.get_collection(name).find_one(feed.with_pbp, {"_id": 1}) is not None
            if league or connection.get_collection(name).find_one(wanted, {"_id": 1}) is not None:
                sources.append((name, league))
    except Exception:  # noqa: BLE001 - the extra sources only enrich the package: the own collection always works
        return [(collection, True)]
    return sources


def games_of_sources(handler: Any, sources: Sequence[Tuple[str, bool]], team_ids: Sequence[str],
                     level_of: Optional[Callable[[str], Optional[int]]] = None) -> Iterator[Dict[str, Any]]:
    """The games of every source as FEB documents, one at a time: all of the own collection, only those of ``team_ids`` in the others; each game once.

    ``level_of(collection)`` (the catalog division, ``None`` for a cup) tags each game with ``LEVEL_KEY``: the division a team belongs to is where it plays."""
    seen = set()
    for name, league in sources:
        level = level_of(name) if level_of else None
        feed = feed_of(name)
        collection = handler.repository.connection.get_collection(name)
        cursor = collection.find(feed.with_pbp if league else {**feed.with_pbp, **feed.teams_filter(team_ids)}, {**feed.projection, "_id": 1})
        for stored in cursor:
            game = feed.adapt(stored)
            key = game.get("_id")
            if key is not None and key in seen:
                continue
            seen.add(key)
            if not league:
                game[LEAGUE_KEY] = False
            if level is not None:
                game[LEVEL_KEY] = level
            yield game
