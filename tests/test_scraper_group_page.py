"""Navigation of ``FEBWebScraper`` to the page of a season and group (issues #449; refactor of ``get_matches``).

``get_matches`` and the calendar of a group (``schedule_client.http_group_calendar``) share one routine that leaves the page showing the season
and group asked for (``FEBWebScraper.group_page``). These tests pin what ``get_matches`` did BEFORE the routine was extracted (they passed on the
old code) and add the corner cases of the routine itself, so the refactor cannot change which pages are requested or posted:

* the page that already shows the selection is used as it is (no postback: the postback of the selected group answers WITHOUT the calendar);
* a different group is selected with one postback, a different season by the year URL or, failing that, by postback;
* a group missing from the dropdown (playoffs) is looked up in the results page;
* nothing is posted when nothing needs selecting; a page that cannot be read gives nothing.
"""
from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup

from src.scraper.feb_scraper import FEBWebScraper
from tests.test_scraper_year_navigation import _future_only_page_html, _make_scraper, _two_group_calendar_html

GROUPS = {"88": "Grupo A", "89": "Grupo B"}
URL = "https://baloncestoenvivo.feb.es/calendario/lf2/9/2026"
URL_2025 = "https://baloncestoenvivo.feb.es/calendario/lf2/9/2025"
RESULTS_2025 = "https://baloncestoenvivo.feb.es/resultados/lf2/9/2025"
A, B = ["100001", "100002"], ["200001", "200002"]


def page(season="2026", group="88", codes=A, groups=None):
    return _two_group_calendar_html(season, group, groups or GROUPS, codes)


def scraper(url_map, post_pages=None):
    """A scraper over canned pages; ``post_pages`` are the answers of the successive POSTs (None = the POST fails)."""
    sc = _make_scraper(url_map)
    answers = list(post_pages or [])

    def post(url, data=None, timeout=None):
        if not answers:
            return None
        html = answers.pop(0)
        if html is None:
            return None
        resp = MagicMock()
        resp.content = html.encode()
        return resp

    sc.web_client.post = MagicMock(side_effect=post)
    sc._merged = MagicMock(side_effect=lambda codes, group, url, soup: codes)
    sc._merge_with_series_codes = sc._merged
    sc._via_series = MagicMock(return_value=["series"])
    sc._get_matches_via_series = sc._via_series
    return sc


def posts(sc):
    """(url, the values of the form) of every POST."""
    return [(c.args[0], set(c.kwargs["data"].values())) for c in sc.web_client.post.call_args_list]


def get_matches(sc, season="2026", group="88", url=URL):
    return sc.get_matches(season, group, season, MagicMock(), url=url)


# --- get_matches: what it did before the extraction -----------------------------------------------------------------------------------

