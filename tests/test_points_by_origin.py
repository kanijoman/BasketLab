"""Points by origin of the possession of each team in a FEB game (#352).

Per team: ``pts_by_origin`` is a partition of the team's points by the way the possession started (the feed's technical
free throws go under ``technical``), so it adds up to the points. On top of it: points and possessions after a
turnover / steal / offensive rebound (second chance), points of the bench (non starters, ``inn`` of the box score) and
points in the paint (made shots of the ``SHOTCHART`` in the zones "aro" and "zona"). Fast-break points are not derived:
the official definition cannot be reproduced from the play-by-play (evaluated against the PDF in #352).
"""
import pytest

from src.pbp.game_derived import DERIVED_VERSION, derive_game_fields
from tests.test_live_core_possessions import _Feed


def _player(pid, starter):
    return {"id": pid, "inn": "1" if starter else "0"}


def _game(feed, shots=None):
    """A: starters p1..; bench ``b``. B: starter ``s``, bench ``p``/``q``."""
    box = {"p2m": 0, "p2a": 0, "p3m": 0, "p3a": 0, "p1m": 0, "p1a": 0, "ro": 0, "rd": 0, "to": 0, "pts": 0}
    teams = [
        {"id": "A", "name": "Local", "TOTAL": {k: str(v) for k, v in box.items()}, "PLAYER": [_player("p1", True), _player("b", False)]},
        {"id": "B", "name": "Visitante", "TOTAL": {k: str(v) for k, v in box.items()}, "PLAYER": [_player("s", True), _player("p", False)]},
    ]
    doc = {"HEADER": {"TEAM": [{"id": "A", "name": "Local"}, {"id": "B", "name": "Visitante"}]},
           "BOXSCORE": {"TEAM": teams}, "PLAYBYPLAY": {"LINES": list(reversed(feed.lines))}}
    if shots is not None:
        doc["SHOTCHART"] = {"SHOTS": shots}
    return doc


def _scenario():
    """A scores (starter); B turns it over; A scores a 3 from the bench; B misses, rebounds and scores (bench: second
    chance); A loses the ball to a steal of B, who scores (starter)."""
    feed = _Feed()
    feed.made("A", "09:50", 2, "p1")
    feed.tov("B", "09:40", "p")
    feed.made("A", "09:30", 3, "b")
    feed.miss("B", "09:20", 2, "p").reb("B", "09:19", "p").made("B", "09:15", 2, "p")
    feed.tov("A", "09:00", "p1").steal("B", "09:00", "s")
    feed.made("B", "08:50", 2, "s")
    return feed


def _teams(feed, shots=None):
    out = derive_game_fields(_game(feed, shots))
    return {t["id"]: t for t in out["TEAM"]}


def test_points_by_origin_partition_the_points_of_each_team():
    teams = _teams(_scenario())

    assert teams["A"]["pts_by_origin"] == {"period_start": 2, "turnover": 3}
    assert teams["B"]["pts_by_origin"] == {"made_basket": 2, "steal": 2}
    assert sum(teams["A"]["pts_by_origin"].values()) == 5 and sum(teams["B"]["pts_by_origin"].values()) == 4


def test_points_and_possessions_after_turnovers_and_steals():
    teams = _teams(_scenario())

    assert (teams["A"]["pts_off_tov"], teams["A"]["poss_off_tov"], teams["A"]["pts_off_steal"]) == (3, 1, 0)
    assert (teams["B"]["pts_off_tov"], teams["B"]["pts_off_steal"], teams["B"]["poss_off_steal"]) == (2, 2, 1)


def test_second_chance_points_and_the_possessions_that_had_one():
    teams = _teams(_scenario())

    assert (teams["B"]["pts_second_chance"], teams["B"]["poss_second_chance"]) == (2, 1)
    assert (teams["A"]["pts_second_chance"], teams["A"]["poss_second_chance"]) == (0, 0)


