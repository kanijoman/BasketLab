"""Keep the production database (Atlas) up to date with FEB (issue #177).

``python run_refresh.py`` scrapes every active competition of the catalogue ``config/competitions.json``
(incremental: only matches that are finished and not stored yet), then compares each collection with FEB's
calendar. Exit code 1 when a competition failed or still lacks played matches (a match that FEB has answered "no data" for more than a week is information, not a problem: #902), 2 when the connection
string is missing. Runs on a schedule in ``.github/workflows/archive-refresh.yml`` over the archive restored into an ephemeral Mongo.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, fields, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.services.refresh_state import (CLOSED_AFTER_DAYS, MAX_ATTEMPTS, MIN_DAYS_BEFORE_UNAVAILABLE, RECHECK_CLOSED_EVERY_DAYS, REVIEW_UNAVAILABLE_EVERY_DAYS, is_closed, load_state,
                                        record_check, save_state)

DEFAULT_CONFIG = "config/competitions.json"


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
    recheck_days: int = 0                                            # >0: stored games of the last N days are downloaded again and replaced if FEB corrected them (#646)
    league: str = "feb"                                              # "fbcyl": a FBCYL group of the catalogue of competitions (#724): scraped by ``fbcyl_match_ingest``, no calendar to compare with
    fbcyl: Dict[str, str] = field(default_factory=dict)              # its ``competition_id``, ``category``, ``gender`` and ``territory``


def load_config(path: Any = DEFAULT_CONFIG) -> List[RefreshEntry]:
    """The entries to scrape of a refresh config (``scrapes``, the old format of the refresh config) or of the catalogue of competitions (``competitions``: the active ones, issue #724)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "competitions" in data:
        from src.services.competition_catalogue import load_catalogue, refresh_entries

        return refresh_entries(load_catalogue(path))
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
    days = raw.get("recheck_days", 0)
    if isinstance(days, bool) or not isinstance(days, int) or days < 0:
        raise ValueError(f"scrapes entry #{position}: recheck_days must be a whole number of days, 0 or more, not {days!r}")
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


LEAGUES = ("feb", "fbcyl")


def select_entries(entries: List[RefreshEntry], names: List[str], seasons: List[str], league: Optional[str]) -> List[RefreshEntry]:
    """The entries of a partial refresh (#924): by competition (``only_competitions``), by season (the year it starts in) and by league, all of them together.

    Every season asked for must have at least one entry with the other filters (a typo, or a season that is not loaded, is an error naming it, not an empty refresh)."""
    if league is not None and league not in LEAGUES:
        raise ValueError(f"unknown league: {league} (one of {', '.join(LEAGUES)})")
    chosen = only_competitions(entries, names)
    if league:
        chosen = [e for e in chosen if e.league == league]
    if seasons:
        wanted = [str(s) for s in seasons]
        lacking = [s for s in wanted if not any(str(e.season_value) == s for e in chosen)]
        if lacking:
            raise ValueError(f"no entries of season {', '.join(lacking)} with those filters")
        chosen = [e for e in chosen if str(e.season_value) in wanted]
    if not chosen:
        raise ValueError("nothing to refresh with those filters")
    return chosen


def ingested_collections(db: Optional[Any], entries: List[RefreshEntry]) -> List[str]:
    """Collection names of ``entries``; the phases of a ``groups: all`` competition are the ones the refresh already stored.

    Reads ``COLLECTION_META`` instead of FEB so that consumers (live packages) work offline.
    """
    from src.database import get_collection_name

    meta = db.repository.connection.get_collection("COLLECTION_META") if db is not None else None
    names: List[str] = []
    for entry in entries:
        if entry.league == "fbcyl":
            continue                                                 # live packages are FEB only
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


def _fill_derived(db: Any, collection: str) -> None:
    """``DERIVED`` of the games of the collection that lack it (issue #630): the Atlas workflow ran this as a second step, the local refresh did not and left games out of the
    pbp tables. Idempotent (a game that has the current version is skipped); it never turns a refresh into an error."""
    try:
        from src.services.derived_backfill import backfill_collection
        from src.services.collection_service import CollectionService

        backfill_collection(db.repository.connection.get_collection(collection), fbcyl=bool(CollectionService._FBCYL_PREFIX.match(collection)))
    except Exception:  # noqa: BLE001 - the next refresh (or run_backfill_derived.py) retries it
        pass


NO_DATA_AFTER = timedelta(days=7)
_NO_DATA = "No data for match "
_FORFEIT_SCORES = frozenset({"0-2", "2-0"})              # a basketball game cannot end like this: it is the default score of a forfeit, and nobody plays it, so no boxscore will ever exist


def forgive_no_data(fresh: Dict[str, Any], job: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    """#902: FEB lists matches that have no boxscore for ever (youth championships: not played, no report) and the run stayed red on every refresh, hiding real failures. A missing
    match goes to ``no_data_codes`` when this scrape asked FEB for it and got "no data" AND either the calendar shows a FORFEIT score for it (0-2 or 2-0: found in the first scheduled refresh
    after #902, where the two matches that kept the run red were forfeits with no date) or it dates the match more than ``NO_DATA_AFTER`` ago (the boxscore of yesterday's match may just
    not be up yet). Anything else, an undated match with a real score or one missing for another reason (a network error, never asked), stays missing. It is asked again on every run."""
    asked = {e[len(_NO_DATA):] for e in job["errors"] if e.startswith(_NO_DATA)}
    since = fresh.get("missing_since") or {}
    score = fresh.get("missing_score") or {}
    quiet = [c for c in fresh.get("missing_codes") or []
             if c in asked and (score.get(c) in _FORFEIT_SCORES or (since.get(c) and now - datetime.fromisoformat(since[c]) > NO_DATA_AFTER))]
    gone = [c for c in fresh.get("missing_codes") or [] if c in set(job.get("unavailable") or [])]      # #924: failed 20 times over a week: no longer a hole, listed apart
    if not quiet and not gone:
        return fresh
    missing = [c for c in fresh["missing_codes"] if c not in quiet and c not in gone]
    return {**fresh, "missing_codes": missing, "no_data_codes": quiet, "up_to_date": not missing}


def _closed_item(name: str) -> Dict[str, Any]:
    return {"collection": name, "closed": True, "fatal": None, "job": None, "freshness": None}


def _refresh_one(db: Any, entry: RefreshEntry, scraper: Optional[Any], check: Callable[[str], Dict[str, Any]], now: Callable[[], datetime], force: bool = False) -> Dict[str, Any]:
    from src.database import get_collection_name
    from src.services.feb_match_ingest import scrape_feb_collection

    today = now().date()
    name = get_collection_name(entry.competition_label, entry.season_label, entry.group_label)
    if not force and is_closed(load_state(db, name), today):
        return _closed_item(name)                                                 # nothing can have changed: no request at all (#924)
    label = f"{entry.competition_label}/{entry.season_label}/{entry.group_label}"
    item: Dict[str, Any] = {"collection": label, "fatal": None, "job": None, "freshness": None}
    try:
        job = scrape_feb_collection(db, entry, scraper, today=today)
        item.update(collection=job["collection"], job=job)
        _ensure_team_index(db, job["collection"])
        _fill_derived(db, job["collection"])
        item["freshness"] = forgive_no_data(check(job["collection"]), job, now())
        state = load_state(db, job["collection"])
        record_check(state, item["freshness"].get("up_to_date"), item["freshness"].get("last_game"), today)
        save_state(db, job["collection"], state)
    except Exception as exc:  # noqa: BLE001 - one failing competition must not block the others
        item["fatal"] = f"{type(exc).__name__}: {exc}"
    return item


def _refresh_fbcyl(db: Any, entry: RefreshEntry, scraper: Optional[Any], today: Optional[Any] = None) -> Dict[str, Any]:
    """One FBCYL group: the matches not stored yet and the ``DERIVED`` of what came in. There is no calendar to compare with and the team index is of the FEB header."""
    from src.services.fbcyl_match_ingest import scrape_fbcyl_collection

    item: Dict[str, Any] = {"collection": f"{entry.competition_label}/{entry.season_label}", "league": "fbcyl", "fatal": None, "job": None, "freshness": None}
    try:
        params = {**entry.fbcyl, "season": entry.season_value, "competition_label": entry.competition_label}
        job = scrape_fbcyl_collection(db, params, scraper, today=today)
        item.update(collection=job["collection"], job=job)
        _fill_derived(db, job["collection"])
    except Exception as exc:  # noqa: BLE001 - one failing group must not block the others
        item["fatal"] = f"{type(exc).__name__}: {exc}"
    return item


def refresh_all(db: Any, entries: List[RefreshEntry], scraper: Optional[Any] = None,
                freshness: Optional[Callable[[str], Dict[str, Any]]] = None, fbcyl_scraper: Optional[Any] = None,
                now: Optional[Callable[[], datetime]] = None, force: bool = False) -> List[Dict[str, Any]]:
    from src.services.data_freshness_service import DataFreshnessService
    from src.services.match_schedule_service import _madrid_now

    check = freshness or DataFreshnessService(db).check
    now = now or _madrid_now
    report = []
    today = now().date()
    for entry in entries:
        if entry.league == "fbcyl":
            report.append(_refresh_fbcyl(db, entry, fbcyl_scraper, today))
            continue
        if not force:
            known = ingested_collections(db, [entry])
            if known and all(is_closed(load_state(db, n), today) for n in known):
                report.extend(_closed_item(n) for n in known)              # every phase closed: not even discovered in FEB (a new phase shows up when the week is over)
                continue
        try:
            concrete = expand_entries([entry], scraper)
        except Exception as exc:  # noqa: BLE001 - a failed discovery is that competition's error only
            report.append({"collection": f"{entry.competition_label}/{entry.season_label}", "fatal": f"{type(exc).__name__}: {exc}",
                           "job": None, "freshness": None})
            continue
        report.extend(_refresh_one(db, e, scraper, check, now, force) for e in concrete)
    return report


def needs_attention(report: List[Dict[str, Any]]) -> bool:
    return any(r["fatal"] or (r["freshness"] or {}).get("up_to_date") is False for r in report)


def to_markdown(report: List[Dict[str, Any]]) -> str:
    out = ["# Refresco de Atlas", ""]
    closed = [r["collection"] for r in report if r.get("closed")]
    if closed:
        shown = ", ".join(closed[:10]) + (f" y {len(closed) - 10} más" if len(closed) > 10 else "")
        out += [f"## Colecciones cerradas: {len(closed)}", f"- Sin comprobar este refresco (último partido de hace más de {CLOSED_AFTER_DAYS} días y al día; se comprueban cada {RECHECK_CLOSED_EVERY_DAYS} días): {shown}", ""]
    for r in report:
        if r.get("closed"):
            continue
        out.append(f"## {r['collection']}")
        if r["fatal"]:
            out.append(f"- **Error**: {r['fatal']}")
            continue
        job, fresh = r["job"], r["freshness"] or {}
        stored = job["done"] - job["skipped"] - len(job["errors"])
        source = "FBCYL" if r.get("league") == "fbcyl" else "FEB"
        out.append(f"- Partidos en {source}: {job['total']} · nuevos guardados: {stored} · ya existentes o en juego: "
                   f"{job['skipped']} · errores: {len(job['errors'])}")
        if job.get("unavailable"):
            out.append(f"- No disponibles (fallaron {MAX_ATTEMPTS} veces en al menos {MIN_DAYS_BEFORE_UNAVAILABLE} días; se piden una vez cada {REVIEW_UNAVAILABLE_EVERY_DAYS} días): {', '.join(job['unavailable'])}")
        if source == "FBCYL":
            out.extend(f"  - {e}" for e in job["errors"][:10])
            continue                                              # FBCYL has no calendar to compare with
        if job.get("rechecked"):
            out.append(f"- Revisados de nuevo (últimos días): {job['rechecked']} · corregidos: {job.get('corrected', 0)}")
        out.append(f"- En la base de datos: {fresh.get('games_in_db')} · último partido: {fresh.get('last_game')}")
        if fresh.get("up_to_date") is False:
            out.append(f"- **Faltan {len(fresh['missing_codes'])} partidos jugados**: {', '.join(fresh['missing_codes'])}")
        elif fresh.get("warning"):
            out.append(f"- Aviso: {fresh['warning']}")
        else:
            out.append("- Al día con el calendario de FEB")
        if fresh.get("no_data_codes"):
            out.append(f"- Sin datos en FEB (incomparecencias o más de {NO_DATA_AFTER.days} días; se vuelven a pedir en cada refresco): {', '.join(fresh['no_data_codes'])}")
        out.extend(f"  - {e}" for e in job["errors"][:10])
    return "\n".join(out)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh the database from FEB")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--only", action="append", default=[], metavar="COMPETITION",
                        help="refresh only this competition (repeatable; comma separated also works), e.g. 'tercera feb'")
    parser.add_argument("--season", action="append", default=[], metavar="YEAR",
                        help="refresh only this season, the year it starts in (repeatable; comma separated also works), e.g. 2025")
    parser.add_argument("--league", choices=LEAGUES, help="refresh only this league")
    parser.add_argument("--force-check", action="store_true", help="check the closed collections too (by default a collection whose last game is over 14 days old and was up to date is checked every 7 days)")
    parser.add_argument("--require-env", action="store_true", help="fail unless MONGODB_CONNECTION_STRING is set (CI)")
    args = parser.parse_args(argv)
    if args.require_env and not os.environ.get("MONGODB_CONNECTION_STRING"):
        print("MONGODB_CONNECTION_STRING is not set (the workflow restores the archive into an ephemeral Mongo and sets it)", file=sys.stderr)
        return 2
    try:
        entries = select_entries(load_config(args.config), [n.strip() for a in args.only for n in a.split(",") if n.strip()],
                                 [s.strip() for a in args.season for s in a.split(",") if s.strip()], args.league)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    from src.database import MongoDBHandler

    db = MongoDBHandler()
    if not db.is_connected():
        print("No se pudo conectar a la base de datos", file=sys.stderr)
        return 2
    report = refresh_all(db, entries, force=args.force_check)
    text = to_markdown(report)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 1 if needs_attention(report) else 0

