"""Regression tests: multi-bracket playoff phase scraping.

LF2 "1/2 FINAL" has TWO separate Series.aspx pages (one per bracket/matchup).
Both links appear in fasesDataList with the same label.  Before the fix,
_build_series_cache stored only the last matching URL (overwrite semantics),
so only one bracket's games were retrieved.

After the fix, _series_url_by_group maps group_id → List[str], and
_get_matches_via_series visits ALL cached URLs, merging and deduplicating
match codes.
"""

import pytest
from unittest.mock import MagicMock, call
from bs4 import BeautifulSoup

from src.scraper.feb_scraper import FEBWebScraper


# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

def _calendar_html_two_fases_links():
    """Calendar page with two fasesDataList links both labelled '1/2 Final'."""
    return """<html><body>
    <table id="ctl00_MainContentPlaceHolderMaster_fasesDataList">
      <tr>
        <td><a href="https://baloncestoenvivo.feb.es/calendario/Series.aspx?f=11111">1/2 Final</a></td>
        <td><a href="https://baloncestoenvivo.feb.es/calendario/Series.aspx?f=22222">1/2 Final</a></td>
      </tr>
    </table>
    </body></html>"""


def _series_page_html(match_codes):
    """Series.aspx page with completed-score links for each match code."""
    links = "".join(
        f'<a href="partido.aspx?p={code}">{60 + i} - {50 + i}</a>'
        for i, code in enumerate(match_codes)
    )
    return f"<html><body>{links}</body></html>"


