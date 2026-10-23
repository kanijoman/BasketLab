"""Drop the old index ``header_local_team_name_1`` of the FEB collections (issue #137).

It was built on ``HEADER.localTeam.teamName`` (a field FEB games do not have; the index code was corrected to ``HEADER.TEAM.name``) and the collections created before keep it:
useless, and it costs space on the free Atlas tier. ``python run_drop_legacy_indexes.py [--collection NAME] [--apply]``: a dry run by default that lists what it would drop; with
``--apply`` it drops. An index counts as the legacy one only when it has that name **and** is on that key, so a real index that happens to share the name is never touched.
Idempotent. It also says whether the index that replaces it (``HEADER.TEAM.name``) exists.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List, Optional

LEGACY_NAME = "header_local_team_name_1"
LEGACY_FIELD = "HEADER.localTeam.teamName"
REPLACEMENT_FIELD = "HEADER.TEAM.name"


def _fields(index: Dict[str, Any]) -> List[str]:
    return [field for field, _ in index.get("key", {}).items()] if hasattr(index.get("key"), "items") else [field for field, _ in index.get("key", [])]


def drop_legacy_indexes(collection: Any, apply: bool = False) -> Dict[str, Any]:
    """``{found, dropped, replacement}`` for one collection: the legacy indexes it has, the ones dropped (only with ``apply``) and whether ``HEADER.TEAM.name`` is indexed."""
    indexes = list(collection.list_indexes())
    found = [i["name"] for i in indexes if i["name"] == LEGACY_NAME and _fields(i) == [LEGACY_FIELD]]
    dropped: List[str] = []
    if apply:
        for name in found:
            collection.drop_index(name)
            dropped.append(name)
    replacement = any(_fields(i) == [REPLACEMENT_FIELD] for i in indexes)
    return {"found": found, "dropped": dropped, "replacement": replacement}


def run(db: Any, apply: bool = False, only: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """The report of every FEB collection (or of ``only``): FBCYL and the internal collections are not touched."""
    from src.services.derived_backfill import feb_collection_names

    available = feb_collection_names(db)
    if only is not None and only not in available:
        raise ValueError(f"{only} no es una colección de partidos FEB de la base de datos")
    return {name: drop_legacy_indexes(db[name], apply=apply) for name in sorted([only] if only else available)}


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Drop the legacy index header_local_team_name_1 of the FEB collections (dry run unless --apply)")
    parser.add_argument("--collection", help="only this collection (default: every FEB games collection)")
    parser.add_argument("--apply", action="store_true", help="drop the indexes (without it only the list of what would be dropped)")
    parser.add_argument("--require-env", action="store_true", help="fail unless MONGODB_CONNECTION_STRING is set (CI)")
    args = parser.parse_args(argv)
    if args.require_env and not os.environ.get("MONGODB_CONNECTION_STRING"):
        print("MONGODB_CONNECTION_STRING is not set", file=sys.stderr)
        return 2

    from pymongo import MongoClient

    from src.database.db_config import get_mongodb_connection_string

    conn = get_mongodb_connection_string()
    if not conn:
        print("No MongoDB connection string (MONGODB_CONNECTION_STRING or db_credentials.txt)", file=sys.stderr)
        return 2
    try:
        report = run(MongoClient(conn)["BASKETBALL"], apply=args.apply, only=args.collection)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    total = 0
    for name, result in report.items():
        if result["found"]:
            total += len(result["found"])
            print(f"{name}: {'eliminado' if result['dropped'] else 'se eliminaría'} {', '.join(result['found'])}"
                  f"{'' if result['replacement'] else ' (¡sin el índice HEADER.TEAM.name que lo sustituye!)'}")
    print(f"{len(report)} colecciones revisadas; {total} índices antiguos {'eliminados' if args.apply else 'encontrados (ejecuta con --apply para eliminarlos)'}.")
    return 0
