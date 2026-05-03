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


# ---------------------------------------------------------------------------
# FEB scraper — _get_fases_groups + _calendar_to_results_url unit tests
# ---------------------------------------------------------------------------

class TestFebScraperFasesGroups:
    """Unit tests for the fasesDataList navigation link parser."""

    @pytest.fixture
    def scraper(self):
        from unittest.mock import MagicMock, patch
        with patch("src.scraper.feb_scraper.FEBWebScraper.__init__", return_value=None):
            from src.scraper.feb_scraper import FEBWebScraper
            s = FEBWebScraper.__new__(FEBWebScraper)
            s.web_client = MagicMock()
            s._series_url_by_group = {}
            return s

    def _soup_with_fases(self, links):
        """Build a minimal soup containing a fasesDataList with given links."""
        from bs4 import BeautifulSoup
        items = "".join(
            f'<a id="fake_{i}" class="hyperlink" href="{href}">{label}</a>'
            for i, (label, href) in enumerate(links)
        )
        html = (
            f'<table id="_ctl0_MainContentPlaceHolderMaster_fasesDataList">'
            f'{items}</table>'
        )
        return BeautifulSoup(html, "html.parser")

    def _soup_group_dropdown(self, value, text):
        """Build a Series.aspx response soup with a group dropdown."""
        from bs4 import BeautifulSoup
        html = (
            f'<select id="_ctl0_MainContentPlaceHolderMaster_gruposDropDownList">'
            f'<option selected="selected" value="{value}">{text}</option>'
            f'</select>'
        )
        return BeautifulSoup(html, "html.parser")

    def test_returns_empty_when_no_fases_container(self, scraper):
        from bs4 import BeautifulSoup
        empty = BeautifulSoup("<html></html>", "html.parser")
        result = scraper._get_fases_groups(empty, set())
        assert result == []

    def test_resolves_direct_link_layout2_aspx_url_regression(self, scraper):
        """Regression: Layout 2 — direct <a> with ID containing fasesDataList.

        The calendario.aspx?g=... URL does not render an outer container;
        the <a> elements have IDs like ..._fasesDataList__ctl0_seriesHyperLink.
        """
        from unittest.mock import MagicMock
        from bs4 import BeautifulSoup
        # Layout 2: direct <a> without outer container
        html = (
            '<a id="_ctl0_MainContentPlaceHolderMaster_fasesDataList__ctl0_seriesHyperLink"'
            ' href="https://baloncestoenvivo.feb.es/Series.aspx?f=44785">'
            '2\u00baA-1\u00baB Final</a>'
        )
        soup = BeautifulSoup(html, "html.parser")
        series_resp = MagicMock()
        series_resp.content = str(
            self._soup_group_dropdown("89477", "2\u00baA-1\u00baB Final")
        ).encode()
        scraper.web_client.get.return_value = series_resp

        result = scraper._get_fases_groups(soup, set())
        assert len(result) == 1
        assert result[0] == ("2\u00baA-1\u00baB Final", "89477")
        # Cache must be populated
        assert scraper._series_url_by_group.get("89477") == (
            "https://baloncestoenvivo.feb.es/Series.aspx?f=44785"
        )

    def test_resolves_single_fases_link_to_group_id(self, scraper):
        from unittest.mock import MagicMock
        soup = self._soup_with_fases([
            ("ELIMINATORIAS", "https://baloncestoenvivo.feb.es/Series.aspx?f=44786")
        ])
        series_resp = MagicMock()
        series_resp.content = str(self._soup_group_dropdown("89478", "ELIMINATORIAS 1/4 Final")).encode()
        scraper.web_client.get.return_value = series_resp

        result = scraper._get_fases_groups(soup, set())
        assert len(result) == 1
        assert result[0] == ("ELIMINATORIAS", "89478")

    def test_skips_already_known_ids(self, scraper):
        """Groups whose IDs are already in existing_ids are not duplicated."""
        from unittest.mock import MagicMock
        soup = self._soup_with_fases([
            ("ELIMINATORIAS", "https://baloncestoenvivo.feb.es/Series.aspx?f=44786")
        ])
        series_resp = MagicMock()
        series_resp.content = str(self._soup_group_dropdown("89478", "ELIMINATORIAS")).encode()
        scraper.web_client.get.return_value = series_resp

        result = scraper._get_fases_groups(soup, {"89478"})  # already known
        assert result == []

    def test_skips_link_when_series_page_unreachable(self, scraper):
        soup = self._soup_with_fases([
            ("ELIMINATORIAS", "https://baloncestoenvivo.feb.es/Series.aspx?f=44786")
        ])
        scraper.web_client.get.return_value = None
        result = scraper._get_fases_groups(soup, set())
        assert result == []

    def test_skips_link_when_no_group_dropdown_on_series_page(self, scraper):
        from unittest.mock import MagicMock
        from bs4 import BeautifulSoup
        soup = self._soup_with_fases([
            ("ELIMINATORIAS", "https://baloncestoenvivo.feb.es/Series.aspx?f=44786")
        ])
        resp = MagicMock()
        resp.content = b"<html><body>no dropdown</body></html>"
        scraper.web_client.get.return_value = resp
        result = scraper._get_fases_groups(soup, set())
        assert result == []

    def test_resolves_multiple_fases_links(self, scraper):
        """Two fasesDataList links should both be resolved and returned."""
        from unittest.mock import MagicMock
        soup = self._soup_with_fases([
            ("ELIMINATORIAS", "https://baloncestoenvivo.feb.es/Series.aspx?f=44786"),
            ("2ºA-1ºB", "https://baloncestoenvivo.feb.es/Series.aspx?f=44785"),
        ])
        responses = [
            MagicMock(content=str(self._soup_group_dropdown("89478", "ELIM")).encode()),
            MagicMock(content=str(self._soup_group_dropdown("89477", "2AB")).encode()),
        ]
        scraper.web_client.get.side_effect = responses
        result = scraper._get_fases_groups(soup, set())
        assert len(result) == 2
        assert ("ELIMINATORIAS", "89478") in result
        assert ("2ºA-1ºB", "89477") in result


