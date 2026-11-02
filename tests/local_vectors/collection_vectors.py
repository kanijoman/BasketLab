"""The vectors of the list of competitions on the device (#705): the names of the real collections (``collection_names.json``: what the database of a working copy had, with its
``Ñ``, ``Ú``, ``º`` and ``ª``) and what ``CollectionService.list_available`` answers for them, the reference of ``frontend/src/localdata/collections.test.ts``.

The browser has no collections: it has the manifest of the publication, one entry per competition with its league and its games. ``published`` is that manifest (the name and the count a
competition would have there; the system collections of the database are not competitions and do not reach it) and ``listed`` what the API answers over the same collections.
"""
import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

from src.services.collection_service import CollectionService

NAMES: List[str] = json.loads((Path(__file__).resolve().parent / "collection_names.json").read_text(encoding="utf-8"))


def games_of(name: str) -> int:
    """A count of games for each collection (the database counts documents): stable and different from one name to the next."""
    return sum(ord(ch) for ch in name) % 97 + 1


def _handler(names: List[str]) -> Any:
    handler = MagicMock()
    handler.is_connected.return_value = True
    handler.connection.get_database.return_value.list_collection_names.return_value = list(names)
    handler.connection.get_collection.side_effect = lambda name: MagicMock(count_documents=lambda *_args, **_kw: games_of(name))
    return handler


def build() -> Dict[str, Any]:
    listed = CollectionService(_handler(NAMES)).list_available()
    return {
        "published": [{"collection": row["name"], "league": row["league"].lower(), "games": row["game_count"]} for row in listed],
        "listed": listed,
        "skipped": [name for name in NAMES if name not in {row["name"] for row in listed}],
    }
