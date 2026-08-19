"""Regression tests: direct year-URL navigation when competition URL year differs from season.

Bug: get_feb_competitions() returns the competition URL with the CURRENT season year
embedded (e.g. /lfchallenge/67/2026 for the 2026/27 setup page).  When the user
selects the PREVIOUS season (value "2025") the scraper was POSTing an ASP.NET
season-select request on the wrong-year page instead of navigating directly to
/lfchallenge/67/2025, which caused 0 matches to be returned.

Affects all competitions (LF Challenge, LF ENDESA, LF2, etc.) whenever the
competition URL points to a newer season than the one requested.

Fix: When the pretty URL or ASPX URL contains a year that differs from
season_value, derive the correct calendar URL by substituting the year and GET it
directly before falling back to the POST-based ASP.NET season selection.
"""

import pytest
from unittest.mock import MagicMock
from bs4 import BeautifulSoup

from src.scraper.feb_scraper import FEBWebScraper


# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

_VIEWSTATE = "AAABBBCCC=="


def _calendar_page_html(season_value: str, group_value: str, match_codes: list) -> str:
    """Full calendario page with season/group dropdowns and completed-match links."""
    links = "".join(
        f'<a href="partido.aspx?p={c}">{60 + i} - {50 + i}</a>'
        for i, c in enumerate(match_codes)
    )
    return (
        f'<html><body>'
        f'<form>'
        f'<input type="hidden" id="__VIEWSTATE" value="{_VIEWSTATE}" />'
        f'<input type="hidden" id="__VIEWSTATEGENERATOR" value="XYZ" />'
        f'<input type="hidden" id="__EVENTVALIDATION" value="EVV" />'
        f'</form>'
        f'<select id="_ctl0_MainContentPlaceHolderMaster_temporadasDropDownList">'
        f'<option value="2026">2026/2027</option>'
        f'<option value="{season_value}" selected="selected">{season_value}/{int(season_value)+1}</option>'
        f'</select>'
        f'<select id="_ctl0_MainContentPlaceHolderMaster_gruposDropDownList">'
        f'<option value="{group_value}" selected="selected">Liga Regular</option>'
        f'</select>'
        f'{links}'
        f'</body></html>'
    )


def _future_only_page_html(season_value: str = "2026", group_value: str = "67") -> str:
    """Calendar page showing future (unplayed) matches only – no p= links."""
    return (
        f'<html><body>'
        f'<form>'
        f'<input type="hidden" id="__VIEWSTATE" value="{_VIEWSTATE}" />'
        f'<input type="hidden" id="__VIEWSTATEGENERATOR" value="XYZ" />'
        f'<input type="hidden" id="__EVENTVALIDATION" value="EVV" />'
        f'</form>'
        f'<select id="_ctl0_MainContentPlaceHolderMaster_temporadasDropDownList">'
        f'<option value="{season_value}" selected="selected">{season_value}/{int(season_value)+1}</option>'
        f'<option value="2025">2025/2026</option>'
        f'</select>'
        f'<select id="_ctl0_MainContentPlaceHolderMaster_gruposDropDownList">'
        f'<option value="{group_value}" selected="selected">Liga Regular</option>'
        f'</select>'
        f'<p>JORNADA 1 - sin resultado</p>'
        f'</body></html>'
    )


def _make_scraper(url_map: dict) -> FEBWebScraper:
    """Scraper with a mocked WebClient that returns canned HTML responses."""
    web_client = MagicMock()

    def _get(url, timeout=None):
        html = url_map.get(url)
        if html is None:
            return None
        resp = MagicMock()
        resp.content = html.encode()
        return resp

    web_client.get.side_effect = _get
    web_client.get_session.return_value = MagicMock()
    return FEBWebScraper(web_client)


# ---------------------------------------------------------------------------
# Tests: get_matches navigates to the correct year URL
# ---------------------------------------------------------------------------

