"""Incremental FEB ingestion of one competition group (shared by the scrape API and the Atlas refresh job)."""

from __future__ import annotations

import gc
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from src.services.refresh_state import load_state, record_failure, record_success, save_state, should_ask
from src.utils.time_utils import utc_now_naive

FEB_STATUS_FINISHED = "3"


# A game cannot be live 8 hours after it started. FEB sometimes never marks a played game as finished (match 2537218 of 3a FEB, played on 11-10-2026, still shows
# status 1, «SCHEDULED», with its four quarters filled in): the rule "not finished means in progress" skipped it in every refresh and the refresh went red every time
# (issue #724). Past ``STALE_AFTER`` from its start, a game whose score of the four quarters is in is assumed finished.
STALE_AFTER = timedelta(hours=8)
QUARTERS_PLAYED = 4


def _four_quarters_filled(doc: Dict[str, Any]) -> bool:
    """``HEADER.QUARTERS.QUARTER`` has at least four quarters, each with the two scores (``scoreA``, ``scoreB``) as numbers; an overtime adds quarters, never removes."""
    quarters = (((doc or {}).get("HEADER") or {}).get("QUARTERS") or {}).get("QUARTER") or []
    filled = 0
    for quarter in quarters:
        try:
            int(quarter.get("scoreA"))
            int(quarter.get("scoreB"))
        except (AttributeError, TypeError, ValueError):
            continue
        filled += 1
    return filled >= QUARTERS_PLAYED


def is_in_progress(doc: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    """True when a FEB doc carries a status other than FINISHED ('3') and may still be played.

    Docs without ``HEADER.status`` (older data) are treated as finished. A game that started more than ``STALE_AFTER`` ago with its four quarters filled in is not in
    progress whatever status FEB shows: it is stored as it is, and a refresh of the last days replaces it if FEB corrects it.
    """
    status = (doc.get("HEADER") or {}).get("status")
    if status is None or str(status) == FEB_STATUS_FINISHED:
        return False
    played = _played(doc)
    if played is not None and _four_quarters_filled(doc) and (now or utc_now_naive()) - played > STALE_AFTER:
        return False
    return True


_CORRECTABLE = ("HEADER", "BOXSCORE", "PLAYBYPLAY", "SHOTCHART")


def _played(doc: Dict[str, Any]) -> Optional[datetime]:
    """When a game was played (``HEADER.starttime``, ``dd-mm-yyyy - hh:mm``), or ``None`` if it cannot be read."""
    try:
        return datetime.strptime(((doc or {}).get("HEADER") or {}).get("starttime") or "", "%d-%m-%Y - %H:%M")
    except ValueError:
        return None


def _recheck(job: Dict[str, Any], db: Any, scraper: Any, session: Any, collection_name: str, code: str, since: datetime) -> None:
    """A stored game inside the window of rechecks (#646): download it again and replace it if FEB corrected it. What is stored is never lost: a
    download that fails, comes empty or is unfinished leaves it as it is."""
    stored = db.get_match_for_recheck(collection_name, int(code))
    played = _played(stored)
    if played is None or played < since:
        job["skipped"] += 1
        return
    job["rechecked"] += 1
    doc = scraper.fetch_boxscore(code, session)
    if not doc or is_in_progress(doc):
        job["skipped"] += 1
    elif any(doc.get(k) != stored.get(k) for k in _CORRECTABLE):
        if db.replace_boxscore(collection_name, code, doc):
            job["corrected"] += 1
        else:
            job["errors"].append(f"Match {code}: could not replace the stored game")
    else:
        job["skipped"] += 1


def store_feb_match(job: Dict[str, Any], db: Any, scraper: Any, session: Any, collection_name: str, code: str,
                    recheck_since: Optional[datetime] = None, state: Optional[Dict[str, Any]] = None, today: Optional[date] = None) -> None:
    """Fetch and store a single FEB match; update job counters. With ``recheck_since`` a stored game played since then is downloaded again and
    replaced if it changed (late corrections of FEB, issue #646). With ``state`` (the refresh state of the collection, #924) a match that keeps failing stops being asked: after
    20 failures over a week it is «unavailable» (``job["unavailable"]``, not an error) and asked once a month."""
    job["current_match"] = code
    today = today or utc_now_naive().date()
    try:
        if db.document_exists(collection_name, int(code)):
            if recheck_since is None:
                job["skipped"] += 1
            else:
                _recheck(job, db, scraper, session, collection_name, code, recheck_since)
            return
        if state is not None and not should_ask(state, code, today):
            job.setdefault("unavailable", []).append(code)
            return
        doc = scraper.fetch_boxscore(code, session)
        if doc and is_in_progress(doc):
            # Storing a partial game would block the final one (document_exists).
            job["skipped"] += 1
        elif doc:
            db.insert_boxscore(collection_name, code, doc)
            if state is not None:
                record_success(state, code)
        else:
            job["errors"].append(f"No data for match {code}")
            if state is not None:
                record_failure(state, code, "No data", today)
    except Exception as exc:
        job["errors"].append(f"Match {code}: {exc}")
        if state is not None:
            record_failure(state, code, str(exc), today)
    finally:
        job["done"] += 1


def save_collection_meta(db: Any, collection_name: str, params: Any) -> None:
    """Remember the calendar URL/selection of the collection (used by the live match list)."""
    try:
        from src.services.collection_meta import save_feb_meta

        save_feb_meta(db, collection_name, params)
    except Exception:  # noqa: BLE001 - metadata is optional, never fail the scrape for it
        pass


def scrape_feb_collection(db: Any, params: Any, scraper: Optional[Any] = None,
                          job: Optional[Dict[str, Any]] = None, now: Optional[datetime] = None, today: Optional[date] = None) -> Dict[str, Any]:
    """Download every match of the selection that is not stored yet; returns the (given) job dict. When ``params.recheck_days`` is set, the stored
    games played in the last days are downloaded again and replaced if FEB corrected them (``rechecked`` and ``corrected`` count them).

    Raises on discovery failures; per-match failures are collected in ``job["errors"]``.
    """
    from src.database import get_collection_name

    if scraper is None:
        from src.scraper import FEBWebScraper

        scraper = FEBWebScraper()
    job = job if job is not None else {}
    job.setdefault("done", 0)
    job.setdefault("skipped", 0)
    job.setdefault("errors", [])
    job.setdefault("rechecked", 0)
    job.setdefault("corrected", 0)
    job.setdefault("unavailable", [])
    collection_name = get_collection_name(params.competition_label, params.season_label, params.group_label)
    job["collection"] = collection_name
    save_collection_meta(db, collection_name, params)

    job["status"] = "discovering"
    _, session = scraper.get_page_content(params.year)
    match_codes = scraper.get_matches(params.season_value, params.group_value, params.year, session,
                                      url=params.competition_url)
    job["total"] = len(match_codes)
    job["status"] = "running"
    days = getattr(params, "recheck_days", 0) or 0
    since = (now or utc_now_naive()) - timedelta(days=days) if days else None
    state = load_state(db, collection_name)
    today = today or (now or utc_now_naive()).date()
    for code in match_codes:
        store_feb_match(job, db, scraper, session, collection_name, code, since, state, today)
        if job["done"] % 10 == 0:
            gc.collect()
    save_state(db, collection_name, state)
    job["status"] = "done"
    job["current_match"] = None
    return job
