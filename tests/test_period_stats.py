"""Per-period figures of each team in a FEB game, stored in ``DERIVED`` (v3, #353).

Each team gets a list of periods ``{p, minutes, <own counters>, opp_<the rival's counters>}``: points, possessions (counted by
the period where they started), field goals, threes, free throws, turnovers, rebounds and fouls. Overtimes stay as separate
periods (5, 6...): the season service groups them as "OT".
"""
import pytest

from src.pbp.game_derived import DERIVED_VERSION, derive_game_fields
from tests.test_live_core_possessions import _Feed
from tests.test_points_by_origin import _game


def _scenario():
    """P1: A scores a 2; B misses a 3 and A rebounds (defensive); A turns it over; B scores a 3; A misses, rebounds its own
    miss (offensive) and scores. P2: B scores a 2, A is fouled and makes one of two free throws. P5 (overtime): A scores a 3."""
    feed = _Feed()
    feed.made("A", "09:50", 2, "p1")
    feed.miss("B", "09:40", 3, "s").reb("A", "09:39", "p1")
    feed.tov("A", "09:30", "p1")
    feed.made("B", "09:20", 3, "s")
    feed.miss("A", "09:10", 2, "p1").reb("A", "09:09", "p1").made("A", "09:05", 2, "p1")
    feed.q = "2"
    feed.made("B", "09:50", 2, "s")
    feed.foul("B", "09:40", "Personal", "s").ft("A", "09:39", True, "p1").ft("A", "09:39", False, "p1")
    feed.q = "5"
    feed.made("A", "04:50", 3, "p1")
    return feed


def _periods():
    out = derive_game_fields(_game(_scenario()))
    return {t["id"]: {p["p"]: p for p in t["periods"]} for t in out["TEAM"]}


def test_the_derived_version_marks_the_periods():
    assert DERIVED_VERSION >= 3


def test_points_and_shots_by_period():
    a, b = _periods()["A"], _periods()["B"]

    assert (a[1]["pts"], a[1]["fga"], a[1]["fgm"], a[1]["fg3m"]) == (4, 3, 2, 0)
    assert (a[2]["pts"], a[2]["fta"], a[2]["ftm"], a[2]["fga"]) == (1, 2, 1, 0)
    assert (b[1]["pts"], b[1]["fga"], b[1]["fg3m"]) == (3, 2, 1)
    assert (b[2]["pts"], b[2]["fga"]) == (2, 1)


def test_turnovers_rebounds_and_fouls_by_period():
    a, b = _periods()["A"], _periods()["B"]

    assert (a[1]["tov"], a[1]["orb"], a[1]["drb"]) == (1, 1, 1)
    assert (b[1]["tov"], b[1]["orb"], b[1]["drb"]) == (0, 0, 0)
    assert b[2]["fouls"] == 1 and a[2]["fouls"] == 0


def test_every_period_carries_the_rivals_figures_as_opp():
    periods = _periods()

    for p in (1, 2, 5):
        assert periods["A"][p]["opp_pts"] == periods["B"][p]["pts"]
        assert periods["A"][p]["opp_drb"] == periods["B"][p]["drb"]
        assert periods["A"][p]["opp_poss"] == periods["B"][p]["poss"]


def test_overtime_is_a_separate_period_of_five_minutes():
    a = _periods()["A"]

    assert sorted(a) == [1, 2, 5]
    assert (a[1]["minutes"], a[2]["minutes"], a[5]["minutes"]) == (10, 10, 5)
    assert a[5]["pts"] == 3


def test_points_of_the_periods_add_up_to_the_points_of_the_team():
    teams = {t["id"]: t for t in derive_game_fields(_game(_scenario()))["TEAM"]}

    for tid, team in teams.items():
        assert sum(p["pts"] for p in team["periods"]) == sum(team["pts_by_origin"].values())


def test_possessions_are_counted_in_the_period_where_they_started():
    teams = {t["id"]: {p["p"]: p for p in t["periods"]} for t in derive_game_fields(_game(_scenario()))["TEAM"]}

    assert sum(p["poss"] for t in teams.values() for p in t.values()) > 0
    assert all(p["poss"] >= 0 for t in teams.values() for p in t.values())


@pytest.mark.parametrize("field", ["pts", "poss", "fga", "fgm", "fg3m", "fta", "ftm", "tov", "orb", "drb", "fouls"])
def test_every_counter_has_its_opp_twin(field):
    entry = _periods()["A"][1]

    assert field in entry and f"opp_{field}" in entry
