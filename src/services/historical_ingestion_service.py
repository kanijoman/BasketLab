"""Historical ingestion service — orchestrates scraping + normalization + upsert.

Reutiilses the existing FEB/FBCYL scrapers without modification.  For each
downloaded match document it produces **two** HISTORICAL documents (one per
team), pre-computing all derived stats and per-100-possession differentials so
predictive-model queries are simple ``$match`` / ``$group`` pipelines.

Normalisation logic is split into focused sub-modules:
- :mod:`src.services._historical_derived` — stat formulae
- :mod:`src.services._feb_normalizer` — FEB document normaliser
- :mod:`src.services._fbcyl_normalizer` — FBCYL document normaliser
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.services._feb_normalizer import normalize_feb_match as _normalize_feb
from src.services._fbcyl_normalizer import normalize_fbcyl_match as _normalize_fbcyl
# Backward-compat re-exports for tests that import private helpers directly
from src.services._historical_derived import compute_derived as _compute_derived, _efg


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_FEB_DATE_RE = re.compile(r"(\d{2})-(\d{2})-(\d{4})")


def _parse_date(raw: str) -> Optional[datetime]:
    """Parse a date string from FEB/FBCYL into a datetime object.

    Handles the FEB format ``"dd-mm-yyyy - HH:MM"`` and falls back to ISO.
    """
    if not raw:
        return None
    m = _FEB_DATE_RE.search(raw)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return datetime(year, month, day)
    try:
        return datetime.fromisoformat(raw[:10])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Public normalization API (re-exported for backward compatibility)
# ---------------------------------------------------------------------------

def normalize_feb_match(
    doc: Dict[str, Any],
    season: str,
    competition: str,
    group: str,
    source_collection: str,
    scraped_at: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Convert a FEB game document into two HISTORICAL documents (one per team)."""
    return _normalize_feb(
        doc, season, competition, group, source_collection,
        _parse_date, scraped_at,
    )


