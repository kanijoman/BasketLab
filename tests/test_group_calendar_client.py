"""Calendar of one group of a competition (issue #449): ``http_group_calendar`` on top of the scraper's own navigation (``group_page``).

The page-level behaviour (what is requested and posted) is pinned in ``test_scraper_group_page.py``; here the client is checked as a whole over
canned pages: the real ``FEBWebScraper`` with a mocked web client, and the parser of the calendar.
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.scraper import FEBWebScraper as Facade, schedule_client
from src.scraper.calendar_parser import parse_calendar
from src.scraper.constants import GROUP_DROPDOWN_ID, SEASON_DROPDOWN_ID
from src.scraper.feb_scraper import FEBWebScraper

CALENDAR = (Path(__file__).parent / "fixtures" / "feb_calendar_snippet.html").read_bytes()
CODES = [m.code for m in parse_calendar(CALENDAR)]
URL = "https://baloncestoenvivo.feb.es/calendario.aspx?g=2&t=2026&nm=segundafeb"


def page(selected="89999", dropdown=True, season="2026"):
    """The page of the competition: the calendar of the group that is selected (A) and the dropdowns of its season and groups."""
    options = "".join(f'<option value="{v}"{" selected" if v == selected else ""}>{t}</option>' for t, v in (("A", "89999"), ("B", "90000")))
    groups = f'<select id="{GROUP_DROPDOWN_ID}">{options}</select>' if dropdown else ""
    seasons = f'<select id="{SEASON_DROPDOWN_ID}"><option value="{season}" selected>{season}</option></select>'
    return (seasons + groups).encode() + CALENDAR


class Site:
    """A mocked FEB site: GET returns ``html``; POST (the group postback) answers the calendar of the group that was posted."""

    def __init__(self, html, post=CALENDAR):
        self.web_client = MagicMock()
        self.web_client.get.side_effect = lambda url, timeout=None: None if html is None else MagicMock(content=html)
        self.web_client.post.side_effect = lambda url, data=None, timeout=None: None if post is None else MagicMock(content=post)
        self.web_client.get_session.return_value = "session"
        # the real facade that schedule_client builds (src.scraper.FEBWebScraper), over the mocked client
        self.scraper = Facade()
        self.scraper.web_client = self.web_client
        self.scraper.web_scraper = FEBWebScraper(self.web_client)

    def install(self, monkeypatch):
        monkeypatch.setattr("src.scraper.FEBWebScraper", lambda: self.scraper)
        return self


@pytest.fixture(autouse=True)
def clean_cache():
    schedule_client._CALENDAR_CACHE.clear()


def test_another_group_is_selected_with_the_postback_and_the_answer_is_parsed(monkeypatch):
    site = Site(page(selected="89999")).install(monkeypatch)
    assert [m.code for m in schedule_client.http_group_calendar(URL, "2026", "90000")] == CODES
    assert site.web_client.post.call_count == 1
    assert "90000" in site.web_client.post.call_args.kwargs["data"].values()


def test_the_group_that_the_page_already_shows_is_read_without_a_postback_regression(monkeypatch):
    """Bug found trying it on the real site: selecting the group that is already selected answers a page WITHOUT the calendar (0 matches) for the
    default groups (2ª FEB A, LF Challenge); the page as it is already has their calendar."""
    site = Site(page(selected="89999"), post=b"<html></html>").install(monkeypatch)
    assert [m.code for m in schedule_client.http_group_calendar(URL, "2026", "89999")] == CODES
    assert site.web_client.post.call_count == 0


def test_a_competition_page_without_group_dropdown_is_read_as_it_is(monkeypatch):
    site = Site(page(dropdown=False), post=b"<html></html>").install(monkeypatch)
    assert [m.code for m in schedule_client.http_group_calendar(URL, "2026", "89981")] == CODES
    assert site.web_client.post.call_count == 0


def test_another_season_goes_through_the_same_navigation_as_the_scraper(monkeypatch):
    """The season of the page is not the one asked for: the URL of that year is requested (the navigation of ``get_matches``)."""
    old = "https://baloncestoenvivo.feb.es/calendario.aspx?g=2&t=2025&nm=segundafeb"
    site = Site(None)
    site.web_client.get.side_effect = lambda url, timeout=None: MagicMock(content=page(season="2025")) if url == old else MagicMock(content=page(season="2026"))
    site.install(monkeypatch)
    assert [m.code for m in schedule_client.http_group_calendar(URL, "2025", "89999")] == CODES
    assert old in [c.args[0] for c in site.web_client.get.call_args_list]


def test_a_page_that_cannot_be_read_raises_so_the_caller_can_say_it(monkeypatch):
    Site(None).install(monkeypatch)
    with pytest.raises(ConnectionError):
        schedule_client.http_group_calendar(URL, "2026", "90000")


def test_a_postback_that_fails_raises_and_is_not_cached(monkeypatch):
    Site(page(), post=None).install(monkeypatch)
    with pytest.raises(Exception, match="Failed to select group"):
        schedule_client.http_group_calendar(URL, "2026", "90000")
    assert not schedule_client._CALENDAR_CACHE


def test_each_group_has_its_own_cache_entry_for_a_minute(monkeypatch):
    site = Site(page()).install(monkeypatch)
    schedule_client.http_group_calendar(URL, "2026", "90000")
    schedule_client.http_group_calendar(URL, "2026", "90000")          # cached: no second request
    assert site.web_client.get.call_count == 1 and site.web_client.post.call_count == 1
    schedule_client.http_group_calendar(URL, "2026", "89999")          # another group of the same page: its own entry
    assert site.web_client.get.call_count == 2


def test_the_cache_does_not_mix_the_plain_page_with_a_group(monkeypatch):
    """The plain calendar of the URL and the calendar of a group are different entries of the same cache."""
    Site(page()).install(monkeypatch)
    schedule_client.http_group_calendar(URL, "2026", "89999")
    assert (URL, "2026", "89999") in schedule_client._CALENDAR_CACHE and URL not in schedule_client._CALENDAR_CACHE
