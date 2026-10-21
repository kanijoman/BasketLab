"""Calendar of a knockout group read from ``Series.aspx`` (issue #456), through the real facade over canned pages.

The Copa de España has one series page for all its phases and one group per phase (``Play-offs 1/16 Final``): the calendar of the group is
the ties of its phase. Groups whose name is not a phase (``2ºA-1ºB Final`` of LF2) take every tie of their series pages.
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.scraper import FEBWebScraper as Facade, schedule_client
from src.scraper.calendar_parser import parse_series
from src.scraper.constants import GROUP_DROPDOWN_ID, SEASON_DROPDOWN_ID
from src.scraper.feb_scraper import FEBWebScraper

SERIES = (Path(__file__).parent / "fixtures" / "feb_series_copa.html").read_bytes()
URL = "https://baloncestoenvivo.feb.es/calendario.aspx?g=73&t=2026&nm=copaespaa"
SERIES_URL = "https://baloncestoenvivo.feb.es/Series.aspx?f=45116"
GROUPS = (("Play-offs 1/16 Final", "90041"), ('FASE DE GRUPOS "A"', "90033"))


def results_page(selected="90041"):
    """``resultados.aspx`` of a knockout group: the dropdowns, no calendar tables, and the link to the series page."""
    options = "".join(f'<option value="{v}"{" selected" if v == selected else ""}>{t}</option>' for t, v in GROUPS)
    return (f'<select id="{SEASON_DROPDOWN_ID}"><option value="2026" selected>2026</option></select>'
            f'<select id="{GROUP_DROPDOWN_ID}">{options}</select>'
            f'<table id="x_fasesDataList"><tr><td><a href="{SERIES_URL}">Play-offs</a></td></tr></table>').encode()


class Site:
    def __init__(self, pages):
        self.pages = pages
        self.web_client = MagicMock()
        self.web_client.get.side_effect = lambda url, timeout=None: MagicMock(content=self.pages[url]) if url in self.pages else None
        self.web_client.post.side_effect = lambda url, data=None, timeout=None: MagicMock(content=results_page())
        self.web_client.get_session.return_value = "session"
        self.scraper = Facade()
        self.scraper.web_client = self.web_client
        self.scraper.web_scraper = FEBWebScraper(self.web_client)

    def install(self, monkeypatch):
        monkeypatch.setattr("src.scraper.FEBWebScraper", lambda: self.scraper)
        return self


RESULTS_URL = "https://baloncestoenvivo.feb.es/resultados.aspx?g=73&t=2026&nm=copaespaa"


@pytest.fixture(autouse=True)
def clean_cache():
    schedule_client._CALENDAR_CACHE.clear()


def copa(monkeypatch, series=SERIES, results=None):
    pages = {URL: results or results_page(), RESULTS_URL: results or results_page(), SERIES_URL: series}
    return Site(pages).install(monkeypatch)


def test_the_calendar_of_a_knockout_group_is_read_from_its_series_page(monkeypatch):
    copa(monkeypatch)
    matches = schedule_client.http_group_calendar(URL, "2026", "90041")
    assert [m.code for m in matches] == ["2543131", "2543132", "2543134", "2543136"]
    assert {m.kind for m in matches} == {"result", "scheduled"}


def test_only_the_ties_of_the_phase_of_the_group_are_kept(monkeypatch):
    """One series page holds every phase of the Copa: the group ``Play-offs 1/16 Final`` must not take the 1/8 ties."""
    later = SERIES + b'<h1 class="titulo-modulo">1/8 Final. A - B</h1><table><tr><td><a href="x/Equipo.aspx?i=1">A</a> - <a href="x/Equipo.aspx?i=2">B</a></td>' \
                     b'<td><a href="x/Partido.aspx?p=999">* - *</a></td><td>01/11/2026 20:00</td></tr></table>'
    copa(monkeypatch, series=later)
    assert "999" not in [m.code for m in schedule_client.http_group_calendar(URL, "2026", "90041")]


def test_the_final_is_not_taken_by_the_group_of_the_1_16_regression(monkeypatch):
    """The phase ``Final`` is contained in the label ``Play-offs 1/16 Final``: only the most specific phase of the label counts."""
    final = SERIES + b'<h1 class="titulo-modulo">Final. A - B</h1><table><tr><td><a href="x/Equipo.aspx?i=1">A</a> - <a href="x/Equipo.aspx?i=2">B</a></td>'                      b'<td><a href="x/Partido.aspx?p=777">* - *</a></td><td>01/12/2026 20:00</td></tr></table>'
    copa(monkeypatch, series=final)
    assert "777" not in [m.code for m in schedule_client.http_group_calendar(URL, "2026", "90041")]


def test_a_group_that_is_not_a_phase_takes_every_tie_of_its_series_pages(monkeypatch):
    """LF2 style: the group ``2ºA-1ºB Final`` has no phase text in common with the ties titles."""
    groups = (("2ºA-1ºB Final", "90041"),)
    options = "".join(f'<option value="{v}" selected>{t}</option>' for t, v in groups)
    page = (f'<select id="{SEASON_DROPDOWN_ID}"><option value="2026" selected>2026</option></select>'
            f'<select id="{GROUP_DROPDOWN_ID}">{options}</select><table id="x_fasesDataList"><tr><td><a href="{SERIES_URL}">2ºA-1ºB</a></td></tr></table>').encode()
    copa(monkeypatch, results=page)
    assert len(schedule_client.http_group_calendar(URL, "2026", "90041")) == 4


def test_a_group_with_a_calendar_does_not_touch_the_series(monkeypatch):
    from tests.test_group_calendar_client import CALENDAR, page

    site = Site({URL: page(selected="89999")}).install(monkeypatch)
    assert schedule_client.http_group_calendar(URL, "2026", "89999")
    assert SERIES_URL not in [c.args[0] for c in site.web_client.get.call_args_list]


def test_a_phase_not_drawn_yet_is_an_empty_calendar_not_an_error(monkeypatch):
    copa(monkeypatch, series=b"<html><body></body></html>")
    assert schedule_client.http_group_calendar(URL, "2026", "90041") == []


def test_a_group_without_series_pages_is_an_empty_calendar(monkeypatch):
    results = results_page().replace(SERIES_URL.encode(), b"")
    copa(monkeypatch, results=results.replace(b"<a href=\"\">Play-offs</a>", b""))
    assert schedule_client.http_group_calendar(URL, "2026", "90041") == []


def test_the_calendar_is_cached_per_group(monkeypatch):
    site = copa(monkeypatch)
    schedule_client.http_group_calendar(URL, "2026", "90041")
    calls = site.web_client.get.call_count
    schedule_client.http_group_calendar(URL, "2026", "90041")
    assert site.web_client.get.call_count == calls


def test_next_rounds_and_upcoming_work_on_the_series_matches_of_the_copa_regression():
    """Bug of 2026-10-21: the Copa had no calendar, so the matches of the day (Llíria, Cultural Leonesa) were not found."""
    from tests.test_match_schedule_service import _rounds, _service
    from datetime import datetime

    matches = parse_series(SERIES)
    rounds, out = _rounds(matches, now="2026-10-21T09:00")
    assert rounds == {1: ["2543132", "2543134", "2543136"]} and out["warning"] is None
    upcoming = _service(calendar=matches, now=datetime(2026, 10, 21, 9, 0)).upcoming("LF_CHALLENGE_2026", "1008978")
    assert [m["code"] for m in upcoming["matches"]] == ["2543134"]
