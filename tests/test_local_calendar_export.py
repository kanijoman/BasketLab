"""The calendar of a competition for the web (#842): every match with its round, kick-off and, once played, its score, from the FEB calendar page or the ESB API of FBCYL.

Real data: the FEB page is ``tests/fixtures/feb_calendar_snippet.html`` and the FBCYL calendar the rows of group 7298 read on 9/11/2026. The network is the only thing faked
(``CalendarSource``). A match is identified by what the games use as ``_id`` (the FEB match code, the FBCYL ``universallyid``), so the browser can tell which results it already has in its rows.
"""
import gzip
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

from src.local_data.calendar_export import MAX_STATUS_CHECKS, CalendarSource, calendar_collections, export_calendar  # noqa: E402
from src.local_data.export import export_collection  # noqa: E402
from src.scraper.calendar_parser import CalendarMatch, parse_calendar  # noqa: E402
from tests.test_local_web_data import FBCYL, FEB, cheap_lineups, handler  # noqa: E402,F401  (fixtures)

FIXTURES = Path(__file__).parent / "fixtures"
FEB_PAGE = (FIXTURES / "feb_calendar_snippet.html").read_bytes()


def _fbcyl_rows():
    return json.loads(gzip.open(FIXTURES / "fbcyl_calendar_7298.json.gz", "rt", encoding="utf-8").read())["rows"]


class Fake(CalendarSource):
    """The federation, answering what the test says; ``asked`` lists the status checks."""

    def __init__(self, feb=None, rows=None, statuses=None):
        self._feb, self._rows, self._statuses, self.asked = feb, rows, statuses or {}, []

    def feb(self, handler, collection):
        if isinstance(self._feb, Exception):
            raise self._feb
        return self._feb

    def fbcyl_rows(self, group_id):
        if isinstance(self._rows, Exception):
            raise self._rows
        return self._rows

    def status(self, code):
        self.asked.append(code)
        return self._statuses.get(code, "finished")


def _match(code, kind, rnd, home="1", away="2", score=None, start=None):
    return CalendarMatch(code=code, kind=kind, round_index=rnd, home_id=home, home_name=f"T{home}", away_id=away, away_name=f"T{away}", score=score, start=start)


# ---------------------------------------------------------------------------------------------------- FEB
def test_a_feb_calendar_is_listed_by_round_with_the_code_as_the_match_id_and_the_score_as_numbers(handler):
    payload = export_calendar(Fake(feb=parse_calendar(FEB_PAGE)), handler, FEB)
    assert payload["league"] == "feb" and payload["collection"] == FEB and payload["games"] == 6 and payload["ties_allowed"] is False
    first = payload["matches"][0]
    assert first == {"code": "2524697", "match_id": "2524697", "round": 1, "kind": "result", "start": None,
                     "home": {"id": "1008779", "name": "CB ISLA BONITA SANO SANO CATERING"}, "away": {"id": "1008995", "name": "GRUPO INTERBUS ALCOBENDAS"}, "score": [71, 64]}
    pending = [m for m in payload["matches"] if m["kind"] == "scheduled"]
    assert len(pending) == 3 and all(m["score"] is None and m["start"] and m["round"] == 2 for m in pending)
    assert all(isinstance(m["home"]["id"], str) for m in payload["matches"])


def test_the_order_does_not_depend_on_the_order_the_page_gives_so_an_unchanged_calendar_has_the_same_bytes(handler):
    page = parse_calendar(FEB_PAGE)
    forward, backward = export_calendar(Fake(feb=page), handler, FEB), export_calendar(Fake(feb=list(reversed(page))), handler, FEB)
    assert json.dumps(forward) == json.dumps(backward)
    assert [(m["round"], m["start"] or "", m["code"]) for m in forward["matches"]] == sorted((m["round"], m["start"] or "", m["code"]) for m in forward["matches"])


def test_a_result_that_is_not_in_the_archive_and_is_being_played_is_live_and_one_that_is_in_it_is_never_asked(handler):
    calendar = [_match("9001", "result", 1, score="70-60"), _match("7001", "result", 1, "3", "4", score="10-8"), _match("7002", "result", 1, "5", "6", score="2-0")]
    source = Fake(feb=calendar, statuses={"7001": "live"})
    by_code = {m["code"]: m["kind"] for m in export_calendar(source, handler, FEB)["matches"]}
    assert by_code == {"9001": "result", "7001": "live", "7002": "result"}                  # 9001 is a game of the fixture archive
    assert sorted(source.asked) == ["7001", "7002"]


@pytest.mark.parametrize("answer", ["unknown", "finished", "scheduled"])
def test_a_status_that_does_not_say_live_leaves_the_result_as_it_is(handler, answer):
    source = Fake(feb=[_match("7001", "result", 1, score="10-8")], statuses={"7001": answer})
    assert export_calendar(source, handler, FEB)["matches"][0]["kind"] == "result"


def test_a_status_check_that_fails_leaves_the_result_as_it_is_and_the_publication_goes_on(handler):
    class Broken(Fake):
        def status(self, code):
            raise RuntimeError("the feed is down")

    assert export_calendar(Broken(feb=[_match("7001", "result", 1, score="10-8")]), handler, FEB)["matches"][0]["kind"] == "result"


