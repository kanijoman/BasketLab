"""Calendar references of the recorder's watchlist (issue #458): a calendar URL, optionally with the group to read.

``https://.../calendario.aspx?g=2&t=2026&nm=segundafeb#t=2026&g=89999`` is the calendar of 2ª FEB A: the page of a competition shows one group,
so a plain URL only ever sees the default one. ``g=all`` reads every group the season lists (the phases of the Copa, which appear round by round).
"""
import pytest

from src.scraper import schedule_client
from src.scraper.calendar_parser import CalendarMatch
from src.scraper.schedule_client import calendar_ref, fetch_calendar_ref, split_calendar_ref

URL = "https://baloncestoenvivo.feb.es/calendario.aspx?g=2&t=2026&nm=segundafeb"


def _m(code):
    return CalendarMatch(code, "scheduled", 1, "1", "A", "2", "B", start="2026-10-21T20:00")


def test_a_plain_url_has_no_group():
    assert split_calendar_ref(URL) == (URL, None, None)


def test_a_reference_carries_season_and_group():
    assert split_calendar_ref(URL + "#t=2026&g=89999") == (URL, "2026", "89999")


def test_a_reference_is_built_from_its_parts_and_round_trips():
    assert calendar_ref(URL, "2026", "89999") == URL + "#t=2026&g=89999"
    assert split_calendar_ref(calendar_ref(URL, "2026", "all")) == (URL, "2026", "all")


@pytest.mark.parametrize("ref", [URL + "#g=89999", URL + "#t=2026", URL + "#x=1"])
def test_a_reference_missing_season_or_group_is_rejected(ref):
    with pytest.raises(ValueError, match="t=.*g="):
        split_calendar_ref(ref)


def test_a_plain_url_is_read_as_a_calendar_page(monkeypatch):
    monkeypatch.setattr(schedule_client, "http_calendar", lambda url: [_m(url)])
    assert [m.code for m in fetch_calendar_ref(URL)] == [URL]


def test_a_group_reference_is_read_with_the_group_navigation(monkeypatch):
    monkeypatch.setattr(schedule_client, "http_group_calendar", lambda url, season, group: [_m(f"{url}|{season}|{group}")])
    assert [m.code for m in fetch_calendar_ref(URL + "#t=2026&g=89999")] == [f"{URL}|2026|89999"]


def test_all_groups_reads_each_group_the_season_lists_without_repeating_matches(monkeypatch):
    class Scraper:
        def get_groups_for_season(self, url, season):
            return [("Play-offs 1/16 Final", "1"), ('FASE DE GRUPOS "A"', "2")]

    monkeypatch.setattr("src.scraper.FEBWebScraper", Scraper)
    monkeypatch.setattr(schedule_client, "http_group_calendar", lambda url, season, group: [_m("5"), _m(f"g{group}")])
    assert [m.code for m in fetch_calendar_ref(URL + "#t=2026&g=all")] == ["5", "g1", "g2"]


def test_one_group_failing_does_not_hide_the_others_when_reading_all(monkeypatch):
    class Scraper:
        def get_groups_for_season(self, url, season):
            return [("A", "1"), ("B", "2")]

    def group(url, season, g):
        if g == "1":
            raise ConnectionError("down")
        return [_m("b")]

    monkeypatch.setattr("src.scraper.FEBWebScraper", Scraper)
    monkeypatch.setattr(schedule_client, "http_group_calendar", group)
    assert [m.code for m in fetch_calendar_ref(URL + "#t=2026&g=all")] == ["b"]


def test_the_watchlist_follows_the_teams_of_interest_in_their_groups_and_in_the_copa():
    import json

    watch = json.loads(open("config/feb_watchlist.json", encoding="utf-8").read())
    refs = [split_calendar_ref(r) for r in watch["calendars"]]
    groups = {(url.split("nm=")[1], group) for url, _, group in refs}
    assert {("segundafeb", "89999"), ("segundafeb", "90000"), ("tercerafeb", "90060"), ("copaespaa", "all")} <= groups
    assert {"1008978", "1008857", "1010490"} <= set(watch["teams"])   # Llíria, Cultural y Deportiva Leonesa, CAJA RURAL RDL
