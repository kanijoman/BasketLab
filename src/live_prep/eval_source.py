"""Where the rule evaluator reads its games from: MongoDB or a folder, always in date order.

The package of a game may only use the games played BEFORE it, so everything here is about order: games come sorted
by their start, and ``same_start_groups`` keeps games that start together apart from each other (none may see the
others in its package). MongoDB games are fetched one at a time: only the ids and dates are held in memory.
"""

from __future__ import annotations

import gzip
import heapq
import itertools
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Union

from src.utils.collection_utils import is_fbcyl

from .db_source import GAME_PROJECTION

START_FORMAT = "%d-%m-%Y - %H:%M"
_WITH_PBP = {"PLAYBYPLAY.LINES": {"$exists": True, "$ne": None}}


def parse_starttime(source: Union[str, Dict[str, Any], None]) -> Optional[datetime]:
    """``HEADER.starttime`` of a game (or the text itself), e.g. ``10-10-2026 - 17:00``; None when unreadable."""
    text = (source.get("HEADER") or {}).get("starttime") if isinstance(source, dict) else source
    try:
        return datetime.strptime(str(text), START_FORMAT)
    except (TypeError, ValueError):
        return None


def game_code(game: Dict[str, Any]) -> str:
    """The FEB match code: the document id in MongoDB, else the header's ``game_code``."""
    code = game.get("_id") or (game.get("HEADER") or {}).get("game_code")
    return str(code) if code not in (None, "") else ""


def _has_pbp(game: Dict[str, Any]) -> bool:
    return bool((game.get("PLAYBYPLAY") or {}).get("LINES"))


def _order_key(game: Dict[str, Any]):
    start = parse_starttime(game)
    return (start is None, start or datetime.min, game_code(game))


def games_from_dir(path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Every ``*.json`` / ``*.json.gz`` game of a folder that has a play-by-play, in date order (undated last)."""
    games = []
    for file in sorted(Path(path).iterdir()):
        if not file.name.endswith((".json", ".json.gz")):
            continue
        raw = file.read_bytes()
        game = json.loads((gzip.decompress(raw) if file.name.endswith(".gz") else raw).decode("utf-8"))
        if isinstance(game, dict) and _has_pbp(game):
            games.append(game)
    return sorted(games, key=_order_key)


def _fbcyl_games(mongo: Any) -> Iterator[Dict[str, Any]]:
    """The games of a FBCYL collection with moves, adapted to the FEB document, in date order.

    The kick-off is text (``Oct 3, 2026, 6:30:00 PM``) that the server cannot parse: only ids and that text are read first and sorted here."""
    from .fbcyl_adapter import starttime
    from .game_sources import FBCYL

    def when(stats: Dict[str, Any]):
        parsed = parse_starttime(starttime(stats))
        return (parsed is None, parsed or datetime.min)

    heads = [(when((row.get("stats") or {})), str((row.get("stats") or {}).get("idMatchExtern") or row["_id"]), row["_id"])
             for row in mongo.find(FBCYL.with_pbp, {"stats.time": 1, "stats.idMatchExtern": 1})]
    for _, _, key in sorted(heads, key=lambda h: (h[0], h[1])):
        stored = mongo.find_one({"_id": key}, FBCYL.projection)
        if stored is not None:
            yield FBCYL.adapt(stored)


def games_from_mongo(handler: Any, collection: str, team_id: Optional[str] = None) -> Iterator[Dict[str, Any]]:
    """The games of a FEB collection with play-by-play, in date order, one document in memory at a time; only those of ``team_id`` if given (#638).

    A first aggregation sorts only ids and dates (``HEADER.starttime`` is text, so it is parsed on the server);
    each game is then fetched with the replay projection (header, roster, play-by-play and shot chart).
    """
    mongo = handler.repository.connection.get_collection(collection)
    if is_fbcyl(collection):
        yield from _fbcyl_games(mongo)
        return
    pipeline = [
        {"$match": {**_WITH_PBP, **({"HEADER.TEAM.id": str(team_id)} if team_id is not None else {})}},
        {"$project": {"start": {"$dateFromString": {"dateString": "$HEADER.starttime", "format": "%d-%m-%Y - %H:%M",
                                                    "onError": None, "onNull": None}}}},
        {"$sort": {"start": 1, "_id": 1}},
    ]
    for row in mongo.aggregate(pipeline, allowDiskUse=True):
        game = mongo.find_one({"_id": row["_id"]}, GAME_PROJECTION)
        if game is not None:
            yield game


def same_start_groups(games: Iterable[Dict[str, Any]]) -> Iterator[List[Dict[str, Any]]]:
    """Consecutive games with the same start (undated ones count as different) as lists, in order."""
    def key(game: Dict[str, Any]):
        start = parse_starttime(game)
        return start if start is not None else ("undated", game_code(game))

    for _, group in itertools.groupby(games, key=key):
        yield list(group)


def merge_recordings(games: Iterable[Dict[str, Any]], recordings: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """The games plus, for each recording not already among them, its final document, all in date order.

    A recording of a match that is not (yet) in the source still has to be evaluated, and in its place in time so
    that its package only uses earlier games. When the source has the match, the stored game wins.
    """
    extra = []
    for code, feed in recordings.items():
        doc = feed.document_at(feed.duration + 1)
        if doc is not None and _has_pbp(doc):
            doc.setdefault("_id", str(code))
            extra.append(doc)
    extra.sort(key=_order_key)
    last = None
    for game in heapq.merge(games, extra, key=_order_key):  # equal keys: the source first, so its copy wins
        code = game_code(game)
        if code and code == last:
            continue
        last = code
        yield game
