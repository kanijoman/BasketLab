"""After-timeout possessions, first possession of each period and the first / last two minutes of each period (#354).

Per team, stored in ``DERIVED`` (v4): ``ato_own`` / ``ato_rival`` (possessions of the team that follow a timeout it called /
one the rival called: count and points), ``first_poss`` (periods whose first possession was the team's: count and points) and
``edges`` (``start`` / ``end``: points, possessions and turnovers of both teams in the first / last ``EDGE_WINDOW_S`` of every
period). The last minute of a period is not excluded here: a timeout of the last minute still starts an after-timeout possession.
"""
import pytest

from src.pbp.game_derived import DERIVED_VERSION, derive_game_fields
from src.pbp.situation_stats import EDGE_WINDOW_S
from tests.test_live_core_possessions import _Feed
from tests.test_points_by_origin import _game


def _teams(feed):
    return {t["id"]: t for t in derive_game_fields(_game(feed))["TEAM"]}


def _ato_scenario():
    """A scores; B calls a timeout and scores a 3 (B's own ATO); A scores; A is on the ball and B's possession that follows
    has a timeout of A inside it; B scores a 2 (B's ATO after a rival timeout)."""
    feed = _Feed()
    feed.made("A", "09:50", 2, "p1")
    feed.timeout("B", "09:45")
    feed.made("B", "09:30", 3, "s")
    feed.made("A", "09:10", 2, "p1")
    feed.timeout("A", "09:05")
    feed.made("B", "08:50", 2, "s")
    return feed


def test_the_derived_version_marks_the_situation_figures():
    assert DERIVED_VERSION >= 4


def test_possessions_after_a_timeout_of_the_team_itself():
    teams = _teams(_ato_scenario())

    assert teams["B"]["ato_own"] == {"n": 1, "pts": 3}
    assert teams["A"]["ato_own"] == {"n": 0, "pts": 0}


def test_possessions_after_a_timeout_of_the_rival():
    teams = _teams(_ato_scenario())

    assert teams["B"]["ato_rival"] == {"n": 1, "pts": 2}
    assert teams["A"]["ato_rival"] == {"n": 0, "pts": 0}


def test_the_first_possession_of_each_period_belongs_to_one_team():
    feed = _Feed()
    feed.made("A", "09:50", 2, "p1").made("B", "09:30", 3, "s")
    feed.q = "2"
    feed.made("B", "09:50", 2, "s").made("A", "09:30", 2, "p1")
    teams = _teams(feed)

    assert teams["A"]["first_poss"] == {"n": 1, "pts": 2}
    assert teams["B"]["first_poss"] == {"n": 1, "pts": 2}


def test_first_and_last_two_minutes_of_the_period():
    feed = _Feed()
    feed.made("A", "09:50", 2, "p1")                      # first 2:00
    feed.made("B", "05:00", 3, "s")                       # middle of the period
    feed.made("A", "01:30", 2, "p1")                      # last 2:00
    feed.tov("B", "01:00", "s")                           # last 2:00
    teams = _teams(feed)

    assert EDGE_WINDOW_S == 120
    assert (teams["A"]["edges"]["start"]["pts"], teams["A"]["edges"]["start"]["opp_pts"]) == (2, 0)
    assert (teams["A"]["edges"]["end"]["pts"], teams["A"]["edges"]["end"]["opp_pts"]) == (2, 0)
    assert (teams["B"]["edges"]["end"]["tov"], teams["A"]["edges"]["end"]["opp_tov"]) == (1, 1)
    assert teams["B"]["edges"]["start"]["pts"] == 0       # the three of the middle is in neither window


def test_possessions_of_a_window_are_counted_where_they_started():
    feed = _Feed().made("A", "09:50", 2, "p1").made("B", "09:40", 2, "s")
    edges = _teams(feed)["A"]["edges"]["start"]

    assert edges["poss"] >= 1 and edges["opp_poss"] >= 1


@pytest.mark.parametrize("key", ["pts", "opp_pts", "poss", "opp_poss", "tov", "opp_tov"])
def test_every_window_has_the_counters_of_both_teams(key):
    edges = _teams(_ato_scenario())["A"]["edges"]

    assert key in edges["start"] and key in edges["end"]
