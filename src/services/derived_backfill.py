"""Backfill of ``DERIVED`` (exact possessions, validated rebounds / turnovers) in the FEB and FBCYL games already stored (#372, #373).

``python run_backfill_derived.py [--collection NAME]``: new games get the field on insertion; this covers the ones stored
before, and re-computes the ones with an older ``DERIVED.v``. Idempotent. Iterates a projected cursor (one game at a time).
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, Optional

from src.pbp.game_derived import DERIVED_VERSION, derive_game_fields

_PROJECTION = {"BOXSCORE.TEAM": 1, "PLAYBYPLAY.LINES": 1, "SHOTCHART.SHOTS": 1}
_FBCYL_PROJECTION = {"moves": 1, "stats.teams": 1, "stats.periodDurationList": 1}


def backfill_collection(collection: Any, fbcyl: bool = False) -> Dict[str, int]:
    """Store ``DERIVED`` in every game of the collection (FEB, or FBCYL with ``fbcyl``) that lacks the current version."""
    result = {"updated": 0, "skipped": collection.count_documents({"DERIVED.v": DERIVED_VERSION}), "unreadable": 0}
    query = {"moves": {"$exists": True}, "DERIVED.v": {"$ne": DERIVED_VERSION}} if fbcyl else {"BOXSCORE": {"$exists": True}, "DERIVED.v": {"$ne": DERIVED_VERSION}}
    for game in collection.find(query, _FBCYL_PROJECTION if fbcyl else _PROJECTION):
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


def fbcyl_collection_names(db: Any) -> list:
    """Every collection of FBCYL games (by the name, like ``CollectionService``)."""
    from src.services.collection_service import CollectionService as C

    return [n for n in db.list_collection_names() if n not in C._SKIP_NAMES and C._FBCYL_PREFIX.match(n)]


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill DERIVED in the stored FEB and FBCYL games")
    parser.add_argument("--collection", help="only this collection (default: every games collection, FEB and FBCYL)")
    parser.add_argument("--require-env", action="store_true", help="fail unless MONGODB_CONNECTION_STRING is set (CI)")
    args = parser.parse_args(argv)
    if args.require_env and not os.environ.get("MONGODB_CONNECTION_STRING"):
        print("MONGODB_CONNECTION_STRING is not set (GitHub secret ATLAS_WRITE_URI)", file=sys.stderr)
        return 2

    from pymongo import MongoClient

    from src.database.db_config import get_mongodb_connection_string

    conn = get_mongodb_connection_string()
    if not conn:
        print("No MongoDB connection string (MONGODB_CONNECTION_STRING or db_credentials.txt)", file=sys.stderr)
        return 2
    db = MongoClient(conn)["BASKETBALL"]
    fbcyl = set(fbcyl_collection_names(db))
    names = [args.collection] if args.collection else feb_collection_names(db) + sorted(fbcyl)
    for name in sorted(names):
        print(name, backfill_collection(db[name], fbcyl=name in fbcyl))
    return 0
