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

from src.external.refresh import DEFAULT_WINDOW_DAYS, refresh_source
from src.services.competition_catalogue import DEFAULT_CATALOGUE, EXTERNAL_LEAGUES, external_entries, load_catalogue


def _database(db: Any = None) -> Any:
    if db is not None:
        return db
    from pymongo import MongoClient

    return MongoClient(os.environ["MONGODB_CONNECTION_STRING"])[os.environ.get("MONGODB_DATABASE", "BASKETBALL")]


def main(argv: Optional[List[str]] = None, db: Any = None, now: Optional[datetime] = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh an external source into its own archive")
    parser.add_argument("--catalogue", default=DEFAULT_CATALOGUE)
    parser.add_argument("--out", default="archive-ext")
    parser.add_argument("--source", choices=EXTERNAL_LEAGUES)
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    parser.add_argument("--list-sources", action="store_true", help="print the sources with an active competition, as JSON, and exit")
    args = parser.parse_args(argv)
    catalogue = load_catalogue(args.catalogue)
    if args.list_sources:
        print(json.dumps(sorted({e["league"] for e in external_entries(catalogue)})))
        return 0
    if not args.source:
        parser.error("--source is required (or --list-sources)")
    status = refresh_source(args.source, catalogue, _database(db), Path(args.out), now or datetime.now(timezone.utc), args.window_days)
    print(json.dumps(status, ensure_ascii=False, indent=1))
    return 1 if status["ok"] is False else 0


if __name__ == "__main__":
    sys.exit(main())