class TestGetMatchesYearNavigation:
    """get_matches must navigate to the correct year URL when competition URL
    year differs from the requested season_value.

    Reproduces the LF Challenge / LF ENDESA bug: the competition dropdown returns
    a URL with the CURRENT season year, but the user wants an OLDER completed season.
    """

    COMP_URL_2026 = "https://baloncestoenvivo.feb.es/calendario/lfchallenge/67/2026"
    COMP_URL_2025 = "https://baloncestoenvivo.feb.es/calendario/lfchallenge/67/2025"

    def test_returns_matches_from_correct_year_url_regression(self):
        """When competition URL has year 2026 but season_value is '2025',
        matches from /lfchallenge/67/2025 must be returned (not 0).

        Primary regression for LF Challenge / LF ENDESA 2025/26 bug.
        """
        url_map = {
            self.COMP_URL_2026: _future_only_page_html("2026", "67"),
            self.COMP_URL_2025: _calendar_page_html("2025", "67", ["111111", "222222"]),
        }
        scraper = _make_scraper(url_map)

        codes = scraper.get_matches(
            season_value="2025",
            group_value="67",
            year="2025",
            session=MagicMock(),
            url=self.COMP_URL_2026,
        )

        assert set(codes) == {"111111", "222222"}, (
            "Should find matches from /lfchallenge/67/2025, not 0 from /2026"
        )

    def test_correct_year_url_is_fetched_directly(self):
        """The scraper must GET /lfchallenge/67/2025 (not just POST on /2026)."""
        url_map = {
            self.COMP_URL_2026: _future_only_page_html("2026", "67"),
            self.COMP_URL_2025: _calendar_page_html("2025", "67", ["999888"]),
        }
        scraper = _make_scraper(url_map)

        scraper.get_matches(
            season_value="2025",
            group_value="67",
            year="2025",
            session=MagicMock(),
            url=self.COMP_URL_2026,
        )

        fetched_urls = [call_args[0][0] for call_args in scraper.web_client.get.call_args_list]
        assert self.COMP_URL_2025 in fetched_urls, (
            "get_matches must request the /2025 URL directly"
        )

    def test_same_year_url_skips_direct_navigation(self):
        """When URL year already matches season_value, no extra GET is needed."""
        url_map = {
            self.COMP_URL_2025: _calendar_page_html("2025", "67", ["555555"]),
        }
        scraper = _make_scraper(url_map)

        codes = scraper.get_matches(
            season_value="2025",
            group_value="67",
            year="2025",
            session=MagicMock(),
            url=self.COMP_URL_2025,
        )

        assert "555555" in codes
        get_calls = [c[0][0] for c in scraper.web_client.get.call_args_list]
        assert get_calls.count(self.COMP_URL_2025) == 1

    def test_aspx_url_with_wrong_year_navigates_correctly(self):
        """ASPX URL with t=2026 but season_value='2025' is also handled.

        Reproduces the LF ENDESA bug: competition URL is ASPX format with t=2026.
        """
        aspx_2026 = "https://baloncestoenvivo.feb.es/calendario.aspx?g=67&t=2026&nm=lfchallenge"
        aspx_2025 = "https://baloncestoenvivo.feb.es/calendario.aspx?g=67&t=2025&nm=lfchallenge"
        url_map = {
            aspx_2026: _future_only_page_html("2026", "67"),
            aspx_2025: _calendar_page_html("2025", "67", ["777777"]),
        }
        scraper = _make_scraper(url_map)

        codes = scraper.get_matches(
            season_value="2025",
            group_value="67",
            year="2025",
            session=MagicMock(),
            url=aspx_2026,
        )

        assert "777777" in codes

    def test_no_group_post_when_year_url_has_matches(self):
        """After direct year navigation finds matches, no group-select POST is needed.

        Prevents failures on pages that embed the group in the URL path and have
        no ASP.NET group dropdown requiring a POST to select.
        """
        url_map = {
            self.COMP_URL_2026: _future_only_page_html("2026", "67"),
            self.COMP_URL_2025: _calendar_page_html("2025", "67", ["111111"]),
        }
        scraper = _make_scraper(url_map)
        scraper.web_client.post = MagicMock()

        scraper.get_matches(
            season_value="2025",
            group_value="67",
            year="2025",
            session=MagicMock(),
            url=self.COMP_URL_2026,
        )

        scraper.web_client.post.assert_not_called()

    def test_original_calendar_url_updated_for_series_aspx_cache(self):
        """After year navigation, _merge_with_series_codes uses the correct-year URL.

        Realistic case: a *playoff* group has Series.aspx links on the page but
        no direct partido.aspx match links (all results are inside the Series page).
        The early-exit does NOT trigger (no direct matches), so _merge_with_series_codes
        is called.  It must use original_calendar_url = /2025, not the stale /2026,
        to build the Series.aspx cache.  If /2026 were used, its fasesDataList is
        empty (future-only page) → 0 matches; if /2025 is used → Series.aspx fetched.
        """
        series_url = "https://baloncestoenvivo.feb.es/calendario/Series.aspx?f=55555"
        # Playoff calendar page: fasesDataList with Series.aspx but NO partido.aspx links.
        cal_2025_playoff = (
            '<html><body>'
            '<select id="_ctl0_MainContentPlaceHolderMaster_temporadasDropDownList">'
            '<option value="2025" selected="selected">2025/2026</option>'
            '</select>'
            '<select id="_ctl0_MainContentPlaceHolderMaster_gruposDropDownList">'
            '<option value="67" selected="selected">Final</option>'
            '</select>'
            '<table id="ctl00_MainContentPlaceHolderMaster_fasesDataList">'
            f'<tr><td><a href="{series_url}">Final</a></td></tr>'
            '</table>'
            '</body></html>'
        )
        series_html = '<html><body><a href="partido.aspx?p=999999">81 - 70</a></body></html>'
        url_map = {
            self.COMP_URL_2026: _future_only_page_html("2026", "67"),
            self.COMP_URL_2025: cal_2025_playoff,
            series_url: series_html,
        }
        scraper = _make_scraper(url_map)

        codes = scraper.get_matches(
            season_value="2025",
            group_value="67",
            year="2025",
            session=MagicMock(),
            url=self.COMP_URL_2026,
        )

        # Series.aspx must be fetched because original_calendar_url was updated to /2025
        fetched_urls = [c[0][0] for c in scraper.web_client.get.call_args_list]
        assert series_url in fetched_urls, (
            "Series.aspx must be fetched — original_calendar_url must point to /2025, not /2026"
        )
        assert "999999" in codes

    def test_direct_navigation_falls_back_to_post_when_year_url_not_found(self):
        """If the year-substituted URL returns None, fall back to POST season select.

        The POST is the only remaining path; if it succeeds, return matches from it.
        """
        post_response = MagicMock()
        post_response.content = _calendar_page_html("2025", "67", ["444444"]).encode()
        url_map = {
            self.COMP_URL_2026: _future_only_page_html("2026", "67"),
            # /2025 URL unavailable — returns None to force POST fallback
        }
        scraper = _make_scraper(url_map)
        scraper.web_client.post = MagicMock(return_value=post_response)

        codes = scraper.get_matches(
            season_value="2025",
            group_value="67",
            year="2025",
            session=MagicMock(),
            url=self.COMP_URL_2026,
        )

        scraper.web_client.post.assert_called_once()
        assert "444444" in codes


