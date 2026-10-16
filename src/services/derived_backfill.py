"""Backfill of ``DERIVED`` (exact possessions, validated rebounds / turnovers) in the FEB games already stored (#372).

``python run_backfill_derived.py [--collection NAME]``: new games get the field on insertion; this covers the ones stored
before, and re-computes the ones with an older ``DERIVED.v``. Idempotent. Iterates a projected cursor (one game at a time).
"""
from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, Optional

from src.pbp.game_derived import DERIVED_VERSION, derive_game_fields

_PROJECTION = {"BOXSCORE.TEAM": 1, "PLAYBYPLAY.LINES": 1}


def backfill_collection(collection: Any) -> Dict[str, int]:
    """Store ``DERIVED`` in every FEB game of the collection that lacks the current version."""
    result = {"updated": 0, "skipped": collection.count_documents({"DERIVED.v": DERIVED_VERSION}), "unreadable": 0}
    query = {"BOXSCORE": {"$exists": True}, "DERIVED.v": {"$ne": DERIVED_VERSION}}
    for game in collection.find(query, _PROJECTION):
        derived = derive_game_fields(game)
        if derived is None:
            result["unreadable"] += 1
            continue
        collection.update_one({"_id": game["_id"]}, {"$set": {"DERIVED": derived}})
        result["updated"] += 1
    return result


def feb_collection_names(db: Any) -> list:
    """Every collection of FEB games (what ``CollectionService`` does not skip or tag as FBCYL)."""
    from src.services.collection_service import CollectionService as C

    return [n for n in db.list_collection_names()
            if n not in C._SKIP_NAMES and not C._SKIP_PREFIXES.match(n) and not C._FBCYL_PREFIX.match(n)]


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill DERIVED in the stored FEB games")
    parser.add_argument("--collection", help="only this collection (default: every FEB games collection)")
    args = parser.parse_args(argv)

    from pymongo import MongoClient

    from src.database.db_config import get_mongodb_connection_string

    conn = get_mongodb_connection_string()
    if not conn:
        print("No MongoDB connection string (MONGODB_CONNECTION_STRING or db_credentials.txt)", file=sys.stderr)
        return 2
    db = MongoClient(conn)["BASKETBALL"]
    names = [args.collection] if args.collection else feb_collection_names(db)
    for name in sorted(names):
        print(name, backfill_collection(db[name]))
    return 0
