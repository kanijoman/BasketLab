"""Scrape router — competition discovery and background data ingestion.

Discovery endpoints return dropdown data scraped live from the FEB/FBCYL
websites so the AdminPage can build its cascading selectors.

Ingestion endpoints accept the user's selection, kick off a background job
that downloads match data, and expose a polling endpoint for progress.

Job state is held in-process (module-level dict).  It resets on server
restart — acceptable for a PoC.  For production, replace with Redis/Celery.
"""

from __future__ import annotations

import gc
import os
import uuid as _uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from src.api.security import require_admin
from pydantic import BaseModel

router = APIRouter()

# ---------------------------------------------------------------------------
# Production guard — scraping is memory-intensive and disabled on free-tier
# cloud deployments.  Set DISABLE_SCRAPING=1 to block all ingestion endpoints
# while still allowing read-only analytics.
# ---------------------------------------------------------------------------
_SCRAPING_DISABLED = os.getenv("DISABLE_SCRAPING", "0") == "1"

def _require_scraping() -> None:
    if _SCRAPING_DISABLED:
        raise HTTPException(
            status_code=503,
            detail=(
                "El scraping está deshabilitado en este servidor. "
                "Ejecuta la descarga localmente con `python run_api.py` "
                "y sube los datos directamente a MongoDB Atlas."
            ),
        )

# ---------------------------------------------------------------------------
# In-process job store
# ---------------------------------------------------------------------------

SCRAPE_JOBS: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# FEB discovery
# ---------------------------------------------------------------------------

@router.get("/feb/competitions", summary="List FEB competitions from the web")
def feb_competitions() -> List[Dict[str, str]]:
    """Scrape ``competiciones.feb.es`` and return available competitions.

    Returns:
        List of ``{name, results_url}`` dicts.
    """
    from src.scraper import FEBWebScraper  # lazy import — avoids startup cost

    scraper = FEBWebScraper()
    try:
        return scraper.get_feb_competitions()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"FEB website unreachable: {exc}")


@router.get("/feb/seasons", summary="List seasons for a FEB competition URL")
def feb_seasons(url: str, year: str = "2025") -> List[Dict[str, str]]:
    """Fetch the calendar page and return season dropdown options.

    Loads ``url`` directly so the page state matches the competition the caller
    selected.  Falls back to the year-based BASE_URL when the GET fails.

    Args:
        url:  Competition calendar URL (e.g. ``https://baloncestoenvivo.feb.es/…``).
        year: Fallback year used to construct the URL if the direct GET fails.

    Returns:
        List of ``{text, value}`` dicts for the season dropdown.
    """
    from src.scraper import FEBWebScraper
    from bs4 import BeautifulSoup

    scraper = FEBWebScraper()
    try:
        response = scraper.web_client.get(url)
        if response is not None:
            soup = BeautifulSoup(response.content, "html.parser")
        else:
            soup, _ = scraper.web_scraper.get_page_content(year)
        seasons = scraper.get_seasons(soup)
        return [{"text": t, "value": v} for t, v in seasons]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not fetch seasons: {exc}")


@router.get("/feb/groups", summary="List groups for a FEB season")
def feb_groups(url: str, season: str, year: str = "2025") -> List[Dict[str, str]]:
    """Select the given season and return the group dropdown options.

    Delegates to ``get_groups_for_season`` which loads ``url`` directly so that
    the ASP.NET __VIEWSTATE is obtained from the same page as the POST target.
    Falls back to the year-based BASE_URL approach if the direct GET fails.

    Args:
        url:    Competition calendar URL.
        season: Season value from the season dropdown.
        year:   Fallback year used when the direct GET to ``url`` returns None.

    Returns:
        List of ``{text, value}`` dicts for the group dropdown.
    """
    from src.scraper import FEBWebScraper

    scraper = FEBWebScraper()
    try:
        groups = scraper.get_groups_for_season(url, season)
        if not groups:
            # Direct GET failed — fall back to the year-based page load
            soup, session = scraper.web_scraper.get_page_content(year)
            hidden = scraper.get_hidden_fields(soup)
            soup, _ = scraper.select_season(session, url, season, hidden)
            groups = scraper.get_groups(soup)
        return [{"text": t, "value": v} for t, v in groups]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not fetch groups: {exc}")


# ---------------------------------------------------------------------------
# FBCYL discovery
# ---------------------------------------------------------------------------

@router.get("/fbcyl/init", summary="Initial FBCYL page — seasons, genders, territories")
def fbcyl_init() -> Dict[str, List[Dict[str, str]]]:
    """Fetch the FBCYL competition finder page and return the three top-level
    dropdown options in a single call to avoid three round-trips.

    Returns:
        Object with ``seasons``, ``genders``, ``territories`` lists,
        each item being a ``{text, value}`` dict.
    """
    from src.scraper.fbcyl_scraper import FBCYLWebScraper
    from src.scraper.web_client import WebClient

    scraper = FBCYLWebScraper(WebClient())
    try:
        soup, _ = scraper.get_page_content()
        return {
            "seasons":     [{"text": t, "value": v} for t, v in scraper.get_seasons(soup)],
            "genders":     [{"text": t, "value": v} for t, v in scraper.get_genders(soup)],
            "territories": [{"text": t, "value": v} for t, v in scraper.get_territories(soup)],
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"FBCYL website unreachable: {exc}")


