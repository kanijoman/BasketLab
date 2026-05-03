"""Scrape router — competition discovery and background data ingestion.

Discovery endpoints return dropdown data scraped live from the FEB/FBCYL
websites so the AdminPage can build its cascading selectors.

Ingestion endpoints accept the user's selection, kick off a background job
that downloads match data, and expose a polling endpoint for progress.

Job state is held in-process (module-level dict).  It resets on server
restart — acceptable for a PoC.  For production, replace with Redis/Celery.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

router = APIRouter()

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


@router.post("/start", summary="Start a background scraping job")
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

def _store_feb_match(
    job: Dict[str, Any],
    db: Any,
    scraper: Any,
    session: Any,
    collection_name: str,
    code: str,
) -> None:
    """Fetch and store a single FEB match; update job counters."""
    job["current_match"] = code
    try:
        if db.document_exists(collection_name, int(code)):
            job["skipped"] += 1
            return
        doc = scraper.fetch_boxscore(code, session)
        if doc:
            db.insert_boxscore(collection_name, code, doc)
        else:
            job["errors"].append(f"No data for match {code}")
    except Exception as exc:
        job["errors"].append(f"Match {code}: {exc}")
    finally:
        job["done"] += 1


def _run_feb_scrape(job_id: str, params: FEBScrapeParams) -> None:
    """Background task: download all FEB matches for the given selection."""
    job = SCRAPE_JOBS[job_id]
    job["status"] = "running"

    try:
        from src.scraper import FEBWebScraper
        from src.database import MongoDBHandler, get_collection_name

        scraper = FEBWebScraper()
        db = MongoDBHandler()

        collection_name = get_collection_name(
            params.competition_label, params.season_label, params.group_label,
        )
        job["collection"] = collection_name

        job["status"] = "discovering"
        _, session = scraper.get_page_content(params.year)
        match_codes = scraper.get_matches(
            params.season_value, params.group_value, params.year,
            session, url=params.competition_url,
        )
        job["total"] = len(match_codes)
        job["status"] = "running"

        for code in match_codes:
            _store_feb_match(job, db, scraper, session, collection_name, code)

        job["status"] = "done"
        job["current_match"] = None

    except Exception as exc:
        job["status"] = "error"
        job["errors"].append(f"Fatal: {exc}")


def _store_fbcyl_match(
    job: Dict[str, Any],
    db: Any,
    scraper: Any,
    collection_name: str,
    uuid: str,
    league_ctx: Dict[str, str],
) -> None:
    """Fetch and store a single FBCYL match; update job counters."""
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
    except Exception as exc:
        job["errors"].append(f"Match {uuid}: {exc}")
    finally:
        job["done"] += 1


def _run_fbcyl_scrape(job_id: str, params: FBCYLScrapeParams) -> None:
    """Background task: download all FBCYL matches for the given selection."""
    job = SCRAPE_JOBS[job_id]
    job["status"] = "running"

    try:
        from src.scraper.fbcyl_scraper import FBCYLWebScraper
        from src.scraper.web_client import WebClient
        from src.database import MongoDBHandler, get_collection_name

        scraper = FBCYLWebScraper(WebClient())
        db = MongoDBHandler()

        collection_name = get_collection_name(
            f"FBCYL_{params.competition_label}", params.season, "",
        )
        job["collection"] = collection_name

        league_ctx: Dict[str, str] = {
            "gender": params.gender,
            "territory": params.territory,
            "category": params.category,
            "competition_id": params.competition_id,
            "season": params.season,
        }

        job["status"] = "discovering"
        match_uuids = scraper.get_matches(params.competition_id)
        job["total"] = len(match_uuids)
        job["status"] = "running"

        for uuid in match_uuids:
            _store_fbcyl_match(job, db, scraper, collection_name, uuid, league_ctx)

        job["status"] = "done"
        job["current_match"] = None

    except Exception as exc:
        job["status"] = "error"
        job["errors"].append(f"Fatal: {exc}")