class TestCalendarToResultsUrl:
    """Unit tests for _FEBWebScraper._calendar_to_results_url."""

    def _convert(self, url, season):
        from src.scraper.feb_scraper import FEBWebScraper
        return FEBWebScraper._calendar_to_results_url(url, season)

    def test_pretty_url_converted_correctly(self):
        result = self._convert(
            "https://baloncestoenvivo.feb.es/calendario/lf2/9/2025", "2025"
        )
        assert result == "https://baloncestoenvivo.feb.es/resultados/lf2/9/2025"

    def test_pretty_url_season_updated(self):
        """When a different season is requested the year in the path changes."""
        result = self._convert(
            "https://baloncestoenvivo.feb.es/calendario/lf2/9/2025", "2024"
        )
        assert result == "https://baloncestoenvivo.feb.es/resultados/lf2/9/2024"

    def test_aspx_url_converted_correctly(self):
        result = self._convert(
            "https://baloncestoenvivo.feb.es/calendario.aspx?g=9&t=2025&nm=lf2", "2025"
        )
        assert result == "https://baloncestoenvivo.feb.es/resultados.aspx?g=9&t=2025&nm=lf2"

    def test_aspx_url_season_updated(self):
        result = self._convert(
            "https://baloncestoenvivo.feb.es/calendario.aspx?g=9&t=2025&nm=lf2", "2024"
        )
        assert result == "https://baloncestoenvivo.feb.es/resultados.aspx?g=9&t=2024&nm=lf2"

    def test_unrecognised_url_returned_unchanged(self):
        url = "https://baloncestoenvivo.feb.es/other/page"
        assert self._convert(url, "2025") == url


# ---------------------------------------------------------------------------
# get_matches — playoff group switches to /resultados/ URL
# ---------------------------------------------------------------------------

