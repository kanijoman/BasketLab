"""FEB calendar parser: keeps the matches that have NOT been played (issue #119).

The scraper only needs finished matches; the live feature needs the upcoming ones too.
Fixture: a trimmed copy of the real https://baloncestoenvivo.feb.es/calendario/lfchallenge/9/2026
(finished results in round 1, dated matches in round 2).
"""
from pathlib import Path

import pytest

from src.scraper.calendar_parser import CalendarMatch, parse_calendar

HTML = (Path(__file__).parent / "fixtures" / "feb_calendar_snippet.html").read_bytes()


@pytest.fixture(scope="module")
def matches():
    return parse_calendar(HTML)


def test_keeps_every_row_finished_or_not(matches):
    assert [m.code for m in matches] == ["2524697", "2524698", "2524699", "2524704", "2524705", "2524706"]


def test_finished_rows_carry_the_score_and_no_start(matches):
    m = matches[0]
    assert m.kind == "result" and m.score == "71-64" and m.start is None
    assert (m.home_id, m.home_name) == ("1008779", "CB ISLA BONITA SANO SANO CATERING")
    assert (m.away_id, m.away_name) == ("1008995", "GRUPO INTERBUS ALCOBENDAS")


def test_unplayed_rows_carry_the_kick_off_time(matches):
    m = matches[3]
    assert m.kind == "scheduled" and m.score is None
    assert m.start is not None and len(m.start) == 16 and m.start[10] == "T"  # "YYYY-MM-DDTHH:MM", Madrid local time


def test_the_date_is_parsed_into_iso_local_time():
    html = ('<div class="tableLayout de dos columnas"><table><tr><th>Local</th></tr><tr>'
            '<td class="equipo local"><a href="https://x/Equipo.aspx?i=1">A</a></td>'
            '<td class="fecha"><a href="https://x/Partido.aspx?p=77">SÁBADO<br/>17/04/2027<br/>19:00</a></td>'
            '<td class="equipo visitante"><a href="https://x/Equipo.aspx?i=2">B</a></td></tr></table></div>')
    (m,) = parse_calendar(html)
    assert m.start == "2027-04-17T19:00" and m.code == "77" and m.round_index == 1


def test_round_index_follows_the_order_of_the_tables(matches):
    assert {m.round_index for m in matches[:3]} == {1}
    assert {m.round_index for m in matches[3:]} == {2}


def test_team_ids_come_from_the_team_links_not_from_names(matches):
    assert all(m.home_id.isdigit() and m.away_id.isdigit() for m in matches)


def test_involves_helper(matches):
    m = matches[0]
    assert m.involves("1008779") and m.involves("1008995") and not m.involves("1")
    assert m.opponent_of("1008779") == ("1008995", "GRUPO INTERBUS ALCOBENDAS")
    assert m.opponent_of("1") is None


def test_rows_without_a_match_link_are_skipped():
    html = ('<div class="tableLayout de dos columnas"><table><tr><th>Local</th></tr><tr>'
            '<td class="equipo local"><a href="https://x/Equipo.aspx?i=1">A</a></td><td class="fecha">Por determinar</td>'
            '<td class="equipo visitante"><a href="https://x/Equipo.aspx?i=2">B</a></td></tr></table></div>')
    assert parse_calendar(html) == []


def test_pages_without_calendar_tables_give_an_empty_list():
    assert parse_calendar("<html><body>nada</body></html>") == []
    assert parse_calendar(b"") == []


def test_matches_are_plain_serialisable_objects(matches):
    d = matches[3].to_dict()
    assert d["code"] == "2524704" and set(d) >= {"code", "kind", "start", "score", "home", "away", "round"}
    assert isinstance(matches[0], CalendarMatch)