@router.get("/fbcyl/categories", summary="FBCYL categories for season/gender/territory")
def fbcyl_categories(
    season: str,
    gender: str = "",
    territory: str = "0",
) -> List[Dict[str, str]]:
    """Call the FBCYL AJAX endpoint to get category options.

    Returns:
        List of ``{text, value}`` dicts.
    """
    from src.scraper.fbcyl_scraper import FBCYLWebScraper
    from src.scraper.web_client import WebClient

    scraper = FBCYLWebScraper(WebClient())
    try:
        cats = scraper.fetch_categories_ajax(season, gender, territory)
        return [{"text": t, "value": v} for t, v in cats]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not fetch categories: {exc}")


@router.get("/fbcyl/competitions", summary="FBCYL competitions for category/gender/territory")
def fbcyl_competitions(
    category: str,
    gender: str = "",
    territory: str = "0",
) -> List[Dict[str, str]]:
    """Call the FBCYL AJAX endpoint to get competition options.

    Returns:
        List of ``{text, value}`` dicts.
    """
    from src.scraper.fbcyl_scraper import FBCYLWebScraper
    from src.scraper.web_client import WebClient

    scraper = FBCYLWebScraper(WebClient())
    try:
        comps = scraper.fetch_competitions_ajax(category, gender, territory)
        return [{"text": t, "value": v} for t, v in comps]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not fetch competitions: {exc}")


# ---------------------------------------------------------------------------
# Scraping job — start + progress
# ---------------------------------------------------------------------------

class FEBScrapeParams(BaseModel):
    """Parameters for a FEB scraping job."""

    competition_url: str
    season_value: str
    group_value: str
    year: str = "2025"
    # Human-readable labels used to build the collection name
    competition_label: str      # e.g. "LF2"
    season_label: str           # e.g. "LF2 2025"
    group_label: str            # e.g. "A"


class FBCYLScrapeParams(BaseModel):
    """Parameters for a FBCYL scraping job."""

    competition_id: str
    season: str
    gender: str = ""
    territory: str = "0"
    category: str
    # Human-readable competition label used to build the collection name
    competition_label: str


class ScrapeRequest(BaseModel):
    """Body for POST /scrape/start."""

    league: str                           # "FEB" | "FBCYL"
    feb: Optional[FEBScrapeParams] = None
    fbcyl: Optional[FBCYLScrapeParams] = None


@router.post("/start", summary="Start a background scraping job", dependencies=[Depends(require_admin)])
def start_scrape(
    req: ScrapeRequest,
    background_tasks: BackgroundTasks,
) -> Dict[str, str]:
    """Queue a background job to download and store match data.

    Args:
        req: League selection and associated dropdown values.

    Returns:
        ``{job_id}`` — use it to poll ``GET /scrape/progress/{job_id}``.
    """
    league = req.league.upper()
    if league not in ("FEB", "FBCYL"):
        raise HTTPException(status_code=400, detail="league must be 'FEB' or 'FBCYL'.")

    if league == "FEB" and not req.feb:
        raise HTTPException(status_code=422, detail="feb params required for FEB league.")
    if league == "FBCYL" and not req.fbcyl:
        raise HTTPException(status_code=422, detail="fbcyl params required for FBCYL league.")

    job_id = str(_uuid.uuid4())
    SCRAPE_JOBS[job_id] = {
        "status": "starting",
        "total": 0,
        "done": 0,
        "skipped": 0,
        "errors": [],
        "current_match": None,
        "collection": None,
    }

    if league == "FEB":
        background_tasks.add_task(_run_feb_scrape, job_id, req.feb)
    else:
        background_tasks.add_task(_run_fbcyl_scrape, job_id, req.fbcyl)

    return {"job_id": job_id}


@router.get("/progress/{job_id}", summary="Poll scraping job progress")
def scrape_progress(job_id: str) -> Dict[str, Any]:
    """Return the current state of a scraping job.

    Args:
        job_id: ID returned by ``POST /scrape/start``.

    Returns:
        Object with ``status``, ``total``, ``done``, ``skipped``,
        ``errors``, ``current_match``, ``collection``.

    Raises:
        404 if the job ID is unknown.
    """
    job = SCRAPE_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job


# ---------------------------------------------------------------------------
# Background task implementations
# ---------------------------------------------------------------------------

from src.services.feb_match_ingest import (  # noqa: E402 - shared with the Atlas refresh job
    FEB_STATUS_FINISHED,
    is_in_progress as _is_in_progress,
    save_collection_meta as _save_collection_meta,
    scrape_feb_collection,
    store_feb_match as _store_feb_match,
)
from src.services.fbcyl_match_ingest import (  # noqa: E402 - shared with the refresh job
    scrape_fbcyl_collection,
    store_fbcyl_match as _store_fbcyl_match,
)


def _run_feb_scrape(job_id: str, params: FEBScrapeParams) -> None:
    """Background task: download all FEB matches for the given selection."""
    job = SCRAPE_JOBS[job_id]
    job["status"] = "running"
    try:
        from src.database import MongoDBHandler

        scrape_feb_collection(MongoDBHandler(), params, job=job)
    except Exception as exc:
        job["status"] = "error"
        job["errors"].append(f"Fatal: {exc}")


def _run_fbcyl_scrape(job_id: str, params: FBCYLScrapeParams) -> None:
    """Background task: download all FBCYL matches for the given selection."""
    job = SCRAPE_JOBS[job_id]
    job["status"] = "running"

    try:
        from src.database import MongoDBHandler

        scrape_fbcyl_collection(MongoDBHandler(), params.model_dump(), job=job)
        job["status"] = "done"
        job["current_match"] = None

    except Exception as exc:
        job["status"] = "error"
        job["errors"].append(f"Fatal: {exc}")

