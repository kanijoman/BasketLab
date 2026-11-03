"""Incremental FBCYL ingestion of one competition group (issue #724): shared by the scrape API and by the refresh job, as ``feb_match_ingest`` is for FEB.

FBCYL has no calendar to compare with and a finished game never changes, so the scrape only downloads the matches that are not stored yet.
"""
from __future__ import annotations

import gc
from typing import Any, Dict, Optional


def store_fbcyl_match(job: Dict[str, Any], db: Any, scraper: Any, collection_name: str, uuid: str, league_ctx: Dict[str, str]) -> None:
    """Fetch and store a single FBCYL match; update the job counters."""
    job["current_match"] = uuid
    try:
        if db.document_exists(collection_name, uuid):
            job["skipped"] += 1
            return
        doc = scraper.get_match_complete_data(uuid, league_ctx=league_ctx)
        if doc:
            db.insert_fbcyl_match(collection_name, uuid, doc)
        else:
            job["errors"].append(f"No data for match {uuid}")
    except Exception as exc:  # noqa: BLE001 - one match must not stop the group
        job["errors"].append(f"Match {uuid}: {exc}")
    finally:
        job["done"] += 1


def scrape_fbcyl_collection(db: Any, params: Dict[str, str], scraper: Optional[Any] = None, job: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
    collection_name = get_collection_name(f"FBCYL_{params['competition_label']}", params["season"], "")
    job["collection"] = collection_name
    league_ctx = {"gender": params.get("gender", ""), "territory": params.get("territory", "0"), "category": params["category"],
                  "competition_id": params["competition_id"], "season": params["season"]}
    job["status"] = "discovering"
    match_uuids = scraper.get_matches(params["competition_id"])
    job["total"] = len(match_uuids)
    job["status"] = "running"
    for uuid in match_uuids:
        store_fbcyl_match(job, db, scraper, collection_name, uuid, league_ctx)
        if job["done"] % 10 == 0:
            gc.collect()
    return job
