"""Incremental FBCYL ingestion of one competition group (issue #724): shared by the scrape API and by the refresh job, as ``feb_match_ingest`` is for FEB.

FBCYL has no calendar to compare with and a finished game never changes, so the scrape only downloads the matches that are not stored yet.
"""
from __future__ import annotations

import gc
from datetime import date
from typing import Any, Dict, Optional

from src.services.refresh_state import load_state, record_failure, record_success, save_state, should_ask
from src.utils.time_utils import utc_now_naive


def store_fbcyl_match(job: Dict[str, Any], db: Any, scraper: Any, collection_name: str, uuid: str, league_ctx: Dict[str, str],
                      state: Optional[Dict[str, Any]] = None, today: Optional[date] = None) -> None:
    """Fetch and store a single FBCYL match; update the job counters. A match that keeps failing (the site answers 500 for some) stops being asked after 20 failures over a week (#924)."""
    job["current_match"] = uuid
    today = today or utc_now_naive().date()
    try:
        if db.document_exists(collection_name, uuid):
            job["skipped"] += 1
            return
        if state is not None and not should_ask(state, uuid, today):
            job.setdefault("unavailable", []).append(uuid)
            return
        doc = scraper.get_match_complete_data(uuid, league_ctx=league_ctx)
        if doc:
            db.insert_fbcyl_match(collection_name, uuid, doc)
            if state is not None:
                record_success(state, uuid)
        else:
            job["errors"].append(f"No data for match {uuid}")
            if state is not None:
                record_failure(state, uuid, "No data", today)
    except Exception as exc:  # noqa: BLE001 - one match must not stop the group
        job["errors"].append(f"Match {uuid}: {exc}")
        if state is not None:
            record_failure(state, uuid, str(exc), today)
    finally:
        job["done"] += 1


def scrape_fbcyl_collection(db: Any, params: Dict[str, str], scraper: Optional[Any] = None, job: Optional[Dict[str, Any]] = None, today: Optional[date] = None) -> Dict[str, Any]:
    """Download every match of the group that is not stored yet; returns the (given) job dict.

    ``params``: ``competition_id`` (the group), ``season``, ``gender``, ``territory``, ``category`` and ``competition_label`` (which names the collection).
    Raises on discovery failures; per-match failures are collected in ``job["errors"]``.
    """
    from src.database import get_collection_name

    if scraper is None:
        from src.scraper.fbcyl_scraper import FBCYLWebScraper
        from src.scraper.web_client import WebClient

        scraper = FBCYLWebScraper(WebClient())
    job = job if job is not None else {}
    job.setdefault("done", 0)
    job.setdefault("skipped", 0)
    job.setdefault("errors", [])
    job.setdefault("unavailable", [])
    collection_name = get_collection_name(f"FBCYL_{params['competition_label']}", params["season"], "")
    job["collection"] = collection_name
    league_ctx = {"gender": params.get("gender", ""), "territory": params.get("territory", "0"), "category": params["category"],
                  "competition_id": params["competition_id"], "season": params["season"]}
    job["status"] = "discovering"
    match_uuids = scraper.get_matches(params["competition_id"])
    job["total"] = len(match_uuids)
    job["status"] = "running"
    state = load_state(db, collection_name)
    today = today or utc_now_naive().date()
    for uuid in match_uuids:
        store_fbcyl_match(job, db, scraper, collection_name, uuid, league_ctx, state, today)
        if job["done"] % 10 == 0:
            gc.collect()
    save_state(db, collection_name, state)
    return job