class TestGetMatchesPlayoffGroup:
    """Regression: select_group POST must not be sent to /calendario/ for
    groups that are absent from that page's dropdown (e.g. playoff phases).

    Before the fix, _run_feb_scrape crashed with
    'Fatal: Failed to select group' because the ASP.NET server returned a
    non-200 for an unknown group value, causing web_client.post → None.
    """

    @pytest.fixture
    def scraper(self):
        from unittest.mock import MagicMock, patch
        with patch("src.scraper.feb_scraper.FEBWebScraper.__init__", return_value=None):
            from src.scraper.feb_scraper import FEBWebScraper
            s = FEBWebScraper.__new__(FEBWebScraper)
            s.web_client = MagicMock()
            s._series_url_by_group = {}
            return s

    def _make_calendar_soup(self, group_options, selected_season="2025"):
        """Calendar page with limited groups (no playoff groups)."""
        from bs4 import BeautifulSoup
        opts = "".join(
            f'<option {"selected" if i == 0 else ""} value="{v}">{t}</option>'
            for i, (t, v) in enumerate(group_options)
        )
        html = (
            f'<select id="_ctl0_MainContentPlaceHolderMaster_temporadasDropDownList">'
            f'<option selected value="{selected_season}">{selected_season}/2026</option>'
            f'</select>'
            f'<select id="_ctl0_MainContentPlaceHolderMaster_gruposDropDownList">{opts}</select>'
            f'<input id="__VIEWSTATE" value="vs1"/>'
            f'<input id="__EVENTVALIDATION" value="ev1"/>'
        )
        return BeautifulSoup(html, "html.parser")

    def _make_results_soup(self, group_options, selected_season="2025", match_code="12345"):
        """Results page with all groups including playoffs, with a match link."""
        from bs4 import BeautifulSoup
        opts = "".join(
            f'<option value="{v}">{t}</option>'
            for t, v in group_options
        )
        html = (
            f'<select id="_ctl0_MainContentPlaceHolderMaster_temporadasDropDownList">'
            f'<option selected value="{selected_season}">{selected_season}/2026</option>'
            f'</select>'
            f'<select id="_ctl0_MainContentPlaceHolderMaster_gruposDropDownList">{opts}</select>'
            f'<input id="__VIEWSTATE" value="vs2"/>'
            f'<input id="__EVENTVALIDATION" value="ev2"/>'
            f'<div class="tableLayout de dos columnas">'
            f'  <table><tr><th>Match</th></tr>'
            f'  <tr><td class="resultado"><a href="partido.aspx?p={match_code}">72 - 65</a></td></tr>'
            f'  </table></div>'
        )
        return BeautifulSoup(html, "html.parser")

    def test_playoff_group_switches_to_resultados_url_regression(self, scraper):
        """Regression: playoff group must use /resultados/ URL, not /calendario/."""
        from unittest.mock import MagicMock, call
        import requests

        calendar_url = "https://baloncestoenvivo.feb.es/calendario/lf2/9/2025"
        results_url = "https://baloncestoenvivo.feb.es/resultados/lf2/9/2025"
        regular_groups = [("Liga Regular A", "88868"), ("Liga Regular B", "88869")]
        all_groups = regular_groups + [("ELIMINATORIAS 1/4 Final", "89478")]

        calendar_soup = self._make_calendar_soup(regular_groups)
        results_soup = self._make_results_soup(all_groups, match_code="99001")
        after_select_soup = self._make_results_soup(
            all_groups, match_code="99001"
        )

        cal_resp = MagicMock(); cal_resp.content = str(calendar_soup).encode()
        res_resp = MagicMock(); res_resp.content = str(results_soup).encode()
        post_resp = MagicMock(); post_resp.content = str(after_select_soup).encode()

        scraper.web_client.get.side_effect = [cal_resp, res_resp]
        scraper.web_client.post.return_value = post_resp
        scraper.web_client.get_session.return_value = MagicMock()

        matches = scraper.get_matches("2025", "89478", "2025",
                                      MagicMock(spec=requests.Session),
                                      url=calendar_url)

        # Must have switched to the resultados URL for the group POST
        post_calls = scraper.web_client.post.call_args_list
        assert any(results_url in str(c) for c in post_calls), (
            "select_group POST should target /resultados/ URL, not /calendario/"
        )
        assert "99001" in matches

    def test_regular_group_does_not_switch_to_resultados(self, scraper):
        """Regular-season groups must NOT trigger the resultados URL switch."""
        from unittest.mock import MagicMock
        import requests

        calendar_url = "https://baloncestoenvivo.feb.es/calendario/lf2/9/2025"
        regular_groups = [("Liga Regular A", "88868"), ("Liga Regular B", "88869")]
        after_select_soup = self._make_results_soup(regular_groups, match_code="88001")

        cal_resp = MagicMock()
        cal_resp.content = str(self._make_calendar_soup(regular_groups)).encode()
        post_resp = MagicMock()
        post_resp.content = str(after_select_soup).encode()

        scraper.web_client.get.return_value = cal_resp
        scraper.web_client.post.return_value = post_resp
        scraper.web_client.get_session.return_value = MagicMock()

        matches = scraper.get_matches("2025", "88869", "2025",
                                      MagicMock(spec=requests.Session),
                                      url=calendar_url)

        # Must have posted to the calendar URL (no switch to resultados)
        post_calls = scraper.web_client.post.call_args_list
        assert all("resultados" not in str(c) for c in post_calls), (
            "Regular groups must not trigger /resultados/ switch"
        )
        assert "88001" in matches


