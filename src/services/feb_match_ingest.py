"""Incremental FEB ingestion of one competition group (shared by the scrape API and the Atlas refresh job)."""

from __future__ import annotations

import gc
from typing import Any, Dict, Optional

FEB_STATUS_FINISHED = "3"


def is_in_progress(doc: Dict[str, Any]) -> bool:
    """True when a FEB doc carries a status other than FINISHED ('3').

    Docs without ``HEADER.status`` (older data) are treated as finished.
    """
    status = (doc.get("HEADER") or {}).get("status")
    return status is not None and str(status) != FEB_STATUS_FINISHED


def store_feb_match(job: Dict[str, Any], db: Any, scraper: Any, session: Any, collection_name: str, code: str) -> None:
    """Fetch and store a single FEB match; update job counters."""
    job["current_match"] = code
    try:
        if db.document_exists(collection_name, int(code)):
            job["skipped"] += 1
            return
        doc = scraper.fetch_boxscore(code, session)
        if doc and is_in_progress(doc):
            # Storing a partial game would block the final one (document_exists).
            job["skipped"] += 1
        elif doc:
            db.insert_boxscore(collection_name, code, doc)
        else:
            job["errors"].append(f"No data for match {code}")
    except Exception as exc:
        job["errors"].append(f"Match {code}: {exc}")
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
                          job: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Download every match of the selection that is not stored yet; returns the (given) job dict.

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
    collection_name = get_collection_name(params.competition_label, params.season_label, params.group_label)
    job["collection"] = collection_name
    save_collection_meta(db, collection_name, params)

    job["status"] = "discovering"
    _, session = scraper.get_page_content(params.year)
    match_codes = scraper.get_matches(params.season_value, params.group_value, params.year, session,
                                      url=params.competition_url)
    job["total"] = len(match_codes)
    job["status"] = "running"
    for code in match_codes:
        store_feb_match(job, db, scraper, session, collection_name, code)
        if job["done"] % 10 == 0:
            gc.collect()
    job["status"] = "done"
    job["current_match"] = None
    return job
