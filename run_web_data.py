"""Entry point of the web artifacts (#328): ``python run_web_data.py --out DIR [--collection NAME ...] [--closed]``.

Writes what the web reads (``src/local_data/web_data``): the sealed rows and reports of every games collection and the manifest ``index.json``. Needs
``PACKAGE_MASTER_KEY`` (or ``PACKAGE_PASSWORD``, >= 8 characters) like the live packages. The workflow ``web-data.yml`` starts from the previous
publication so that what did not change keeps its bytes. ``--closed`` leaves the open scope out (the beta is over).
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Publish the sealed rows and reports for the web")
    parser.add_argument("--out", required=True)
    parser.add_argument("--collection", action="append", help="only this collection (repeatable); the rest of the previous publication is kept")
    parser.add_argument("--closed", action="store_true", help="do not wrap for the open scope")
    parser.add_argument("--scouting", action="append", help="also scout the teams of this collection (repeatable); default: the competitions where a club of interest plays")
    parser.add_argument("--no-scouting", action="store_true", help="do not publish the full scouting of the rival (it takes about ten seconds per team)")
    args = parser.parse_args(argv)

    from src.api.deps import _create_handler
    from src.live_prep.package_sealing import make_sealer
    from src.local_data.web_data import publish_web_data
    from src.local_data.scouting_export import interest_clubs, scouting_collections
    from src.services.derived_backfill import fbcyl_collection_names, feb_collection_names

    handler = _create_handler()
    db = handler.connection.client["BASKETBALL"]
    names = args.collection or sorted(set(feb_collection_names(db)) | set(fbcyl_collection_names(db)))
    try:
        sealer = make_sealer({"mode": "scoped", "open": not args.closed}, os.environ)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    scouting = [] if args.no_scouting else (args.scouting or [n for n in scouting_collections(handler, interest_clubs()) if n in names])
    started = time.time()
    manifest = publish_web_data(handler, args.out, sealer, names, keep_others=bool(args.collection), scouting=scouting,
                                on_collection=lambda name: print(f"{name}: {time.time() - started:.0f} s"))
    size = sum(e["bytes"] for e in manifest["rows"] + manifest["reports"])
    print(f"{len(manifest['rows'])} competitions, {size / 1024:.0f} KB (manifests), {time.time() - started:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