def test_no_more_than_the_limit_of_status_checks_are_made_in_a_competition(handler):
    calendar = [_match(str(7000 + i), "result", 1, score="1-0") for i in range(MAX_STATUS_CHECKS + 5)]
    source = Fake(feb=calendar)
    export_calendar(source, handler, FEB)
    assert len(source.asked) == MAX_STATUS_CHECKS


def test_a_calendar_that_cannot_be_had_is_nothing_and_never_an_exception(handler, caplog):
    assert export_calendar(Fake(feb=RuntimeError("layout changed")), handler, FEB) is None
    assert FEB in caplog.text and "layout changed" in caplog.text


def test_an_empty_calendar_is_nothing_to_publish(handler):
    assert export_calendar(Fake(feb=[]), handler, FEB) is None


# ---------------------------------------------------------------------------------------------------- FBCYL
def test_the_fbcyl_calendar_identifies_a_match_by_its_uuid_and_keeps_the_kick_off_of_a_played_one():
    payload = export_calendar(Fake(rows=_fbcyl_rows()), None, FBCYL, "7298")
    assert payload["league"] == "fbcyl" and payload["games"] == 156 and payload["ties_allowed"] is False
    row = next(r for r in _fbcyl_rows() if r["idMatch"] == "149374")
    played = next(m for m in payload["matches"] if m["code"] == "fbcyl-149374")
    assert played == {"code": "fbcyl-149374", "match_id": "6ac24423afc7e7e9628cf9d7", "round": int(row["round"]), "kind": "result", "start": "2026-10-04T12:30",
                      "home": {"id": "39675", "name": row["nameLocalTeam"].strip()}, "away": {"id": "40288", "name": row["nameVisitorTeam"].strip()}, "score": [55, 75]}
    assert sum(m["kind"] == "result" for m in payload["matches"]) == 35 and all(m["start"] for m in payload["matches"])


def test_the_fbcyl_ids_of_a_real_game_are_the_ones_of_its_rows_so_the_browser_can_link_them(handler):
    """The match is linked by uuid and the teams by ``teamIdExtern``: what the rows of the game say is what the calendar says (and the local team is the home one)."""
    doc = json.loads(gzip.open(FIXTURES / "fbcyl_game_ok.json.gz", "rt", encoding="utf-8").read())
    doc["_id"] = doc["uuid"]
    handler.connection.client["BASKETBALL"][FBCYL].delete_many({})
    handler.connection.client["BASKETBALL"][FBCYL].insert_one(doc)
    rows = export_collection(handler.connection.client["BASKETBALL"][FBCYL], FBCYL)["team_rows"]
    calendar = next(m for m in export_calendar(Fake(rows=_fbcyl_rows()), handler, FBCYL, "7298")["matches"] if m["code"] == "fbcyl-149374")
    assert {str(r["match_id"]) for r in rows} == {calendar["match_id"]}
    local = next(r for r in rows if r["is_local"])
    assert str(local["team_id"]) == calendar["home"]["id"] and str(next(r for r in rows if not r["is_local"])["team_id"]) == calendar["away"]["id"]


def test_a_group_that_allows_ties_says_so():
    rows = [{**r, "tiedAllowed": "1"} for r in _fbcyl_rows()]
    assert export_calendar(Fake(rows=rows), None, FBCYL, "7298")["ties_allowed"] is True


def test_a_fbcyl_competition_without_a_group_or_with_an_unreadable_calendar_is_nothing(handler):
    assert export_calendar(Fake(rows=_fbcyl_rows()), handler, FBCYL, None) is None
    assert export_calendar(Fake(rows=RuntimeError("no matches")), handler, FBCYL, "7298") is None


# ---------------------------------------------------------------------------------------------------- which competitions
def test_only_the_newest_season_without_knockouts_and_with_a_group_has_a_calendar():
    names = ["SEGUNDA_FEB_2026_2027_Liga_Regular_A", "SEGUNDA_FEB_2025_2026_Liga_Regular_A", "COPA_ESPAÑA_2026_2027_Octavos_de_Final",
             "FBCYL_1ª_FASE-GRUPO_A-1_2026_", "FBCYL_1ª_FASE-GRUPO_A-2_2026_", "FBCYL_1ª_FASE-GRUPO_A-1_2025_"]
    groups = {"FBCYL_1ª_FASE-GRUPO_A-1_2026_": "7298"}
    assert calendar_collections(names, groups) == {"SEGUNDA_FEB_2026_2027_Liga_Regular_A", "FBCYL_1ª_FASE-GRUPO_A-1_2026_"}


def test_the_real_source_asks_the_service_for_the_url_of_the_competition_and_parses_the_page(handler):
    handler.connection.client["BASKETBALL"]["COLLECTION_META"].insert_one({"_id": FEB, "competition_url": "https://example.test/calendario.aspx?g=9"})
    asked = []
    source = CalendarSource(fetch_calendar=lambda url: asked.append(url) or parse_calendar(FEB_PAGE))
    assert len(source.feb(handler, FEB)) == 6 and asked == ["https://example.test/calendario.aspx?g=9"]