# ---------------------------------------------------------------------------
# _extract_match_codes — fallback for /resultados/ page structure
# ---------------------------------------------------------------------------

class TestExtractMatchCodesFallback:
    """Regression: _extract_match_codes must extract codes from /resultados/
    pages which use jornadaDataGrid instead of 'tableLayout de dos columnas'."""

    @pytest.fixture
    def scraper(self):
        from unittest.mock import MagicMock, patch
        with patch("src.scraper.feb_scraper.FEBWebScraper.__init__", return_value=None):
            from src.scraper.feb_scraper import FEBWebScraper
            s = FEBWebScraper.__new__(FEBWebScraper)
            s.web_client = MagicMock()
            return s

    def _resultados_soup(self, codes_and_scores):
        """Build a minimal /resultados/-style page with match links."""
        from bs4 import BeautifulSoup
        rows = "".join(
            f'<tr><td><a href="https://baloncestoenvivo.feb.es/Partido.aspx?p={code}">'
            f'{score}</a></td></tr>'
            for code, score in codes_and_scores
        )
        html = (
            f'<table id="_ctl0_MainContentPlaceHolderMaster_jornadaDataGrid">'
            f'{rows}</table>'
        )
        return BeautifulSoup(html, "html.parser")

    def test_extracts_codes_from_resultados_structure_regression(self, scraper):
        """Regression: playoff match codes must be found on /resultados/ pages."""
        soup = self._resultados_soup([
            ("2512426", "52-67"),
            ("2512422", "56-65"),
            ("2512424", "68-70"),
            ("2512423", "*-*"),   # future match — must be skipped
        ])
        codes = scraper._extract_match_codes(soup)
        assert set(codes) == {"2512426", "2512422", "2512424"}
        assert len(codes) == 3

    def test_skips_future_matches_with_star_score(self, scraper):
        soup = self._resultados_soup([("9999", "*-*"), ("8888", "70-60")])
        codes = scraper._extract_match_codes(soup)
        assert codes == ["8888"]

    def test_calendar_structure_still_works(self, scraper):
        """Primary /calendario/ structure must still be used when present."""
        from bs4 import BeautifulSoup
        html = (
            '<div class="tableLayout de dos columnas">'
            '  <table>'
            '    <tr><th>Header</th></tr>'
            '    <tr><td class="resultado">'
            '      <a href="partido.aspx?p=11111">72 - 65</a>'
            '    </td></tr>'
            '  </table>'
            '</div>'
        )
        soup = BeautifulSoup(html, "html.parser")
        codes = scraper._extract_match_codes(soup)
        assert codes == ["11111"]

    def test_no_duplicates_across_both_structures(self, scraper):
        """Same code must not appear twice even if both structures are present."""
        from bs4 import BeautifulSoup
        html = (
            '<div class="tableLayout de dos columnas">'
            '  <table><tr><th/></tr>'
            '  <tr><td class="resultado">'
            '    <a href="partido.aspx?p=55555">72 - 65</a>'
            '  </td></tr></table></div>'
            '<table id="jornadaDataGrid">'
            '  <tr><td><a href="Partido.aspx?p=55555">72-65</a></td></tr>'
            '</table>'
        )
        soup = BeautifulSoup(html, "html.parser")
        codes = scraper._extract_match_codes(soup)
        assert codes.count("55555") == 1


