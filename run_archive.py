"""Entry point of the private archive of the games (#646).

``python run_archive.py dump --out DIR [--collection NAME ...]`` writes the archive of the database (seeding it from a local database, or saving it
after a refresh); ``python run_archive.py load --src DIR --replace`` restores it into the database of ``MONGODB_CONNECTION_STRING`` (the ephemeral
Mongo of a job): it REPLACES the collections it holds, so it needs ``--replace``. ``pull --repo URL --dir DIR`` downloads the archive from the
private repository and ``push --repo URL --dir DIR`` saves it back (only when it changed; the last versions stay tagged), see ``archive_repo``.
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
    dump.add_argument("--no-shrink", action="store_true", help="refuse (exit 1, nothing written) to replace the archive in --out with fewer games")
    load = sub.add_parser("load", help="restore the archive into the database (replaces its collections)")
    load.add_argument("--src", required=True)
    load.add_argument("--collection", action="append")
    load.add_argument("--replace", action="store_true", help="required: the collections of the archive are dropped and rewritten")
    pull = sub.add_parser("pull", help="download the archive from the private repository")
    push = sub.add_parser("push", help="save the archive in the private repository (only if it changed)")
    for sync in (pull, push):
        sync.add_argument("--repo", required=True, help="git URL of the private repository")
        sync.add_argument("--dir", required=True)
    push.add_argument("--message", default="Archive refresh")
    args = parser.parse_args(argv)

    if args.command in ("pull", "push"):
        from src.local_data import archive_repo

        if args.command == "pull":
            archive_repo.pull(args.repo, args.dir)
            print(f"archive downloaded into {args.dir}")
        else:
            print("archive saved" if archive_repo.push(args.repo, args.dir, args.message) else "archive unchanged: nothing pushed")
        return 0

    from pymongo import MongoClient

    from src.database.db_config import get_mongodb_connection_string
    from src.local_data.archive import dump_archive, load_archive

    db = MongoClient(get_mongodb_connection_string())["BASKETBALL"]
    started = time.time()
    if args.command == "dump":
        try:
            manifest = dump_archive(db, args.out, only=args.collection, allow_shrink=not args.no_shrink)
        except ValueError as error:
            print(error, file=sys.stderr)
            return 1
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