def test_bench_points_are_those_of_the_players_that_did_not_start():
    teams = _teams(_scenario())

    assert teams["A"]["pts_bench"] == 3        # the 3 of the bench player; the starter's 2 do not count
    assert teams["B"]["pts_bench"] == 2        # the second chance of the bench player; the steal basket was the starter's


def test_technical_free_throws_go_under_technical_and_do_not_open_a_possession():
    feed = _Feed()
    feed.made("A", "09:50", 2, "p1")
    feed.foul("B", "09:45", "Técnica").ft("A", "09:44", True, "p1")
    feed.made("B", "09:30", 2, "s")
    teams = _teams(feed)

    assert teams["A"]["pts_by_origin"] == {"period_start": 2, "technical": 1}


def test_bench_points_include_the_technical_free_throws_of_bench_players():
    """Bug: technical free throws belong to no possession, so the bench points left them out (3 of 32 team-games of the PDF)."""
    feed = _Feed()
    feed.made("A", "09:50", 2, "p1")
    feed.foul("A", "09:45", "Técnica").ft("B", "09:44", True, "p")      # bench player of B
    feed.ft("B", "09:44", True, "s")                                    # starter of B
    teams = _teams(feed)

    assert teams["B"]["pts_bench"] == 1 and teams["B"]["pts_by_origin"] == {"technical": 2}


def test_paint_points_come_from_the_made_shots_of_the_shotchart_in_the_rim_and_key_zones():
    shots = [
        {"m": "1", "x": 6.0, "y": 50.0, "team": 0, "quarter": 1, "t": "09:50", "player": "1"},     # at the rim: counts
        {"m": "1", "x": 30.0, "y": 8.0, "team": 0, "quarter": 1, "t": "09:30", "player": "1"},     # outside the key
        {"m": "0", "x": 6.0, "y": 50.0, "team": 0, "quarter": 1, "t": "09:20", "player": "1"},     # missed: no points
    ]
    teams = _teams(_scenario(), shots)

    assert teams["A"]["pts_paint"] == 2 and teams["B"]["pts_paint"] == 0


def test_a_game_without_shotchart_has_no_paint_points():
    assert _teams(_scenario())["A"]["pts_paint"] is None


def test_the_derived_version_marks_the_points_by_origin():
    assert DERIVED_VERSION >= 2


@pytest.mark.parametrize("field", ["pts_off_tov", "pts_off_steal", "pts_second_chance", "pts_bench", "poss_off_tov"])
def test_every_metric_is_a_non_negative_number(field):
    assert all(t[field] >= 0 for t in _teams(_scenario()).values())


# ---------------------------------------------------------------- fast break, our own estimate (#398)

def _transition_scenario():
    """B steals and scores 4 s later (fast break); later B rebounds and scores 10 s later (too slow), and again rebounds and scores 4 s later (fast break);
    B also scores quickly after a made basket of A (not a transition) and a free throw trip after a steal (free throws do not count)."""
    feed = _Feed()
    feed.tov("A", "09:00", "p1").steal("B", "09:00", "s")
    feed.made("B", "08:56", 2, "s")                                   # steal -> basket in 4 s: fast break (2)
    feed.miss("A", "08:30", 2, "p1").reb("B", "08:30", "p")           # defensive rebound
    feed.made("B", "08:20", 2, "p")                                   # 10 s later: not a fast break
    feed.miss("A", "07:50", 3, "p1").reb("B", "07:50", "s")
    feed.made("B", "07:46", 3, "s")                                   # 4 s after the rebound: fast break (3)
    feed.made("A", "07:30", 2, "p1")
    feed.made("B", "07:25", 2, "s")                                   # 5 s after a made basket: not a transition origin
    feed.tov("A", "07:10", "p1")                                      # a turnover of the rival WITHOUT steal (violation, out of bounds...)
    feed.made("B", "07:06", 2, "s")                                   # 4 s later: fast break (2)
    return feed


