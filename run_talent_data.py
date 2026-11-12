"""Entry point of the Talent publication (#878): ``python run_talent_data.py --out DIR [--rosters DIR] [--collection NAME ...] [--closed]``.

Writes what BasketLab Talent reads (``src/market/publish``): one sealed file per competition and season with a row per player, team and competition, and the manifest ``index.json``. Needs
``PACKAGE_MASTER_KEY`` (or ``PACKAGE_PASSWORD``, >= 8 characters) like ``web-data``. ``--rosters`` is the ``rosters/`` folder of the private ``basketlab-archive-ext`` (the roster sweep writes it,
#905): without it the rows have no birth date, height or position. The workflow ``talent-data.yml`` starts from the previous publication so that what did not change keeps its bytes.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Publish the sealed player rows of BasketLab Talent")
    parser.add_argument("--out", required=True)
    parser.add_argument("--rosters", help="folder with rosters/<season>.json (default: no rosters)")
    parser.add_argument("--collection", action="append", help="only this collection (repeatable); only for tests: the competitions of the others are not published")
    parser.add_argument("--closed", action="store_true", help="do not wrap for the open scope")
    args = parser.parse_args(argv)

    from src.database.shared_handler import shared_handler
    from src.live_prep.package_sealing import make_sealer
    from src.market.publish import publish_talent_data
    from src.market.roster_store import read_rosters
    from src.services.competition_catalogue import DEFAULT_CATALOGUE, load_catalogue
    from src.services.derived_backfill import fbcyl_collection_names, feb_collection_names

    handler = shared_handler()
    db = handler.connection.client["BASKETBALL"]
    names = args.collection or sorted(set(feb_collection_names(db)) | set(fbcyl_collection_names(db)))
    try:
        sealer = make_sealer({"mode": "scoped", "open": not args.closed}, os.environ)
        roster = read_rosters(args.rosters) if args.rosters else []
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    started = time.time()
    unknown = []
    manifest = publish_talent_data(handler.connection, args.out, sealer, names, load_catalogue(DEFAULT_CATALOGUE), roster_rows=roster,
                                   on_competition=lambda c, players, groups: print(f"{c.key}: {players} players, {groups} collections, {time.time() - started:.0f} s", flush=True),
                                   on_unknown=unknown.extend)
    if unknown:
        print(f"{len(unknown)} collections say neither their competition nor their season and are left out: {', '.join(unknown)}")
    size = sum(e["bytes"] for e in manifest["competitions"])
    print(f"{len(manifest['competitions'])} competitions, {size / 1024:.0f} KB, {sum(e['players'] for e in manifest['competitions'])} rows, {len(roster)} roster rows, {time.time() - started:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
