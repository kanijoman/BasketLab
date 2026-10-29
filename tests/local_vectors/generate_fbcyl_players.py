"""Regenerate ``players_fbcyl.json``: the parity vectors of the FBCYL player table of the local-first data (#644).

The reference is what ``GET /players/{collection}`` answers for an FBCYL league: the season pipeline of ``FBCYLPipelineBuilder`` plus the advanced figures
of ``PlayerStatsService``. That pipeline uses ``$substrCP``, ``$reduce`` and ``$getField``, which mongomock does not implement, so the ``cases`` are
produced on a REAL ``mongod`` (``MONGODB_CONNECTION_STRING`` or localhost, a scratch database that is dropped) and committed; CI does not regenerate
them. The ``rows`` (the exporter's, mongomock is enough) are regenerated and checked everywhere.
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import mongomock

sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[2] / "src"), str(Path(__file__).resolve().parent)]

from fbcyl_games import build_games  # noqa: E402
from generate import FILTERS, _fbcyl_in_range  # noqa: E402

from src.database.repository import BasketballRepository  # noqa: E402
from src.local_data.export import fbcyl_player_rows  # noqa: E402
from src.services._team_id import with_team_id  # noqa: E402
from src.services.player_stats_service import PlayerStatsService  # noqa: E402

OUT = Path(__file__).resolve().parent / "players_fbcyl.json"
COLLECTION = "FBCYL_LEAGUE"
SCRATCH = "BASKETLAB_VECTORS_644"
PLAYER_FILTERS = FILTERS + [
    {"name": "one team", "team": "BRAVO"},
    {"name": "one team away won", "team": "CARLOS", "venue": "away", "result": "won"},
    {"name": "unknown team", "team": "NOBODY"},
]


def _repository(collection) -> BasketballRepository:
    conn = MagicMock()
    conn.is_connected.return_value = True
    conn.get_collection.side_effect = lambda name: collection
    return BasketballRepository(conn)


def _clean(rows: list) -> list:
    return [{k: v for k, v in row.items() if k != "_id"} for row in rows]


def _players(db, games: list, everything, filt: dict) -> list:
    """What the API answers: the players of the games in range, their advanced figures from the season-wide team context."""
    db.drop_collection(COLLECTION)
    if games:
        db[COLLECTION].insert_many(games)
    venue = {"home": True, "away": False}.get(filt.get("venue"))
    players = _repository(db[COLLECTION]).get_player_stats(COLLECTION, None, venue, filt.get("result"), team_filter=filt.get("team")) or []
    if players:
        handler = type("Handler", (), {"get_team_stats": lambda self, c: with_team_id(everything.get_team_stats(c)),
                                       "get_opponent_stats": lambda self, c: with_team_id(everything.get_opponent_stats(c))})()
        PlayerStatsService(handler)._enrich_with_advanced_stats(COLLECTION, players)
    # the pipeline sorts by team and points; Mongo does not say which of two players with the same points comes first: the file breaks the tie by id
    return sorted(_clean(players), key=lambda p: (p["team_name"], -p["total_pts"], str(p["player_id"])))


def build_rows() -> list:
    col = mongomock.MongoClient()["v"][COLLECTION]
    col.insert_many(build_games())
    return fbcyl_player_rows(col)


def build_cases(client) -> list:
    db = client[SCRATCH]
    try:
        db.drop_collection("ALL")
        db["ALL"].insert_many(build_games())
        everything = _repository(db["ALL"])
        return [{"filter": {k: v for k, v in f.items() if k != "name"}, "name": f["name"],
                 "players": _players(db, [g for g in build_games() if _fbcyl_in_range(g, f)], everything, f)} for f in PLAYER_FILTERS]
    finally:
        client.drop_database(SCRATCH)


def main() -> None:
    from pymongo import MongoClient

    previous = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"cases": []}
    client = MongoClient(os.environ.get("MONGODB_CONNECTION_STRING", "mongodb://localhost:27017/"), serverSelectionTimeoutMS=3000)
    try:
        client.admin.command("ping")
        cases = build_cases(client)
    except Exception as error:  # noqa: BLE001 - no real mongod: keep the committed reference, refresh only the rows
        print("no real mongod, keeping the committed cases:", type(error).__name__)
        cases = previous["cases"]
    OUT.write_text(json.dumps({"rows": build_rows(), "cases": cases}, ensure_ascii=False, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
