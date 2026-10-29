"""Entry point of the private archive of the games (#646).

``python run_archive.py dump --out DIR [--collection NAME ...]`` writes the archive of the database (seeding it from a local database, or saving it
after a refresh); ``python run_archive.py load --src DIR --replace`` restores it into the database of ``MONGODB_CONNECTION_STRING`` (the ephemeral
Mongo of a job): it REPLACES the collections it holds, so it needs ``--replace``.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Dump or restore the archive of the games")
    sub = parser.add_subparsers(dest="command", required=True)
    dump = sub.add_parser("dump", help="write the archive of the database")
    dump.add_argument("--out", required=True)
    dump.add_argument("--collection", action="append", help="only this collection (repeatable); the rest of the archive is kept")
    load = sub.add_parser("load", help="restore the archive into the database (replaces its collections)")
    load.add_argument("--src", required=True)
    load.add_argument("--collection", action="append")
    load.add_argument("--replace", action="store_true", help="required: the collections of the archive are dropped and rewritten")
    args = parser.parse_args(argv)

    from pymongo import MongoClient

    from src.database.db_config import get_mongodb_connection_string
    from src.local_data.archive import dump_archive, load_archive

    db = MongoClient(get_mongodb_connection_string())["BASKETBALL"]
    started = time.time()
    if args.command == "dump":
        manifest = dump_archive(db, args.out, only=args.collection)
        games, size = sum(c["games"] for c in manifest["collections"]), sum(c["bytes"] for c in manifest["collections"])
        print(f"{len(manifest['collections'])} collections, {games} games, {size / 1e6:.1f} MB, {time.time() - started:.0f} s")
        return 0
    if not args.replace:
        print("load replaces the collections of the archive: pass --replace", file=sys.stderr)
        return 2
    loaded = load_archive(args.src, db, only=args.collection)
    print(f"{len(loaded)} collections, {sum(loaded.values())} games, {time.time() - started:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