# ---------------------------------------------------------------------------
# Tests: _derive_seasonal_url helper
# ---------------------------------------------------------------------------

class TestDeriveSeasonalUrl:
    """Unit tests for the _derive_seasonal_url static helper."""

    def test_pretty_url_year_substituted(self):
        from src.scraper.feb_scraper import FEBWebScraper
        result = FEBWebScraper._derive_seasonal_url(
            "https://baloncestoenvivo.feb.es/calendario/lfchallenge/67/2026", "2025"
        )
        assert result == "https://baloncestoenvivo.feb.es/calendario/lfchallenge/67/2025"

    def test_aspx_t_param_substituted(self):
        from src.scraper.feb_scraper import FEBWebScraper
        result = FEBWebScraper._derive_seasonal_url(
            "https://baloncestoenvivo.feb.es/calendario.aspx?g=4&t=2026&nm=lfendesa", "2025"
        )
        assert result == "https://baloncestoenvivo.feb.es/calendario.aspx?g=4&t=2025&nm=lfendesa"

    def test_same_year_returns_same_url(self):
        from src.scraper.feb_scraper import FEBWebScraper
        url = "https://baloncestoenvivo.feb.es/calendario/lf2/9/2025"
        assert FEBWebScraper._derive_seasonal_url(url, "2025") == url

    def test_url_without_year_pattern_unchanged(self):
        from src.scraper.feb_scraper import FEBWebScraper
        url = "https://baloncestoenvivo.feb.es/home.aspx"
        assert FEBWebScraper._derive_seasonal_url(url, "2025") == url

    def test_lf_endesa_pretty_url(self):
        from src.scraper.feb_scraper import FEBWebScraper
        result = FEBWebScraper._derive_seasonal_url(
            "https://baloncestoenvivo.feb.es/calendario/lfendesa/4/2026", "2025"
        )
        assert result == "https://baloncestoenvivo.feb.es/calendario/lfendesa/4/2025"


