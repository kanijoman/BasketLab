"""Keep the production database (Atlas) up to date with FEB (issue #177).

``python run_atlas_refresh.py`` scrapes every competition listed in ``config/atlas_refresh.json``
(incremental: only matches that are finished and not stored yet), then compares each collection with FEB's
calendar. Exit code 1 when a competition failed or still lacks played matches, 2 when the connection
string is missing. Runs on a schedule in ``.github/workflows/atlas-refresh.yml``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

DEFAULT_CONFIG = "config/atlas_refresh.json"


@dataclass
class RefreshEntry:
    """One FEB competition group to keep fresh (same fields as the scrape API's ``FEBScrapeParams``)."""

    competition_url: str
    season_value: str
    group_value: str
    competition_label: str
    season_label: str
    group_label: str
    year: str = "2025"


def load_config(path: Any = DEFAULT_CONFIG) -> List[RefreshEntry]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    names = {f.name for f in fields(RefreshEntry)}
    required = [n for n in names if n != "year"]
    entries = []
    for i, raw in enumerate(data.get("scrapes", []), start=1):
        missing = [k for k in required if not raw.get(k)]
        if missing:
            raise ValueError(f"scrapes entry #{i} lacks: {', '.join(sorted(missing))}")
        entries.append(RefreshEntry(**{k: v for k, v in raw.items() if k in names}))
    return entries


def refresh_all(db: Any, entries: List[RefreshEntry], scraper: Optional[Any] = None,
                freshness: Optional[Callable[[str], Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    from src.services.data_freshness_service import DataFreshnessService
    from src.services.feb_match_ingest import scrape_feb_collection

    check = freshness or DataFreshnessService(db).check
    report = []
    for entry in entries:
        label = f"{entry.competition_label}/{entry.season_label}/{entry.group_label}"
        item: Dict[str, Any] = {"collection": label, "fatal": None, "job": None, "freshness": None}
        try:
            job = scrape_feb_collection(db, entry, scraper)
            item.update(collection=job["collection"], job=job)
            item["freshness"] = check(job["collection"])
        except Exception as exc:  # noqa: BLE001 - one failing competition must not block the others
            item["fatal"] = f"{type(exc).__name__}: {exc}"
        report.append(item)
    return report


def needs_attention(report: List[Dict[str, Any]]) -> bool:
    return any(r["fatal"] or (r["freshness"] or {}).get("up_to_date") is False for r in report)


def to_markdown(report: List[Dict[str, Any]]) -> str:
    out = ["# Refresco de Atlas", ""]
    for r in report:
        out.append(f"## {r['collection']}")
        if r["fatal"]:
            out.append(f"- **Error**: {r['fatal']}")
            continue
        job, fresh = r["job"], r["freshness"] or {}
        stored = job["done"] - job["skipped"] - len(job["errors"])
        out.append(f"- Partidos en FEB: {job['total']} · nuevos guardados: {stored} · ya existentes o en juego: "
                   f"{job['skipped']} · errores: {len(job['errors'])}")
        out.append(f"- En la base de datos: {fresh.get('games_in_db')} · último partido: {fresh.get('last_game')}")
        if fresh.get("up_to_date") is False:
            out.append(f"- **Faltan {len(fresh['missing_codes'])} partidos jugados**: {', '.join(fresh['missing_codes'])}")
        elif fresh.get("warning"):
            out.append(f"- Aviso: {fresh['warning']}")
        else:
            out.append("- Al día con el calendario de FEB")
        out.extend(f"  - {e}" for e in job["errors"][:10])
    return "\n".join(out)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh the database from FEB")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--require-env", action="store_true", help="fail unless MONGODB_CONNECTION_STRING is set (CI)")
    args = parser.parse_args(argv)
    if args.require_env and not os.environ.get("MONGODB_CONNECTION_STRING"):
        print("MONGODB_CONNECTION_STRING is not set (GitHub secret ATLAS_WRITE_URI)", file=sys.stderr)
        return 2
    entries = load_config(args.config)
    from src.database import MongoDBHandler

    db = MongoDBHandler()
    if not db.is_connected():
        print("No se pudo conectar a la base de datos", file=sys.stderr)
        return 2
    report = refresh_all(db, entries)
    text = to_markdown(report)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 1 if needs_attention(report) else 0

