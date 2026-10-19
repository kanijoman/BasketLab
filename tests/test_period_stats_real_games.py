"""Per-period figures on the 16 real games of LF Challenge 2026-27, against the partials of the official PDF (#353).

The points of each period must equal the PDF's partials (``quarters_home_away``, home first as in ``HEADER.TEAM``), overtimes
included; the periods of a team add up to its points; possessions of both teams of a period are within a couple of each other.
"""
import pytest

from src.pbp.game_derived import derive_game_fields
from tests.test_points_by_origin_real_games import IDS, PDF, _doc


def _derived(gid):
    return derive_game_fields(_doc(gid))["TEAM"]


@pytest.mark.parametrize("gid", IDS)
def test_points_by_period_equal_the_pdf_partials(gid):
    partials = PDF[gid]["quarters_home_away"]
    for index, team in enumerate(_derived(gid)):
        assert [p["pts"] for p in team["periods"]] == [q[index] for q in partials]


@pytest.mark.parametrize("gid", IDS)
def test_periods_add_up_to_the_team_points_and_carry_the_rivals_points(gid):
    home, away = _derived(gid)

    assert sum(p["pts"] for p in home["periods"]) == sum(home["pts_by_origin"].values())
    assert [p["opp_pts"] for p in home["periods"]] == [p["pts"] for p in away["periods"]]


@pytest.mark.parametrize("gid", IDS)
def test_possessions_of_a_period_are_balanced_between_the_teams(gid):
    home, away = _derived(gid)

    for mine, other in zip(home["periods"], away["periods"]):
        assert abs(mine["poss"] - other["poss"]) <= 3
        assert mine["minutes"] in (10, 5)