class TestGetMatchesNavigation:
    def test_a_page_that_cannot_be_read_gives_nothing_and_posts_nothing(self):
        sc = scraper({})
        assert get_matches(sc) == [] and sc.web_client.post.call_count == 0

    def test_the_page_that_already_shows_the_selection_is_used_as_it_is(self):
        sc = scraper({URL: page()})
        assert get_matches(sc) == A
        assert sc.web_client.post.call_count == 0 and sc._merged.call_count == 0     # early return: no series merge either

    def test_the_selection_shown_but_without_played_matches_still_posts_nothing_and_goes_on_to_the_series(self):
        sc = scraper({URL: _future_only_page_html("2026", "88")})
        get_matches(sc)
        assert sc.web_client.post.call_count == 0 and sc._merged.call_count == 1

    def test_another_group_is_selected_with_one_postback_of_that_group(self):
        sc = scraper({URL: page()}, post_pages=[page(group="89", codes=B)])
        assert get_matches(sc, group="89") == B
        [(url, values)] = posts(sc)
        assert url == URL and "89" in values and "2026" in values

    def test_the_default_group_requested_explicitly_is_not_posted(self):
        sc = scraper({URL: page()}, post_pages=[page(group="89", codes=B)])
        assert get_matches(sc, group="88") == A and sc.web_client.post.call_count == 0

    def test_another_season_goes_to_the_url_of_that_year_without_a_postback(self):
        sc = scraper({URL: page(), URL_2025: page(season="2025", codes=B)})
        assert get_matches(sc, season="2025", group="88") == B and sc.web_client.post.call_count == 0

    def test_another_season_and_another_group_post_only_the_group_on_the_url_of_that_year(self):
        sc = scraper({URL: page(), URL_2025: page(season="2025")}, post_pages=[page(season="2025", group="89", codes=B)])
        assert get_matches(sc, season="2025", group="89") == B
        [(url, values)] = posts(sc)
        assert url == URL_2025 and "89" in values

    def test_when_the_url_of_that_year_does_not_answer_the_season_is_posted_then_the_group(self):
        sc = scraper({URL: page()}, post_pages=[page(season="2025"), page(season="2025", group="89", codes=B)])
        assert get_matches(sc, season="2025", group="89") == B
        assert [url for url, _ in posts(sc)] == [URL, URL] and "2025" in posts(sc)[0][1] and "89" in posts(sc)[1][1]

    def test_a_group_missing_from_the_dropdown_is_looked_up_in_the_results_page(self):
        """Playoff groups are not in the calendar dropdown: the results page lists them all."""
        results = page(season="2025", group="88", groups={**GROUPS, "90": "Playoff"})
        sc = scraper({URL: page(), URL_2025: page(season="2025"), RESULTS_2025: results}, post_pages=[page(season="2025", group="90", codes=B)])
        assert get_matches(sc, season="2025", group="90") == B
        [(url, values)] = posts(sc)
        assert url == RESULTS_2025 and "90" in values

    def test_a_group_missing_from_the_dropdown_with_no_results_page_posts_on_the_page_it_has(self):
        sc = scraper({URL: page(), URL_2025: page(season="2025")}, post_pages=[page(season="2025", group="90", codes=B)])
        assert get_matches(sc, season="2025", group="90") == B
        assert posts(sc)[0][0] == URL_2025

    def test_a_postback_that_fails_raises(self):
        sc = scraper({URL: page()}, post_pages=[None])
        with pytest.raises(Exception, match="Failed to select group"):
            get_matches(sc, group="89")

    def test_without_url_the_page_of_the_year_is_used(self):
        from src.scraper.feb_scraper import BASE_URL
        from utils import normalize_year  # same helper as get_matches

        base = BASE_URL.format(year=normalize_year("2026"))
        sc = scraper({base: page()})
        assert sc.get_matches("2026", "88", "2026", MagicMock()) == A

    def test_a_page_without_dropdowns_selects_the_season_by_postback(self):
        bare = '<html><body><form><input type="hidden" id="__VIEWSTATE" value="x" /></form></body></html>'
        sc = scraper({URL: bare}, post_pages=[page(), page()])
        get_matches(sc)
        assert sc.web_client.post.call_count >= 1


# --- the shared routine ----------------------------------------------------------------------------------------------------------------

class TestGroupPage:
    def test_it_returns_the_page_with_the_group_selected_and_says_it_needed_no_postback_when_it_was_there(self):
        sc = scraper({URL: page()})
        found = sc.group_page("2026", "88", MagicMock(), URL)
        assert found.shown and sc.web_client.post.call_count == 0
        assert isinstance(found.soup, BeautifulSoup) and found.url == URL and found.calendar_url == URL

    def test_it_returns_the_page_of_another_group_after_one_postback(self):
        sc = scraper({URL: page()}, post_pages=[page(group="89", codes=B)])
        found = sc.group_page("2026", "89", MagicMock(), URL)
        assert not found.shown and sc.web_client.post.call_count == 1
        assert [a["href"] for a in found.soup.find_all("a")] == [f"partido.aspx?p={c}" for c in B]

    def test_the_url_of_the_year_becomes_the_calendar_url_for_the_series(self):
        sc = scraper({URL: page(), URL_2025: page(season="2025")})
        found = sc.group_page("2025", "88", MagicMock(), URL)
        assert found.url == URL_2025 and found.calendar_url == URL_2025 and found.shown

    def test_a_page_that_cannot_be_read_is_none(self):
        assert scraper({}).group_page("2026", "88", MagicMock(), URL) is None

    def test_a_page_with_the_group_shown_is_shown_even_without_played_matches(self):
        """The calendar of a group that has not played yet must be read as it is (the postback would answer without calendar)."""
        sc = scraper({URL: _future_only_page_html("2026", "88")})
        found = sc.group_page("2026", "88", MagicMock(), URL)
        assert found.shown and sc.web_client.post.call_count == 0

    def test_a_page_without_group_dropdown_is_returned_as_it_is_for_a_calendar(self):
        """A single-group competition has no group selector: for a calendar the page already is the group."""
        html = '<html><body><form></form><select id="_ctl0_MainContentPlaceHolderMaster_temporadasDropDownList"><option value="2026" selected="selected">2026</option></select></body></html>'
        sc = scraper({URL: html})
        found = sc.group_page("2026", "89981", MagicMock(), URL, single_group_ok=True)
        assert found is not None and found.shown and sc.web_client.post.call_count == 0
