"""Add the FBCYL youth and senior competitions to ``config/competitions.json`` (#920): autonomic only, cadete upwards and senior, men and women.

    python run_fbcyl_catalogue.py --season 2026 --paused 2025 --paused 2024      # asks fbcyl.es (one request a second) and adds what is missing
    python run_fbcyl_catalogue.py --season 2026 --combos tests/fixtures/fbcyl_autonomic_combos.json   # the same, from an answer already saved

``--season`` seasons are added active, ``--paused`` ones paused (they are loaded in batches: set ``active`` to true one season at a time). A group already in the catalogue is never added or
changed; a category that is not recognised is reported and left out. See ``src/services/fbcyl_catalogue.py`` and docs/OPERATIONS.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from src.services.competition_catalogue import DEFAULT_CATALOGUE
from src.services.fbcyl_catalogue import fetch_combos, update_catalogue_file


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--season", action="append", default=[], help="a season (the year it starts in) to add active; repeatable")
    parser.add_argument("--paused", action="append", default=[], help="a season to add paused; repeatable")
    parser.add_argument("--catalogue", default=DEFAULT_CATALOGUE)
    parser.add_argument("--combos", help="read the combos from this file (the answer of the site saved before) instead of asking the site")
    args = parser.parse_args(argv)
    seasons = {**{s: False for s in args.paused}, **{s: True for s in args.season}}
    if not seasons:
        parser.error("give at least one --season or --paused")
    if args.combos:
        combos = json.loads(open(args.combos, encoding="utf-8").read())
    else:
        from src.scraper.fbcyl_scraper import FBCYLWebScraper
        from src.scraper.web_client import WebClient

        scraper = FBCYLWebScraper(WebClient())
        combos = [c for season in seasons for c in fetch_combos(scraper, season)]
    report = update_catalogue_file(args.catalogue, combos, seasons)
    print(f"{report['added']} groups added ({report['paused_added']} paused)")
    for text in report["unknown"]:
        print(f"unknown category, left out: {text}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