def test_fast_break_points_are_the_field_goals_scored_within_six_seconds_after_a_turnover_of_the_rival_or_a_defensive_rebound():
    teams = _teams(_transition_scenario())

    assert teams["B"]["pts_fastbreak"] == 7 and teams["A"]["pts_fastbreak"] == 0


def test_transition_possessions_are_the_ones_that_start_with_a_rival_turnover_steal_or_not_or_a_defensive_rebound():
    teams = _teams(_transition_scenario())

    assert teams["B"]["poss_transition"] == 4 and teams["A"]["poss_transition"] == 0


def test_the_window_is_six_seconds_and_a_basket_after_it_is_not_a_fast_break():
    from src.pbp.points_by_origin import FASTBREAK_MAX_S

    assert FASTBREAK_MAX_S == 6
    feed = _Feed()
    feed.tov("A", "09:00", "p1").steal("B", "09:00", "s")
    feed.made("B", "08:53", 2, "s")                                   # 7 s: out

    assert _teams(feed)["B"]["pts_fastbreak"] == 0


def test_free_throws_after_a_steal_are_not_fast_break_points():
    feed = _Feed()
    feed.tov("A", "09:00", "p1").steal("B", "09:00", "s")
    feed.foul("A", "08:58", "Personal", "p1").ft("B", "08:57", True, "s").ft("B", "08:57", True, "s")

    assert _teams(feed)["B"]["pts_fastbreak"] == 0


def test_the_derived_version_marks_the_fast_break_figures():
    assert DERIVED_VERSION >= 6


# ---------------------------------------------------------------- second chance: only after an offensive rebound

def _second_chance(feed):
    return _teams(feed)["B"]["pts_second_chance"]


def test_points_after_an_offensive_rebound_are_second_chance_baskets_and_free_throws_alike():
    feed = _Feed()
    feed.miss("B", "09:50", 2, "s").reb("B", "09:49", "p").made("B", "09:45", 2, "p")                         # basket after the rebound
    feed.miss("A", "09:30", 2, "p1").reb("A", "09:29", "p1").made("A", "09:25", 2, "p1")                      # the other team
    feed.miss("B", "09:10", 2, "s").reb("B", "09:09", "p").foul("A", "09:05", "Personal", "p1")
    feed.ft("B", "09:04", True, "p").ft("B", "09:04", True, "p")                                              # free throws after the rebound

    assert _second_chance(feed) == 4


def test_points_after_a_defensive_rebound_or_a_turnover_or_a_made_basket_are_not_second_chance():
    feed = _Feed()
    feed.miss("A", "09:50", 2, "p1").reb("B", "09:49", "s").made("B", "09:45", 2, "s")                        # defensive rebound
    feed.tov("A", "09:30", "p1").made("B", "09:26", 2, "s")                                                   # turnover of the rival
    feed.made("A", "09:10", 2, "p1").made("B", "09:05", 2, "s")                                               # after a made basket

    assert _second_chance(feed) == 0


def test_free_throws_of_a_shooting_foul_on_a_miss_are_not_second_chance():
    feed = _Feed()
    feed.miss("B", "09:50", 2, "s").foul("A", "09:49", "Personal", "p1")
    feed.ft("B", "09:48", True, "s").ft("B", "09:48", True, "s")                                              # a trip: the ball was never lost

    assert _second_chance(feed) == 0


def test_a_basket_after_the_team_keeps_the_ball_with_no_rebound_recorded_is_second_chance():
    """The feed lacks the rebound but the same team shoots again: it kept the ball, an implicit offensive rebound."""
    feed = _Feed()
    feed.miss("B", "09:50", 2, "s").made("B", "09:45", 2, "p")

    assert _second_chance(feed) == 2


def test_second_chance_points_are_a_part_of_the_points_of_the_origin_that_opened_the_possession():
    teams = _teams(_scenario())

    assert teams["B"]["pts_second_chance"] <= sum(teams["B"]["pts_by_origin"].values())