def normalize_fbcyl_match(
    doc: Dict[str, Any],
    season: str,
    competition: str,
    group: str,
    gender: Optional[str],
    source_collection: str,
    scraped_at: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Convert a FBCYL game document into two HISTORICAL documents."""
    return _normalize_fbcyl(
        doc, season, competition, group, gender, source_collection,
        _parse_date, scraped_at,
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class HistoricalIngestionService:
    """Orchestrates downloading a season and storing it in HISTORICAL.

    Designed to run inside a background thread (same pattern as the existing
    scraping jobs) so it can report progress through a shared job-state dict.
    """

    def __init__(self, repository):
        """
        Args:
            repository: ``HistoricalRepository`` instance.
        """
        self._repo = repository

    def ingest_feb_season(
        self,
        job: Dict[str, Any],
        competition_url: str,
        season_value: str,
        group_value: str,
        year: str,
        competition_label: str,
        season_label: str,
        group_label: str,
        normalized_season: str,
    ) -> None:
        """Download every FEB match for one season and upsert into HISTORICAL.

        Updates *job* in place so the caller's progress endpoint reflects live
        state.
        """
        from src.scraper import FEBWebScraper
        from src.database import get_collection_name

        scraper = FEBWebScraper()
        source_col = get_collection_name(competition_label, season_label, group_label)

        job["status"] = "discovering"
        _, session = scraper.get_page_content(year)
        match_codes = scraper.get_matches(
            season_value, group_value, year, session, url=competition_url
        )
        job["total"] = job.get("total", 0) + len(match_codes)
        job["status"] = "running"

        scraped_at = datetime.utcnow()
        for code in match_codes:
            job["current_match"] = code
            try:
                doc = scraper.fetch_boxscore(code, session)
                if not doc:
                    job["errors"].append(f"No data for match {code}")
                    continue
                hdocs = normalize_feb_match(
                    doc,
                    season=normalized_season,
                    competition=competition_label,
                    group=group_label,
                    source_collection=source_col,
                    scraped_at=scraped_at,
                )
                for hdoc in hdocs:
                    self._repo.upsert_match_team(hdoc)
            except Exception as exc:
                job["errors"].append(f"Match {code}: {exc}")
            finally:
                job["done"] = job.get("done", 0) + 1

    def ingest_feb_competition(
        self,
        job: Dict[str, Any],
        competition_url: str,
        competition_label: str,
        year: str,
        seasons: List[Dict[str, str]],
    ) -> None:
        """Download all groups for each selected season into HISTORICAL."""
        from src.scraper import FEBWebScraper

        _season_re = re.compile(r"\d{4}-\d{2}")
        scraper = FEBWebScraper()

        for season_info in seasons:
            season_value = season_info["season_value"]
            season_label = season_info["season_label"]
            m = _season_re.search(season_label)
            normalized = m.group(0) if m else season_label

            job["current_season"] = normalized
            job["status"] = "discovering"

            groups = scraper.get_groups_for_season(competition_url, season_value)
            if not groups:
                job["errors"].append(
                    f"No se encontraron grupos para {normalized}. "
                    "La temporada puede estar vacía o no disponible."
                )
                continue

            for group_label, group_value in groups:
                self.ingest_feb_season(
                    job=job,
                    competition_url=competition_url,
                    season_value=season_value,
                    group_value=group_value,
                    year=year,
                    competition_label=competition_label,
                    season_label=season_label,
                    group_label=group_label,
                    normalized_season=normalized,
                )

    def ingest_fbcyl_season(
        self,
        job: Dict[str, Any],
        competition_id: str,
        season: str,
        gender: str,
        territory: str,
        category: str,
        competition_label: str,
        normalized_season: str,
    ) -> None:
        """Download every FBCYL match for one season and upsert into HISTORICAL."""
        from src.scraper.fbcyl_scraper import FBCYLWebScraper
        from src.scraper.web_client import WebClient
        from src.database import get_collection_name

        scraper = FBCYLWebScraper(WebClient())
        league_ctx = {
            "gender": gender,
            "territory": territory,
            "category": category,
            "competition_id": competition_id,
            "season": season,
        }
        source_col = get_collection_name(
            f"FBCYL_{competition_label}", season, ""
        )

        job["status"] = "discovering"
        match_uuids = scraper.get_matches(competition_id)
        job["total"] = job.get("total", 0) + len(match_uuids)
        job["status"] = "running"

        scraped_at = datetime.utcnow()
        gender_char = "F" if "f" in gender.lower() else "M" if gender else None

        for uuid in match_uuids:
            job["current_match"] = uuid
            try:
                doc = scraper.get_match_complete_data(uuid, league_ctx=league_ctx)
                if not doc:
                    job["errors"].append(f"No data for match {uuid}")
                    continue
                hdocs = normalize_fbcyl_match(
                    doc,
                    season=normalized_season,
                    competition=competition_label,
                    group="",
                    gender=gender_char,
                    source_collection=source_col,
                    scraped_at=scraped_at,
                )
                for hdoc in hdocs:
                    self._repo.upsert_match_team(hdoc)
            except Exception as exc:
                job["errors"].append(f"Match {uuid}: {exc}")
            finally:
                job["done"] = job.get("done", 0) + 1

        _season_re = re.compile(r"\d{4}-\d{2}")
        scraper = FEBWebScraper()

        for season_info in seasons:
            season_value = season_info["season_value"]
            season_label = season_info["season_label"]
            m = _season_re.search(season_label)
            normalized = m.group(0) if m else season_label

            job["current_season"] = normalized
            job["status"] = "discovering"

            groups = scraper.get_groups_for_season(competition_url, season_value)
            if not groups:
                job["errors"].append(
                    f"No se encontraron grupos para {normalized}. "
                    "La temporada puede estar vacía o no disponible."
                )
                continue

            for group_label, group_value in groups:
                self.ingest_feb_season(
                    job=job,
                    competition_url=competition_url,
                    season_value=season_value,
                    group_value=group_value,
                    year=year,
                    competition_label=competition_label,
                    season_label=season_label,
                    group_label=group_label,
                    normalized_season=normalized,
                )

    def ingest_fbcyl_season(
        self,
        job: Dict[str, Any],
        competition_id: str,
        season: str,
        gender: str,
        territory: str,
        category: str,
        competition_label: str,
        normalized_season: str,
    ) -> None:
        """Download every FBCYL match for one season and upsert into HISTORICAL.

        Args:
            job:                Mutable job-state dict.
            competition_id:     FBCYL competition identifier.
            season:             Season identifier used by the FBCYL scraper.
            gender:             Gender string, e.g. ``"F"`` or ``""``.
            territory:          Territory identifier.
            category:           Category identifier.
            competition_label:  Human-readable competition name.
            normalized_season:  Normalised season string, e.g. ``"2024-25"``.
        """
        from src.scraper.fbcyl_scraper import FBCYLWebScraper
        from src.scraper.web_client import WebClient
        from src.database import get_collection_name

        scraper = FBCYLWebScraper(WebClient())
        league_ctx = {
            "gender": gender,
            "territory": territory,
            "category": category,
            "competition_id": competition_id,
            "season": season,
        }
        source_col = get_collection_name(
            f"FBCYL_{competition_label}", season, ""
        )

        job["status"] = "discovering"
        match_uuids = scraper.get_matches(competition_id)
        job["total"] = job.get("total", 0) + len(match_uuids)
        job["status"] = "running"

        scraped_at = datetime.utcnow()
        gender_char = "F" if "f" in gender.lower() else "M" if gender else None

        for uuid in match_uuids:
            job["current_match"] = uuid
            try:
                doc = scraper.get_match_complete_data(uuid, league_ctx=league_ctx)
                if not doc:
                    job["errors"].append(f"No data for match {uuid}")
                    continue
                hdocs = normalize_fbcyl_match(
                    doc,
                    season=normalized_season,
                    competition=competition_label,
                    group="",
                    gender=gender_char,
                    source_collection=source_col,
                    scraped_at=scraped_at,
                )
                for hdoc in hdocs:
                    self._repo.upsert_match_team(hdoc)
            except Exception as exc:
                job["errors"].append(f"Match {uuid}: {exc}")
            finally:
                job["done"] = job.get("done", 0) + 1
