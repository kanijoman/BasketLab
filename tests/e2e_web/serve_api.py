"""API server for the web smoke e2e (issue #111): the real FastAPI app on an in-memory MongoDB.

``python tests/e2e_web/serve_api.py [port]`` patches ``pymongo.MongoClient`` with mongomock BEFORE the
database handler is created, seeds one competition from the committed FEB sample game and serves the app
with uvicorn. No credentials, no network.
"""
import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

COLLECTION = "L_F_-2_2025_2026_Liga_Regular_B"  # a name the collection list recognises as FEB


def _unwrap(node):
    """Extended-JSON wrappers of the sample ($numberInt, ...) to plain numbers."""
    if isinstance(node, dict):
        if len(node) == 1:
            key, value = next(iter(node.items()))
            if key == "$numberInt":
                return int(value)
            if key in ("$numberDouble", "$numberLong"):
                return float(value) if key == "$numberDouble" else int(value)
        return {k: _unwrap(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_unwrap(v) for v in node]
    return node


def seed(client) -> str:
    sample = _unwrap(json.loads((ROOT / "src" / "JSON_samples" / "feb_game.json").read_text(encoding="utf-8")))
    db = client["BASKETBALL"]
    for i in range(1, 4):
        doc = copy.deepcopy(sample)
        doc["_id"] = 9000 + i
        doc["_season"] = "2025-2026"
        doc["_competition"] = "L F -2"
        db[COLLECTION].insert_one(doc)
    db["COLLECTION_META"].insert_one({"_id": COLLECTION, "competition_url": "https://example.invalid/cal"})
    return COLLECTION


def main() -> None:
    import mongomock
    import pymongo

    pymongo.MongoClient = mongomock.MongoClient  # type: ignore[assignment]
    from src.api import deps

    handler = deps._create_handler()
    seed(handler.connection.client)

    import uvicorn
    from src.api.app import app

    uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8000, log_level="warning")


if __name__ == "__main__":
    main()
