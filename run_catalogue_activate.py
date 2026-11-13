"""Turn on a batch of seasons of the catalogue (#876): ``active: true`` on the paused history and youth entries, a few seasons at a time.

    python run_catalogue_activate.py --season 2023 --season 2022 --exclude "TERCERA FEB"      # batch 1 of the FEB history
    python run_catalogue_activate.py --season 2025 --only "TERCERA FEB"                       # Tercera FEB has its own batches
    python run_catalogue_activate.py --season 2025 --league fbcyl                              # a paused FBCYL season

Never touches the current season, what is already active or other leagues; running it twice changes nothing. Then wait for a refresh to load the batch (docs/OPERATIONS.md).
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from src.services.catalogue_batches import activate_seasons  # noqa: E402
from src.services.competition_catalogue import DEFAULT_CATALOGUE  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--season", action="append", required=True, help="a season (the year it starts in); repeatable")
    parser.add_argument("--league", default="feb", choices=("feb", "fbcyl"))
    parser.add_argument("--only", action="append", help="only this competition; repeatable")
    parser.add_argument("--exclude", action="append", help="leave this competition out; repeatable")
    parser.add_argument("--catalogue", default=DEFAULT_CATALOGUE)
    args = parser.parse_args(argv)
    report = activate_seasons(args.catalogue, args.season, league=args.league, only=args.only, exclude=args.exclude)
    print(f"{report['activated']} entries activated: {report['by_season'] or 'nothing to do'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