# ---------------------------------------------------------------------------
# Tests: get_groups_for_season derives correct resultados URL
# ---------------------------------------------------------------------------

class TestGetGroupsForSeasonYearNavigation:
    """get_groups_for_season uses _calendar_to_results_url to substitute the year
    correctly — verify this works for both URL formats."""

    def _groups_page_html(self, group_value: str, group_label: str) -> str:
        return (
            f'<html><body>'
            f'<select id="_ctl0_MainContentPlaceHolderMaster_gruposDropDownList">'
            f'<option value="{group_value}" selected="selected">{group_label}</option>'
            f'</select>'
            f'</body></html>'
        )

    def test_pretty_url_2026_season_2025_fetches_resultados_2025(self):
        results_url = "https://baloncestoenvivo.feb.es/resultados/lfchallenge/67/2025"
        url_map = {results_url: self._groups_page_html("67", "Liga Regular")}
        scraper = _make_scraper(url_map)

        groups = scraper.get_groups_for_season(
            "https://baloncestoenvivo.feb.es/calendario/lfchallenge/67/2026",
            "2025",
        )

        assert groups == [("Liga Regular", "67")]
        fetched = [c[0][0] for c in scraper.web_client.get.call_args_list]
        assert results_url in fetched

    def test_aspx_url_2026_season_2025_fetches_resultados_2025(self):
        results_url = "https://baloncestoenvivo.feb.es/resultados.aspx?g=67&t=2025&nm=lfchallenge"
        url_map = {results_url: self._groups_page_html("67", "Liga Regular")}
        scraper = _make_scraper(url_map)

        groups = scraper.get_groups_for_season(
            "https://baloncestoenvivo.feb.es/calendario.aspx?g=67&t=2026&nm=lfchallenge",
            "2025",
        )

        assert groups == [("Liga Regular", "67")]
        fetched = [c[0][0] for c in scraper.web_client.get.call_args_list]
        assert results_url in fetched

    def test_lfendesa_aspx_2026_season_2025(self):
        """LF ENDESA-specific regression: g=4, nm=lfendesa."""
        results_url = "https://baloncestoenvivo.feb.es/resultados.aspx?g=4&t=2025&nm=lfendesa"
        url_map = {results_url: self._groups_page_html("4", "LF ENDESA Regular")}
        scraper = _make_scraper(url_map)

        groups = scraper.get_groups_for_season(
            "https://baloncestoenvivo.feb.es/calendario.aspx?g=4&t=2026&nm=lfendesa",
            "2025",
        )

        assert groups == [("LF ENDESA Regular", "4")]
