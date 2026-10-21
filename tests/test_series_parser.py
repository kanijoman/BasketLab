"""Calendar of the knockout phases (``Series.aspx``), which are not in ``calendario.aspx`` (issue #456).

Found on 2026-10-21 with the Copa de España: the 1/16 ties only exist as ``<h1 class="titulo-modulo">`` + a one-row table
(teams, ``Partido.aspx?p=`` with the score or ``* - *``, date). ``parse_calendar`` returned 0 matches, so ``upcoming`` and
``next_rounds`` were empty. The fixture is a real, trimmed page (a played tie, a scheduled one, Llíria and Cultural Leonesa).
"""
from pathlib import Path

from src.scraper.calendar_parser import CalendarMatch, parse_calendar, parse_series

PAGE = Path(__file__).parent / "fixtures" / "feb_series_copa.html"


def _real():
    return {m.code: m for m in parse_series(PAGE.read_bytes())}


def _tie(title, rows):
    body = "".join(f'<tr><td><a href="https://x/Equipo.aspx?i={h}">{hn}</a> - <a href="https://x/Equipo.aspx?i={a}">{an}</a></td>'
                   f'<td><a href="https://x/Partido.aspx?p={code}">{res}</a></td><td>\n {date}\n {hour}\n</td></tr>'
                   for h, hn, a, an, code, res, date, hour in rows)
    return f'<h1 class="titulo-modulo">\n {title}\n</h1><table>{body}</table>'


class TestRealPage:
    def test_every_tie_is_a_match_in_page_order(self):
        assert list(_real()) == ["2543131", "2543132", "2543134", "2543136"]

    def test_a_played_tie_is_a_result_with_its_score_and_no_start_time(self):
        m = _real()["2543131"]
        assert (m.kind, m.score, m.start) == ("result", "76-86", None)
        assert (m.home_id, m.away_id) == ("1009109", "1010493") and m.home_name == "COVIRAN GRANADA"

    def test_a_tie_not_played_yet_is_scheduled_with_its_kick_off(self):
        m = _real()["2543134"]
        assert (m.kind, m.score, m.start) == ("scheduled", None, "2026-10-21T20:00")
        assert (m.home_id, m.home_name, m.away_name) == ("1008978", "CLUB ESPORTIU BÀSQUET LLÍRIA", "INVEREADY ASKATUAK GIPUZKOA")

    def test_the_phase_is_the_title_before_the_first_dot(self):
        assert {m.phase for m in _real().values()} == {"1/16 Final"}

    def test_teams_of_interest_are_found_by_id(self):
        matches = list(_real().values())
        assert [m.code for m in matches if m.involves("1008857")] == ["2543136"]

    def test_a_single_match_tie_is_the_first_match_of_its_tie(self):
        assert {m.round_index for m in _real().values()} == {1}

    def test_the_page_is_not_a_calendar_page(self):
        assert parse_calendar(PAGE.read_bytes()) == []


class TestShapes:
    def test_a_two_leg_tie_gives_one_match_per_row_numbered_within_the_tie(self):
        html = _tie("Final. A - B", [("1", "A", "2", "B", "10", "80 - 70", "10/05/2027", "20:00"),
                                      ("2", "B", "1", "A", "11", "* - *", "13/05/2027", "21:00")])
        first, second = parse_series(html)
        assert (first.kind, first.round_index, first.phase) == ("result", 1, "Final")
        assert (second.kind, second.round_index, second.start, second.home_id) == ("scheduled", 2, "2027-05-13T21:00", "2")

    def test_ties_are_numbered_independently(self):
        html = _tie("1/8 Final. A - B", [("1", "A", "2", "B", "10", "* - *", "10/05/2027", "20:00")]) + \
            _tie("1/8 Final. C - D", [("3", "C", "4", "D", "11", "* - *", "10/05/2027", "21:00")])
        assert [m.round_index for m in parse_series(html)] == [1, 1]

    def test_a_title_without_a_dot_keeps_the_whole_text_as_its_phase(self):
        assert parse_series(_tie("Final", [("1", "A", "2", "B", "10", "* - *", "10/05/2027", "20:00")]))[0].phase == "Final"

    def test_a_scheduled_tie_without_date_keeps_no_start(self):
        html = _tie("Final. A - B", [("1", "A", "2", "B", "10", "* - *", "", "")])
        assert parse_series(html)[0].start is None

    def test_a_tie_not_drawn_yet_gives_no_match(self):
        assert parse_series('<h1 class="titulo-modulo">Final. - </h1><table><tr><td> - </td><td></td><td></td></tr></table>') == []

    def test_empty_or_unrelated_pages_give_nothing(self):
        assert parse_series("") == [] and parse_series(b"") == [] and parse_series("<html><body>no series</body></html>") == []

    def test_the_serialised_form_is_the_one_of_the_calendar_without_the_phase(self):
        d = _real()["2543131"].to_dict()
        assert set(d) == {"code", "kind", "round", "score", "start", "home", "away"}
        assert isinstance(_real()["2543131"], CalendarMatch)
