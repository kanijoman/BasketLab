"""The «Trayectoria» table of a FEB player page: one line per season and team, with the dates of alta and baja (#1082)."""
import gzip
from pathlib import Path

import pytest

from src.local_data.feb_trajectory import TrajectoryError, left_team, parse_trajectory

FIXTURE = Path(__file__).parent / "fixtures" / "feb_player_216888_950692.html.gz"   # a real page: 13 seasons, one with a baja


@pytest.fixture(scope="module")
def lines():
    return parse_trajectory(gzip.open(FIXTURE).read())


def test_one_line_per_season_and_team(lines):
    assert len(lines) == 13
    assert lines[0] == {"season": "14/15", "category": "EBA", "team_id": "671397", "alta": "2014-10-01", "baja": None}


def test_the_baja_of_a_line_is_read(lines):
    line = next(l for l in lines if l["team_id"] == "921670")
    assert (line["alta"], line["baja"]) == ("2023-10-03", "2024-02-09")


def test_the_line_is_tied_to_the_team_by_its_id_not_by_its_name(lines):
    assert {l["team_id"] for l in lines if l["season"] == "24/25"} == {"950692"}


def test_a_page_without_the_table_is_a_visible_error_never_no_bajas():
    with pytest.raises(TrajectoryError):
        parse_trajectory("<html><body><h1>Otra cosa</h1></body></html>")


def test_a_line_whose_date_cannot_be_read_is_an_error():
    html = ('<table id="x_trayectoriaDataGrid"><tr><th>Temp.</th></tr><tr><td>23/24</td><td>LEB</td><td><a href="Equipo.aspx?i=5">A</a></td><td>J</td>'
            '<td>mañana</td><td></td></tr></table>')
    with pytest.raises(TrajectoryError):
        parse_trajectory(html)


LINES = [{"season": "23/24", "category": "LEB", "team_id": "921670", "alta": "2023-10-03", "baja": "2024-02-09"},
         {"season": "24/25", "category": "2FEB", "team_id": "950692", "alta": "2024-09-04", "baja": None}]


@pytest.mark.parametrize("team,today,expected", [
    ("921670", "2026-11-24", True),        # baja filled and past: he left that team
    ("921670", "2024-02-09", True),        # the day of the baja he is already out
    ("921670", "2024-02-08", False),       # a baja still to come: he is active until then
    ("950692", "2026-11-24", False),       # no baja
    ("111111", "2026-11-24", False),       # no line for that team (a page not updated yet): he stays
])
def test_left_team_corners(team, today, expected):
    assert left_team(LINES, team, today) is expected
