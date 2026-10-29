"""Entry point of the precomputed team reports (#638): ``python run_local_reports.py [--out DIR] [--collection NAME ...] [--closed]``.

One sealed file per team and mode (own analysis, rival scouting) for each games collection, plus ``index.json``. Needs ``PACKAGE_MASTER_KEY``
(or ``PACKAGE_PASSWORD``, >= 8 characters) like the live packages; ``--closed`` leaves the open scope out (the beta is over).
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Precompute and seal the team reports")
    parser.add_argument("--out", default=os.path.join("frontend", "public", "local-data", "reports"))
    parser.add_argument("--collection", action="append", help="only this collection (repeatable); default: every games collection")
    parser.add_argument("--closed", action="store_true", help="do not wrap for the open scope")
    args = parser.parse_args(argv)

    from src.api.deps import _create_handler
    from src.live_prep.package_sealing import make_sealer
    from src.local_data.team_reports import publish_reports
    from src.services.derived_backfill import fbcyl_collection_names, feb_collection_names

    handler = _create_handler()
    db = handler.connection.client["BASKETBALL"]
    names = args.collection or sorted(set(feb_collection_names(db)) | set(fbcyl_collection_names(db)))
    sealer = make_sealer({"mode": "scoped", "open": not args.closed}, os.environ)
    started = time.time()
    last = [started]

    def progress(collection: str, reports: int) -> None:
        now = time.time()
        print(f"{collection}: {reports} reports, {now - last[0]:.1f} s")
        last[0] = now

    index = publish_reports(handler, names, args.out, sealer, on_collection=progress)
    size = sum(e["bytes"] for e in index["reports"])
    print(f"{len(index['reports'])} reports, {size / 1024:.0f} KB, {time.time() - started:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
