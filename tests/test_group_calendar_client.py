"""Calendar of one group of a competition (issue #449): the page shows one group; another one is selected with the ASP.NET postback."""
from pathlib import Path

from bs4 import BeautifulSoup

from src.scraper import schedule_client
from src.scraper.calendar_parser import parse_calendar
from src.scraper.constants import GROUP_DROPDOWN_ID

CALENDAR = (Path(__file__).parent / "fixtures" / "feb_calendar_snippet.html").read_bytes()
URL = "https://baloncestoenvivo.feb.es/calendario.aspx?g=2&t=2026&nm=segundafeb"


def page(selected="89999", dropdown=True):
    """The page of the competition: the calendar of the group that is selected (A) and the dropdown of its groups."""
    options = "".join(f'<option value="{v}"{" selected" if v == selected else ""}>{t}</option>' for t, v in (("A", "89999"), ("B", "90000")))
    select = f'<select id="{GROUP_DROPDOWN_ID}">{options}</select>' if dropdown else ""
    return select.encode() + CALENDAR


class FakeScraper:
    instances = []

    def __init__(self, html=None):
        self.calls, self.gets = [], 0
        FakeScraper.instances.append(self)
        outer = self
        self.web_client = type("W", (), {"get": lambda _s, url, **kw: outer._get(), "get_session": staticmethod(lambda: "session")})()

    html = page()

    def _get(self):
        self.gets += 1
        return type("R", (), {"content": type(self).html})()

    def get_hidden_fields(self, soup):
        return {"__VIEWSTATE": "x"}

    def select_group(self, session, url, season, group, hidden):
        self.calls.append((session, url, season, group, hidden))
        return BeautifulSoup(CALENDAR, "html.parser")


def run(monkeypatch, group, html=None):
    schedule_client._CALENDAR_CACHE.clear()
    FakeScraper.instances.clear()
    FakeScraper.html = html or page()
    monkeypatch.setattr("src.scraper.FEBWebScraper", FakeScraper)
    return schedule_client.http_group_calendar(URL, "2026", group)


def test_another_group_is_selected_with_the_postback_and_the_answer_is_parsed(monkeypatch):
    matches = run(monkeypatch, "90000")
    assert matches and [m.code for m in matches] == [m.code for m in parse_calendar(CALENDAR)]
    assert FakeScraper.instances[0].calls == [("session", URL, "2026", "90000", {"__VIEWSTATE": "x"})]


def test_the_group_that_the_page_already_shows_is_read_without_a_postback_regression(monkeypatch):
    """Bug found trying it on the real site: selecting the group that is already selected answers a page WITHOUT the calendar (0 matches) for
    the default groups (2ª FEB A, LF Challenge); the page as it is already has their calendar."""
    matches = run(monkeypatch, "89999")
    assert matches and FakeScraper.instances[0].calls == []


def test_a_competition_page_without_group_dropdown_is_read_as_it_is(monkeypatch):
    assert run(monkeypatch, "89981", html=page(dropdown=False)) and FakeScraper.instances[0].calls == []


def test_each_group_has_its_own_cache_entry_for_a_minute(monkeypatch):
    run(monkeypatch, "90000")
    schedule_client.http_group_calendar(URL, "2026", "90000")          # cached: no second request
    schedule_client.http_group_calendar(URL, "2026", "89999")          # another group of the same page: its own entry
    assert len(FakeScraper.instances) == 2
