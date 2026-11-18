"""Refresh one external source (ACB, FIBA, NCAA) into its own folder of the external archive (#884): ``python run_external_refresh.py --source ncaa --out archive-ext`` and, for the matrix of the workflow,
``python run_external_refresh.py --list-sources`` (the sources that have an active competition in ``config/competitions.json``: a new one gets its job without editing a list).

The job of a source is the only thing that writes ``<out>/<source>/`` (one writer per folder). It restores that archive into an ephemeral Mongo (``MONGODB_CONNECTION_STRING``), asks the registered source for
the games, validates and reconciles them and writes the archive back with its ``status.json``. Exit code: 0 when it worked and when the source has no scraper yet (``pending``), 1 when it failed (so the job
goes red and the workflow opens its issue); it never touches another source nor FEB's archive. See ``src/external/refresh.py`` and docs/OPERATIONS.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))                # as the other entry points: ``utils`` and the rest of ``src`` import each other by their short name

from src.external.refresh import DEFAULT_WINDOW_DAYS, refresh_source  # noqa: E402
from src.external.sources import register_defaults  # noqa: E402
from src.services.competition_catalogue import DEFAULT_CATALOGUE, EXTERNAL_LEAGUES, external_entries, load_catalogue  # noqa: E402


def _database(db: Any = None) -> Any:
    if db is not None:
        return db
    from pymongo import MongoClient

    return MongoClient(os.environ["MONGODB_CONNECTION_STRING"])[os.environ.get("MONGODB_DATABASE", "BASKETBALL")]


def _positive(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a whole number") from None
    if value < 1:
        raise argparse.ArgumentTypeError("the budget must be 1 or more")
    return value


def main(argv: Optional[List[str]] = None, db: Any = None, now: Optional[datetime] = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh an external source into its own archive")
    parser.add_argument("--catalogue", default=DEFAULT_CATALOGUE)
    parser.add_argument("--out", default="archive-ext")
    parser.add_argument("--source", choices=EXTERNAL_LEAGUES)
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    parser.add_argument("--budget", type=_positive, default=None, help="how many games a run may ask the source for (the default of the source when absent: 300 for FIBA, one request every 2 s)")
    parser.add_argument("--list-sources", action="store_true", help="print the sources with an active competition, as JSON, and exit")
    args = parser.parse_args(argv)
    catalogue = load_catalogue(args.catalogue)
    if args.list_sources:
        print(json.dumps(sorted({e["league"] for e in external_entries(catalogue)})))
        return 0
    if not args.source:
        parser.error("--source is required (or --list-sources)")
    register_defaults(args.source, args.budget)                         # the real source, unless one is already registered (the tests register their own)
    status = refresh_source(args.source, catalogue, _database(db), Path(args.out), now or datetime.now(timezone.utc), args.window_days)
    print(json.dumps(status, ensure_ascii=False, indent=1))
    return 1 if status["ok"] is False else 0


if __name__ == "__main__":
    sys.exit(main())