def _results_page_html_with_group(group_label, group_id):
    """Results page with a group dropdown containing a single option."""
    return f"""<html><body>
    <select id="_ctl0_MainContentPlaceHolderMaster_gruposDropDownList">
      <option value="{group_id}" selected="selected">{group_label}</option>
    </select>
    </body></html>"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scraper(url_map: dict) -> FEBWebScraper:
    """Create a FEBWebScraper with a mocked WebClient that returns HTML stubs.

    Args:
        url_map: Maps URL string → HTML string (or None to simulate failure).
    """
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
# _build_series_cache — stores multiple URLs per group_id
# ---------------------------------------------------------------------------

class TestBuildSeriesCache:
    """_build_series_cache must collect ALL matching Series.aspx URLs per group."""

    CALENDAR_URL = "https://baloncestoenvivo.feb.es/calendario/lf2/9/2025"
    SERIES_URL_A = "https://baloncestoenvivo.feb.es/calendario/Series.aspx?f=11111"
    SERIES_URL_B = "https://baloncestoenvivo.feb.es/calendario/Series.aspx?f=22222"

    def test_two_fases_links_both_stored_regression(self):
        """When two '1/2 Final' links exist, both URLs must be cached under the same group_id."""
        scraper = _make_scraper({self.CALENDAR_URL: _calendar_html_two_fases_links()})
        groups = [("1/2 Final", "150")]

        scraper._build_series_cache(groups, self.CALENDAR_URL)

        cached = scraper._series_url_by_group.get("150", [])
        assert self.SERIES_URL_A in cached, "First Series.aspx URL must be cached"
        assert self.SERIES_URL_B in cached, "Second Series.aspx URL must be cached"

    def test_single_fases_link_still_works(self):
        """A single fasesDataList link works as before."""
        html = """<html><body>
        <table id="ctl00_MainContentPlaceHolderMaster_fasesDataList">
          <tr><td><a href="https://baloncestoenvivo.feb.es/calendario/Series.aspx?f=99999">Final</a></td></tr>
        </table>
        </body></html>"""
        scraper = _make_scraper({self.CALENDAR_URL: html})
        groups = [("Final", "200")]

        scraper._build_series_cache(groups, self.CALENDAR_URL)

        cached = scraper._series_url_by_group.get("200", [])
        assert len(cached) == 1
        assert "f=99999" in cached[0]

    def test_no_duplicate_urls_stored(self):
        """The same URL appearing twice in fasesDataList must be stored only once."""
        html = """<html><body>
        <table id="ctl00_MainContentPlaceHolderMaster_fasesDataList">
          <tr>
            <td><a href="https://baloncestoenvivo.feb.es/calendario/Series.aspx?f=11111">1/2 Final</a></td>
          </tr>
        </table>
        </body></html>"""
        scraper = _make_scraper({self.CALENDAR_URL: html})
        groups = [("1/2 Final", "150")]

        # Call twice to simulate idempotent behaviour
        scraper._build_series_cache(groups, self.CALENDAR_URL)
        scraper._build_series_cache(groups, self.CALENDAR_URL)

        cached = scraper._series_url_by_group.get("150", [])
        assert len(cached) == 1


# ---------------------------------------------------------------------------
# _get_matches_via_series — visits ALL cached URLs
# ---------------------------------------------------------------------------

class TestGetMatchesViaSeries:
    """_get_matches_via_series must aggregate codes from every cached URL."""

    CALENDAR_URL = "https://baloncestoenvivo.feb.es/calendario/lf2/9/2025"
    SERIES_URL_A = "https://baloncestoenvivo.feb.es/calendario/Series.aspx?f=11111"
    SERIES_URL_B = "https://baloncestoenvivo.feb.es/calendario/Series.aspx?f=22222"

    def test_two_series_urls_all_codes_returned_regression(self):
        """When group has two cached Series.aspx URLs, codes from BOTH are returned.

        Reproduces the LF2 1/2 FINAL bug: 2 games on May 16 + 1 on May 23, only
        the May 23 game was returned before the fix.
        """
        url_map = {
            # Series A: two May-16 games
            self.SERIES_URL_A: _series_page_html(["111111", "222222"]),
            # Series B: one May-23 game
            self.SERIES_URL_B: _series_page_html(["333333"]),
        }
        scraper = _make_scraper(url_map)
        # Pre-populate cache as _build_series_cache would after the fix
        scraper._series_url_by_group["150"] = [self.SERIES_URL_A, self.SERIES_URL_B]

        codes = scraper._get_matches_via_series(self.CALENDAR_URL, "150")

        assert set(codes) == {"111111", "222222", "333333"}, (
            "All three match codes must be returned, not just those from one bracket"
        )

    def test_single_cached_url_still_works(self):
        """When only one URL is cached, behaviour is unchanged."""
        url_map = {self.SERIES_URL_A: _series_page_html(["111111"])}
        scraper = _make_scraper(url_map)
        scraper._series_url_by_group["150"] = [self.SERIES_URL_A]

        codes = scraper._get_matches_via_series(self.CALENDAR_URL, "150")

        assert codes == ["111111"]

    def test_deduplicates_codes_across_pages(self):
        """If the same match code appears on two Series.aspx pages, return it only once."""
        url_map = {
            self.SERIES_URL_A: _series_page_html(["111111", "222222"]),
            self.SERIES_URL_B: _series_page_html(["222222", "333333"]),  # 222222 is duplicate
        }
        scraper = _make_scraper(url_map)
        scraper._series_url_by_group["150"] = [self.SERIES_URL_A, self.SERIES_URL_B]

        codes = scraper._get_matches_via_series(self.CALENDAR_URL, "150")

        assert codes.count("222222") == 1, "Duplicate code must appear only once"
        assert set(codes) == {"111111", "222222", "333333"}

    def test_partial_failure_returns_successful_codes(self):
        """If one Series.aspx fetch fails, codes from the other are still returned."""
        url_map = {
            self.SERIES_URL_A: _series_page_html(["111111"]),
            # SERIES_URL_B is absent → web_client.get returns None
        }
        scraper = _make_scraper(url_map)
        scraper._series_url_by_group["150"] = [self.SERIES_URL_A, self.SERIES_URL_B]

        codes = scraper._get_matches_via_series(self.CALENDAR_URL, "150")

        assert codes == ["111111"], "Codes from the successful page must still be returned"

    def test_empty_cache_returns_empty(self):
        """No cached URLs → empty list returned."""
        scraper = _make_scraper({})
        # _series_url_by_group["150"] is absent

        codes = scraper._get_matches_via_series(self.CALENDAR_URL, "150")

        assert codes == []


# ---------------------------------------------------------------------------
# _get_fases_groups — stores multiple Series.aspx URLs per group
# ---------------------------------------------------------------------------

class TestGetFasesGroups:
    """_get_fases_groups must cache ALL Series.aspx URLs even when group already known."""

    SERIES_URL_A = "https://baloncestoenvivo.feb.es/calendario/Series.aspx?f=11111"
    SERIES_URL_B = "https://baloncestoenvivo.feb.es/calendario/Series.aspx?f=22222"

    def _series_page_with_group(self, group_id):
        return _results_page_html_with_group("1/2 Final", group_id)

    def test_both_series_urls_cached_when_same_group_id(self):
        """Two Series.aspx pages selecting the same group_id → both URLs cached."""
        url_map = {
            self.SERIES_URL_A: self._series_page_with_group("150"),
            self.SERIES_URL_B: self._series_page_with_group("150"),
        }
        calendar_html = _calendar_html_two_fases_links()
        soup = BeautifulSoup(calendar_html, "html.parser")
        scraper = _make_scraper(url_map)

        scraper._get_fases_groups(soup, set())

        cached = scraper._series_url_by_group.get("150", [])
        assert self.SERIES_URL_A in cached
        assert self.SERIES_URL_B in cached
