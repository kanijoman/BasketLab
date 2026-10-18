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
