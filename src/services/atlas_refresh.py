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
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

DEFAULT_CONFIG = "config/atlas_refresh.json"


ALL_GROUPS = "all"


@dataclass
class RefreshEntry:
    """One FEB competition group to keep fresh (same fields as the scrape API's ``FEBScrapeParams``).

    ``groups == "all"`` makes it a whole competition instead: no group fields, its groups (phases, play-offs
    included) are discovered from FEB on each run (``expand_entries``), optionally narrowed by ``group_filter``.
    """

    competition_url: str
    season_value: str
    competition_label: str
    season_label: str
    group_value: str = ""
    group_label: str = ""
    year: str = "2025"
    groups: str = ""
    group_filter: List[str] = field(default_factory=list)


def load_config(path: Any = DEFAULT_CONFIG) -> List[RefreshEntry]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    names = {f.name for f in fields(RefreshEntry)}
    entries = []
    for i, raw in enumerate(data.get("scrapes", []), start=1):
        entries.append(_parse_entry(i, raw, names))
    return entries


def _parse_entry(position: int, raw: Dict[str, Any], names: Any) -> RefreshEntry:
    whole = raw.get("groups")
    if whole not in (None, "", ALL_GROUPS):
        raise ValueError(f"scrapes entry #{position}: groups must be \"{ALL_GROUPS}\", not {whole!r}")
    group_fields = ("group_value", "group_label")
    if whole == ALL_GROUPS and any(raw.get(k) for k in group_fields):
        raise ValueError(f"scrapes entry #{position}: groups \"{ALL_GROUPS}\" excludes {' and '.join(group_fields)}")
    required = ["competition_url", "season_value", "competition_label", "season_label"]
    required += [] if whole == ALL_GROUPS else list(group_fields)
    missing = [k for k in required if not raw.get(k)]
    if missing:
        raise ValueError(f"scrapes entry #{position} lacks: {', '.join(sorted(missing))}")
    return RefreshEntry(**{k: v for k, v in raw.items() if k in names})


def expand_entries(entries: List[RefreshEntry], scraper: Optional[Any] = None) -> List[RefreshEntry]:
    """Concrete groups of ``entries``: a ``groups: all`` competition becomes one entry per group FEB lists for its season.

    Raises when FEB lists none (a silent empty refresh would hide a broken page).
    """
    out: List[RefreshEntry] = []
    for entry in entries:
        if entry.groups != ALL_GROUPS:
            out.append(entry)
            continue
        if scraper is None:
            from src.scraper import FEBWebScraper

            scraper = FEBWebScraper()
        found = scraper.get_groups_for_season(entry.competition_url, entry.season_value)
        wanted = [f.lower() for f in entry.group_filter]
        found = [(label, value) for label, value in found if not wanted or any(w in label.lower() for w in wanted)]
        if not found:
            raise ValueError(f"FEB no lista grupos para {entry.competition_label} {entry.season_label}")
        out.extend(replace(entry, groups="", group_filter=[], group_label=label, group_value=value) for label, value in found)
    return out


def only_competitions(entries: List[RefreshEntry], names: List[str]) -> List[RefreshEntry]:
    """Entries of the competitions named (case, spaces and punctuation ignored: ``tercera feb`` = ``TERCERA FEB``, ``lf2`` = ``L.F.-2``).

    The first load of a competition is heavy (0,5 s per match), so it can be run on its own; no names = every entry.
    """
    if not names:
        return entries
    from src.scraper.schedule_client import normalize_name

    wanted = {normalize_name(n): n for n in names}
    known = {normalize_name(e.competition_label) for e in entries}
    unknown = [n for key, n in wanted.items() if key not in known]
    if unknown:
        raise ValueError(f"unknown competition: {', '.join(unknown)}")
    return [e for e in entries if normalize_name(e.competition_label) in wanted]


def ingested_collections(db: Optional[Any], entries: List[RefreshEntry]) -> List[str]:
    """Collection names of ``entries``; the phases of a ``groups: all`` competition are the ones the refresh already stored.

    Reads ``COLLECTION_META`` instead of FEB so that consumers (live packages) work offline.
    """
    from src.database import get_collection_name

    meta = db.repository.connection.get_collection("COLLECTION_META") if db is not None else None
    names: List[str] = []
    for entry in entries:
        if entry.groups != ALL_GROUPS:
            names.append(get_collection_name(entry.competition_label, entry.season_label, entry.group_label))
            continue
        if meta is None:
            continue
        wanted = [f.lower() for f in entry.group_filter]
        for doc in meta.find({"competition_url": entry.competition_url, "season_value": entry.season_value}):
            if not wanted or any(w in str(doc.get("group_label", "")).lower() for w in wanted):
                names.append(doc["_id"])
    return names


def _ensure_team_index(db: Any, collection: str) -> None:
    """``HEADER.TEAM.id`` of the games (issue #502): the packages read the games of a team in every collection of the season. Idempotent: it also covers the collections that already existed."""
    from src.database.indexes import IndexManager

    IndexManager(db.repository.connection).ensure_team_index(collection)


def _refresh_one(db: Any, entry: RefreshEntry, scraper: Optional[Any], check: Callable[[str], Dict[str, Any]]) -> Dict[str, Any]:
    from src.services.feb_match_ingest import scrape_feb_collection

    label = f"{entry.competition_label}/{entry.season_label}/{entry.group_label}"
    item: Dict[str, Any] = {"collection": label, "fatal": None, "job": None, "freshness": None}
    try:
        job = scrape_feb_collection(db, entry, scraper)
        item.update(collection=job["collection"], job=job)
        _ensure_team_index(db, job["collection"])
        item["freshness"] = check(job["collection"])
    except Exception as exc:  # noqa: BLE001 - one failing competition must not block the others
        item["fatal"] = f"{type(exc).__name__}: {exc}"
    return item


def refresh_all(db: Any, entries: List[RefreshEntry], scraper: Optional[Any] = None,
                freshness: Optional[Callable[[str], Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    from src.services.data_freshness_service import DataFreshnessService

    check = freshness or DataFreshnessService(db).check
    report = []
    for entry in entries:
        try:
            concrete = expand_entries([entry], scraper)
        except Exception as exc:  # noqa: BLE001 - a failed discovery is that competition's error only
            report.append({"collection": f"{entry.competition_label}/{entry.season_label}", "fatal": f"{type(exc).__name__}: {exc}",
                           "job": None, "freshness": None})
            continue
        report.extend(_refresh_one(db, e, scraper, check) for e in concrete)
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
    parser.add_argument("--only", action="append", default=[], metavar="COMPETITION",
                        help="refresh only this competition (repeatable; comma separated also works), e.g. 'tercera feb'")
    parser.add_argument("--require-env", action="store_true", help="fail unless MONGODB_CONNECTION_STRING is set (CI)")
    args = parser.parse_args(argv)
    if args.require_env and not os.environ.get("MONGODB_CONNECTION_STRING"):
        print("MONGODB_CONNECTION_STRING is not set (GitHub secret ATLAS_WRITE_URI)", file=sys.stderr)
        return 2
    try:
        entries = only_competitions(load_config(args.config), [n.strip() for a in args.only for n in a.split(",") if n.strip()])
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
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

