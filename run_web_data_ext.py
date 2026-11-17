"""Entry point of the publication of the external sources (#884): ``python run_web_data_ext.py --archive archive-ext --out DIR [--closed]``.

Writes what the web reads of ACB, FIBA and NCAA (``src/external/publish``): the sealed rows of every external competition that is in the external archive and the manifest ``index.json`` with the ``league`` of each
competition and the freshness of each source. Needs ``PACKAGE_MASTER_KEY`` (or ``PACKAGE_PASSWORD``, >= 8 characters), the same as ``web-data`` so that one open key opens both publications, and the ephemeral
Mongo of the run (``MONGODB_CONNECTION_STRING``). It publishes to its own branch (``web-data-ext.yml``): a failure here never stops the data of Analytics. See docs/OPERATIONS.md.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))


def main(argv=None, handler=None) -> int:
    parser = argparse.ArgumentParser(description="Publish the sealed rows of the external sources for the web")
    parser.add_argument("--archive", default="archive-ext", help="the external archive: one folder per source")
    parser.add_argument("--out", required=True)
    parser.add_argument("--catalogue", default=None)
    parser.add_argument("--closed", action="store_true", help="do not wrap for the open scope")
    args = parser.parse_args(argv)

    from src.external.publish import publish_external
    from src.live_prep.package_sealing import make_sealer
    from src.services.competition_catalogue import DEFAULT_CATALOGUE, load_catalogue

    try:
        sealer = make_sealer({"mode": "scoped", "open": not args.closed}, os.environ)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    if handler is None:
        from src.database.shared_handler import shared_handler

        handler = shared_handler()
    manifest = publish_external(Path(args.archive), Path(args.out), load_catalogue(args.catalogue or DEFAULT_CATALOGUE), handler, sealer)
    for source in manifest["sources"]:
        print(f"{source['source']}: {source['state']}, last good run {source.get('last_ok', 'never')}, {source['published']} of {source['games']} games published ({source['unreliable']} do not reconcile)")
    print(f"{len(manifest['rows'])} competitions, {len(manifest['sources'])} sources")
    return 0


if __name__ == "__main__":
    sys.exit(main())
