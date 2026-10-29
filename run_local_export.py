"""Entry point of the local-data export (#327): ``python run_local_export.py [--out DIR] [--collection NAME ...]``.

Writes one file per games collection with the rows of the contract and an ``index.json`` (default ``frontend/public/local-data``, git-ignored),
which the web reads when the local data source is on (``?data=local``).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Export the rows of the local-first contract")
    parser.add_argument("--out", default=os.path.join("frontend", "public", "local-data"))
    parser.add_argument("--collection", action="append", help="only this collection (repeatable); the rest of the directory is kept")
    args = parser.parse_args(argv)

    from pymongo import MongoClient

    from src.database.db_config import get_mongodb_connection_string
    from src.local_data.export import export_all

    db = MongoClient(get_mongodb_connection_string())["BASKETBALL"]
    index = export_all(db, args.out, only=args.collection)
    for entry in index["collections"]:
        print(f"{entry['name']}: {entry['games']} games, {entry['bytes'] / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
