"""Tests for the scrape router — job lifecycle and discovery endpoints.

Covers:
- POST /start with FEB params → returns job_id
- POST /start with FBCYL params → returns job_id
- POST /start with invalid league → 400
- POST /start with FEB but missing feb params → 422
- POST /start with FBCYL but missing fbcyl params → 422
- GET /progress/{job_id} → returns job state
- GET /progress/unknown → 404
- Internal _store_feb_match: skip existing doc
- Internal _store_feb_match: handles scrape error
- Internal _store_fbcyl_match: skip existing doc
- Discovery endpoints: return 502 on external failure
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db
from src.api.routers.scrape import SCRAPE_JOBS, _store_feb_match, _store_fbcyl_match


V1 = "/api/v1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_scrape_jobs():
    """Clear in-process job store before every test."""
    SCRAPE_JOBS.clear()
    yield
    SCRAPE_JOBS.clear()


@pytest.fixture
def client():
    mock_db = MagicMock()
    mock_db.is_connected.return_value = True
    app.dependency_overrides[get_db] = lambda: mock_db
    yield TestClient(app)
    app.dependency_overrides.clear()


_FEB_PARAMS = {
    "league": "FEB",
    "feb": {
        "competition_url": "https://baloncestoenvivo.feb.es/competition/1",
        "season_value": "2025",
        "group_value": "A",
        "year": "2025",
        "competition_label": "LF2",
        "season_label": "LF2 2025",
        "group_label": "A",
    },
}

_FBCYL_PARAMS = {
    "league": "FBCYL",
    "fbcyl": {
        "competition_id": "12",
        "season": "2025",
        "gender": "M",
        "territory": "0",
        "category": "Senior",
        "competition_label": "SeniorA",
    },
}


# ---------------------------------------------------------------------------
# POST /scrape/start
# ---------------------------------------------------------------------------

class TestStartScrape:
    def test_feb_returns_job_id(self, client):
        r = client.post(f"{V1}/scrape/start", json=_FEB_PARAMS)
        assert r.status_code == 200
        data = r.json()
        assert "job_id" in data
        assert len(data["job_id"]) == 36  # UUID4

    def test_fbcyl_returns_job_id(self, client):
        r = client.post(f"{V1}/scrape/start", json=_FBCYL_PARAMS)
        assert r.status_code == 200
        assert "job_id" in r.json()

    def test_invalid_league_returns_400(self, client):
        r = client.post(f"{V1}/scrape/start", json={"league": "ACB"})
        assert r.status_code == 400

    def test_feb_missing_feb_params_returns_422(self, client):
        r = client.post(f"{V1}/scrape/start", json={"league": "FEB"})
        assert r.status_code == 422

    def test_fbcyl_missing_fbcyl_params_returns_422(self, client):
        r = client.post(f"{V1}/scrape/start", json={"league": "FBCYL"})
        assert r.status_code == 422

    def test_job_is_stored_in_scrape_jobs(self, client):
        r = client.post(f"{V1}/scrape/start", json=_FEB_PARAMS)
        job_id = r.json()["job_id"]
        assert job_id in SCRAPE_JOBS

    def test_initial_job_status_is_starting_or_complete(self, client):
        """Background tasks run synchronously in TestClient, so status may advance."""
        r = client.post(f"{V1}/scrape/start", json=_FEB_PARAMS)
        job_id = r.json()["job_id"]
        # Status is set to "starting" before background task runs; TestClient
        # runs background tasks inline so it may have advanced to "done"/"error".
        assert SCRAPE_JOBS[job_id]["status"] in ("starting", "running", "discovering", "done", "error")


# ---------------------------------------------------------------------------
# GET /scrape/progress/{job_id}
# ---------------------------------------------------------------------------

class TestScrapeProgress:
    def test_known_job_returns_state(self, client):
        r = client.post(f"{V1}/scrape/start", json=_FEB_PARAMS)
        job_id = r.json()["job_id"]
        r2 = client.get(f"{V1}/scrape/progress/{job_id}")
        assert r2.status_code == 200
        data = r2.json()
        assert "status" in data
        assert "done" in data
        assert "total" in data
        assert "errors" in data

    def test_unknown_job_returns_404(self, client):
        r = client.get(f"{V1}/scrape/progress/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_progress_counters_start_at_zero(self, client):
        r = client.post(f"{V1}/scrape/start", json=_FEB_PARAMS)
        job_id = r.json()["job_id"]
        data = client.get(f"{V1}/scrape/progress/{job_id}").json()
        assert data["done"] == 0
        assert data["total"] == 0
        assert data["errors"] == []


# ---------------------------------------------------------------------------
# Internal helpers: _store_feb_match
# ---------------------------------------------------------------------------

class TestStoreFebMatch:
    def _make_job(self):
        return {"done": 0, "skipped": 0, "errors": [], "current_match": None}

    def test_skips_existing_document(self):
        job = self._make_job()
        db = MagicMock()
        db.document_exists.return_value = True
        scraper = MagicMock()
        _store_feb_match(job, db, scraper, MagicMock(), "COL", "1001")
        assert job["skipped"] == 1
        assert job["done"] == 1
        scraper.fetch_boxscore.assert_not_called()

    def test_inserts_new_document(self):
        job = self._make_job()
        db = MagicMock()
        db.document_exists.return_value = False
        scraper = MagicMock()
        scraper.fetch_boxscore.return_value = {"HEADER": {}}
        _store_feb_match(job, db, scraper, MagicMock(), "COL", "1001")
        assert job["done"] == 1
        assert job["skipped"] == 0
        db.insert_boxscore.assert_called_once()

    def test_records_error_on_exception(self):
        job = self._make_job()
        db = MagicMock()
        db.document_exists.side_effect = RuntimeError("oops")
        scraper = MagicMock()
        _store_feb_match(job, db, scraper, MagicMock(), "COL", "1001")
        assert job["done"] == 1
        assert len(job["errors"]) == 1
        assert "1001" in job["errors"][0]

    def test_records_error_when_fetch_returns_none(self):
        job = self._make_job()
        db = MagicMock()
        db.document_exists.return_value = False
        scraper = MagicMock()
        scraper.fetch_boxscore.return_value = None
        _store_feb_match(job, db, scraper, MagicMock(), "COL", "1001")
        assert job["done"] == 1
        assert len(job["errors"]) == 1


# ---------------------------------------------------------------------------
# Internal helpers: _store_fbcyl_match
# ---------------------------------------------------------------------------

class TestStoreFbcylMatch:
    def _make_job(self):
        return {"done": 0, "skipped": 0, "errors": [], "current_match": None}

    def test_skips_existing_document(self):
        job = self._make_job()
        db = MagicMock()
        db.document_exists.return_value = True
        scraper = MagicMock()
        _store_fbcyl_match(job, db, scraper, "COL", "uuid-001", {})
        assert job["skipped"] == 1
        scraper.get_match_complete_data.assert_not_called()

    def test_inserts_new_document(self):
        job = self._make_job()
        db = MagicMock()
        db.document_exists.return_value = False
        scraper = MagicMock()
        scraper.get_match_complete_data.return_value = {"stats": {}}
        _store_fbcyl_match(job, db, scraper, "COL", "uuid-001", {})
        assert job["done"] == 1
        db.insert_fbcyl_match.assert_called_once()


# ---------------------------------------------------------------------------
# Discovery endpoints — external failure → 502
# ---------------------------------------------------------------------------

class TestDiscoveryEndpoints:
    def test_feb_competitions_returns_502_on_failure(self, client):
        with patch("src.scraper.FEBWebScraper") as MockScraper:
            MockScraper.return_value.get_feb_competitions.side_effect = ConnectionError("offline")
            r = client.get(f"{V1}/scrape/feb/competitions")
        assert r.status_code == 502

    def test_fbcyl_init_returns_502_on_failure(self, client):
        with patch("src.scraper.fbcyl_scraper.FBCYLWebScraper") as MockScraper:
            MockScraper.return_value.get_page_content.side_effect = ConnectionError("offline")
            r = client.get(f"{V1}/scrape/fbcyl/init")
        assert r.status_code == 502


# ---------------------------------------------------------------------------
# FEB seasons/groups — url-direct load + fallback + regression
# ---------------------------------------------------------------------------

_COMP_URL = "https://baloncestoenvivo.feb.es/calendario/lf2/9/2025"
_COMP_URL_2026 = "https://baloncestoenvivo.feb.es/calendario/lf2/9/2026"


class TestFebDiscoveryEndpoints:
    """Covers the url-direct GET pattern for feb_seasons and feb_groups.

    Before the fix these endpoints called get_page_content(year) which always
    loaded BASE_URL(year='2025').  When the competition url points to a
    different year the __VIEWSTATE from the wrong page causes ASP.NET to
    ignore the postback and return the default group list — omitting
    playoff phases like "ELIMINATORIAS 1/ FINAL".
    """

    # ── feb_seasons ──────────────────────────────────────────────────────────

    def test_feb_seasons_uses_url_directly(self, client):
        """web_client.get must be called with the url parameter, not BASE_URL."""
        from unittest.mock import MagicMock
        fake_resp = MagicMock()
        fake_resp.content = b"<html></html>"
        with patch("src.scraper.FEBWebScraper") as MockScraper:
            inst = MockScraper.return_value
            inst.web_client.get.return_value = fake_resp
            inst.get_seasons.return_value = [("Temporada 2025/26", "s25")]
            r = client.get(f"{V1}/scrape/feb/seasons?url={_COMP_URL}&year=2025")
        assert r.status_code == 200
        inst.web_client.get.assert_called_once_with(_COMP_URL)
        inst.web_scraper.get_page_content.assert_not_called()

    def test_feb_seasons_fallback_on_none_response(self, client):
        """When web_client.get returns None the fallback get_page_content is used."""
        from bs4 import BeautifulSoup
        fake_soup = BeautifulSoup("<html></html>", "html.parser")
        with patch("src.scraper.FEBWebScraper") as MockScraper:
            inst = MockScraper.return_value
            inst.web_client.get.return_value = None
            inst.web_scraper.get_page_content.return_value = (fake_soup, MagicMock())
            inst.get_seasons.return_value = [("Temporada 2025/26", "s25")]
            r = client.get(f"{V1}/scrape/feb/seasons?url={_COMP_URL}&year=2025")
        assert r.status_code == 200
        inst.web_scraper.get_page_content.assert_called_once_with("2025")

    def test_feb_seasons_returns_502_on_exception(self, client):
        with patch("src.scraper.FEBWebScraper") as MockScraper:
            MockScraper.return_value.web_client.get.side_effect = RuntimeError("boom")
            r = client.get(f"{V1}/scrape/feb/seasons?url={_COMP_URL}&year=2025")
        assert r.status_code == 502

    # ── feb_groups ───────────────────────────────────────────────────────────

    def test_feb_groups_uses_url_directly(self, client):
        """get_groups_for_season must be called with the url parameter."""
        with patch("src.scraper.FEBWebScraper") as MockScraper:
            inst = MockScraper.return_value
            inst.get_groups_for_season.return_value = [("Grupo A", "ga")]
            r = client.get(
                f"{V1}/scrape/feb/groups?url={_COMP_URL}&season=s25&year=2025"
            )
        assert r.status_code == 200
        inst.get_groups_for_season.assert_called_once_with(_COMP_URL, "s25")
        inst.web_scraper.get_page_content.assert_not_called()

    def test_feb_groups_fallback_on_empty_result(self, client):
        """When get_groups_for_season returns [] the year-based fallback is used."""
        from bs4 import BeautifulSoup
        fake_soup = BeautifulSoup("<html></html>", "html.parser")
        with patch("src.scraper.FEBWebScraper") as MockScraper:
            inst = MockScraper.return_value
            inst.get_groups_for_season.return_value = []
            inst.web_scraper.get_page_content.return_value = (fake_soup, MagicMock())
            inst.get_hidden_fields.return_value = {}
            inst.select_season.return_value = (fake_soup, {})
            inst.get_groups.return_value = [("Grupo A", "ga")]
            r = client.get(
                f"{V1}/scrape/feb/groups?url={_COMP_URL}&season=s25&year=2025"
            )
        assert r.status_code == 200
        inst.web_scraper.get_page_content.assert_called_once_with("2025")
        data = r.json()
        assert data[0]["text"] == "Grupo A"

    def test_feb_groups_returns_502_on_exception(self, client):
        with patch("src.scraper.FEBWebScraper") as MockScraper:
            MockScraper.return_value.get_groups_for_season.side_effect = RuntimeError("boom")
            r = client.get(
                f"{V1}/scrape/feb/groups?url={_COMP_URL}&season=s25&year=2025"
            )
        assert r.status_code == 502

    def test_feb_groups_returns_eliminatorias_group_regression(self, client):
        """Regression: ELIMINATORIAS 1/ FINAL must appear when the scraper returns it.

        Before the fix the VIEWSTATE mismatch caused ASP.NET to ignore the
        season selection postback so only default (regular-season) groups were
        returned — the playoff group "ELIMINATORIAS 1/ FINAL" was silently
        omitted.
        """
        playoff_groups = [
            ("Grupo A", "ga"),
            ("Grupo B", "gb"),
            ("ELIMINATORIAS 1/ FINAL", "elim1"),
        ]
        with patch("src.scraper.FEBWebScraper") as MockScraper:
            MockScraper.return_value.get_groups_for_season.return_value = playoff_groups
            r = client.get(
                f"{V1}/scrape/feb/groups?url={_COMP_URL}&season=s25&year=2025"
            )
        assert r.status_code == 200
        texts = [item["text"] for item in r.json()]
        assert "ELIMINATORIAS 1/ FINAL" in texts

    def test_feb_groups_year_mismatch_does_not_break_regression(self, client):
        """Regression: url with year=2026 and year param=2025 must not raise.

        This simulates the October 2026 scenario when the FEB website updates
        its competition links to /9/2026 but the frontend still sends year=2025
        as the default.  The fix (using url directly) makes the year param
        irrelevant for the happy path.
        """
        with patch("src.scraper.FEBWebScraper") as MockScraper:
            MockScraper.return_value.get_groups_for_season.return_value = [
                ("Grupo A", "ga")
            ]
            r = client.get(
                f"{V1}/scrape/feb/groups?url={_COMP_URL_2026}&season=s26&year=2025"
            )
        assert r.status_code == 200
        assert r.json()[0]["text"] == "Grupo A"