# ---------------------------------------------------------------------------
# _get_matches_via_series — Series.aspx fallback for groups with no matches
# on /resultados/ page (e.g. "2ºA-1ºB Final")
# ---------------------------------------------------------------------------

class TestGetMatchesViaSeriesFallback:
    """Regression: get_matches must return match codes for playoff groups whose
    matches only appear on Series.aspx pages, not on /resultados/.

    Root cause: after select_group POST, the ASP.NET session state causes a
    re-GET of /calendario/ to omit the fasesDataList block.  The fix caches
    the group→Series.aspx URL mapping during get_groups_for_season so
    _get_matches_via_series can use it directly.
    """

    @pytest.fixture
    def scraper(self):
        from unittest.mock import MagicMock, patch
        with patch("src.scraper.feb_scraper.FEBWebScraper.__init__", return_value=None):
            from src.scraper.feb_scraper import FEBWebScraper
            s = FEBWebScraper.__new__(FEBWebScraper)
            s.web_client = MagicMock()
            s._series_url_by_group = {}
            return s

    def _series_soup(self, group_value, match_codes_scores):
        """Series.aspx page with group dropdown selected and match links."""
        from bs4 import BeautifulSoup
        opts = f'<option selected value="{group_value}">2ºA-1ºB Final</option>'
        rows = "".join(
            f'<tr><td><a href="https://baloncestoenvivo.feb.es/Partido.aspx?p={code}">'
            f'{score}</a></td></tr>'
            for code, score in match_codes_scores
        )
        html = (
            f'<select id="_ctl0_MainContentPlaceHolderMaster_gruposDropDownList">'
            f'{opts}</select>'
            f'<table id="jornadaDataGrid">{rows}</table>'
        )
        return BeautifulSoup(html, "html.parser")

    def test_uses_cached_series_url_when_available_regression(self, scraper):
        """Regression: when cache has series URL for the group, use it directly."""
        from unittest.mock import MagicMock
        series_url = "https://baloncestoenvivo.feb.es/Series.aspx?f=44785"
        scraper._series_url_by_group["89477"] = series_url

        series_resp = MagicMock()
        series_resp.content = str(
            self._series_soup("89477", [("2512420", "58 - 71"), ("2512421", "* - *")])
        ).encode()
        scraper.web_client.get.return_value = series_resp

        codes = scraper._get_matches_via_series(
            "https://baloncestoenvivo.feb.es/calendario.aspx?g=9&t=2025&nm=lf2",
            "89477",
        )

        assert codes == ["2512420"], f"Expected ['2512420'], got {codes}"
        # Must have fetched the cached series URL, not the calendar
        scraper.web_client.get.assert_called_once_with(
            series_url, timeout=scraper.web_client.get.call_args[1].get("timeout", None)
            if scraper.web_client.get.call_args[1] else None
        )

    def test_cached_series_url_skips_future_matches(self, scraper):
        """Only completed matches (score digits-digits) must be returned."""
        from unittest.mock import MagicMock
        series_url = "https://baloncestoenvivo.feb.es/Series.aspx?f=44785"
        scraper._series_url_by_group["89477"] = series_url

        series_resp = MagicMock()
        series_resp.content = str(
            self._series_soup("89477", [("2512421", "* - *"), ("2512422", "* - *")])
        ).encode()
        scraper.web_client.get.return_value = series_resp

        codes = scraper._get_matches_via_series(
            "https://baloncestoenvivo.feb.es/calendario.aspx?g=9&t=2025&nm=lf2",
            "89477",
        )
        assert codes == [], "Future-only playoff series must return empty list"

    def test_cache_populated_by_get_fases_groups(self, scraper):
        """_get_fases_groups must populate _series_url_by_group for each found group."""
        from unittest.mock import MagicMock
        from bs4 import BeautifulSoup

        series_url = "https://baloncestoenvivo.feb.es/Series.aspx?f=44785"
        # Calendar page with fasesDataList link
        cal_html = (
            f'<div id="_ctl0_MainContentPlaceHolderMaster_fasesDataList">'
            f'  <a href="{series_url}">2ºA-1ºB Final</a>'
            f'</div>'
        )
        # Series page with group 89477 selected
        series_html = (
            '<select id="_ctl0_MainContentPlaceHolderMaster_gruposDropDownList">'
            '  <option selected value="89477">2ºA-1ºB Final</option>'
            '</select>'
        )
        series_resp = MagicMock()
        series_resp.content = series_html.encode()
        scraper.web_client.get.return_value = series_resp

        existing_ids = {"88868", "88869"}
        cal_soup = BeautifulSoup(cal_html, "html.parser")
        scraper._get_fases_groups(cal_soup, existing_ids)

        assert scraper._series_url_by_group.get("89477") == series_url, (
            "_series_url_by_group must be populated with the series URL"
        )

    def test_returns_empty_when_cache_miss_and_no_fases_on_page(self, scraper):
        """Cache miss and calendar page without fasesDataList must return []."""
        from unittest.mock import MagicMock, patch

        # No cache entry for this group
        assert "89477" not in scraper._series_url_by_group

        # Fresh requests.get returns page without fasesDataList (neither layout)
        no_fases_html = "<html><body><p>No fases</p></body></html>"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.content = no_fases_html.encode()

        with patch("src.scraper.feb_scraper.requests.get", return_value=mock_resp):
            codes = scraper._get_matches_via_series(
                "https://baloncestoenvivo.feb.es/calendario.aspx?g=9&t=2025&nm=lf2",
                "89477",
            )

        assert codes == []

    def test_slow_path_layout2_direct_link_regression(self, scraper):
        """Regression: slow path must work when cache is empty — rebuilds via
        /resultados/ groups + label matching and retries Series.aspx.

        This covers the case where _get_matches_via_series is called without
        a prior get_groups_for_season call (e.g. direct API use).
        """
        from unittest.mock import MagicMock, call
        from bs4 import BeautifulSoup

        assert "89477" not in scraper._series_url_by_group

        series_url = "https://baloncestoenvivo.feb.es/Series.aspx?f=44785"
        cal_url = "https://baloncestoenvivo.feb.es/calendario.aspx?g=9&t=2025&nm=lf2"

        # /resultados/ response with all groups
        results_html = (
            '<select id="_ctl0_MainContentPlaceHolderMaster_gruposDropDownList">'
            '  <option value="89477">2\u00baA-1\u00baB Final</option>'
            '  <option value="89478">ELIMINATORIAS 1/4 Final</option>'
            '</select>'
        )
        results_resp = MagicMock()
        results_resp.content = results_html.encode()

        # Calendar page with fasesDataList (Layout 2)
        cal_html = (
            '<a id="_ctl0_MainContentPlaceHolderMaster_fasesDataList__ctl0_seriesHyperLink"'
            f' href="{series_url}">2\u00baA-1\u00baB</a>'
        )
        cal_resp = MagicMock()
        cal_resp.content = cal_html.encode()

        # Series.aspx page with match links
        series_resp = MagicMock()
        series_resp.content = str(
            self._series_soup("89477", [("2512420", "58 - 71"), ("2512421", "* - *")])
        ).encode()

        # Calls: [results GET, calendar GET for _build_series_cache, series GET]
        scraper.web_client.get.side_effect = [results_resp, cal_resp, series_resp]

        codes = scraper._get_matches_via_series(cal_url, "89477", season_value="2025")

        assert codes == ["2512420"]
        assert scraper._series_url_by_group.get("89477") == series_url

