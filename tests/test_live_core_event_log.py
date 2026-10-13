"""Enriched event log (issue #237): [elapsed, team_id, kind, value, player_id].

The old log only kept pts / tov / orb without the player, which is not enough to diagnose a run or a drought or to
measure shooting streaks. Kinds: pts (points of a made shot), fg2 / fg3 / ft (an attempt: value 1 made, 0 missed),
tov, orb, stl and timeout. ``player_id`` is None when the event has no player (team turnover, timeout).
"""
import json

from src.live_core.engine import LiveEngine
from src.live_core.events import Event
from src.live_core.state import LiveGame

A, B = "T1", "T2"


def game():
    g = LiveGame([(A, "Alfa"), (B, "Beta")], {"a1": ("Ana", A), "b1": ("Bea", B)})
    return g


def ev(num, elapsed, kind, team=A, player="a1", **kw):
    period, remaining = 1, 600 - elapsed
    return Event(num=num, period=period, remaining=remaining, elapsed=elapsed, kind=kind, team_id=team,
                 player_id=player, **kw)


def log_of(*events):
    g = game()
    for e in events:
        g.apply(e)
    return g.snapshot()["log"]


def test_a_made_shot_logs_the_attempt_and_the_points_with_the_player():
    assert log_of(ev(1, 30, "fg2", made=True, points=2)) == [[30, A, "fg2", 1, "a1"], [30, A, "pts", 2, "a1"]]
    assert log_of(ev(1, 30, "fg3", made=True, points=3)) == [[30, A, "fg3", 1, "a1"], [30, A, "pts", 3, "a1"]]


def test_a_missed_shot_logs_only_the_attempt():
    assert log_of(ev(1, 30, "fg3", made=False)) == [[30, A, "fg3", 0, "a1"]]
    assert log_of(ev(1, 30, "ft", made=False)) == [[30, A, "ft", 0, "a1"]]


def test_a_made_free_throw_is_one_point():
    assert log_of(ev(1, 30, "ft", made=True, points=1)) == [[30, A, "ft", 1, "a1"], [30, A, "pts", 1, "a1"]]


def test_turnovers_name_the_player_and_team_turnovers_have_none():
    assert log_of(ev(1, 40, "turnover")) == [[40, A, "tov", 1, "a1"]]
    assert log_of(ev(1, 40, "turnover", player=None)) == [[40, A, "tov", 1, None]]


def test_offensive_rebounds_name_the_rebounder_and_defensive_ones_are_not_logged():
    miss = ev(1, 50, "fg2", made=False)
    assert log_of(miss, ev(2, 52, "rebound")) == [[50, A, "fg2", 0, "a1"], [52, A, "orb", 1, "a1"]]
    assert log_of(miss, ev(2, 52, "rebound", team=B, player="b1")) == [[50, A, "fg2", 0, "a1"]]


def test_steals_and_timeouts_are_logged_for_their_team():
    assert log_of(ev(1, 60, "steal", team=B, player="b1")) == [[60, B, "stl", 1, "b1"]]
    assert log_of(ev(1, 70, "timeout", player=None)) == [[70, A, "timeout", 1, None]]


def test_every_entry_has_five_elements_and_the_log_is_json():
    log = log_of(ev(1, 30, "fg2", made=True, points=2), ev(2, 40, "turnover", player=None), ev(3, 50, "timeout", player=None))
    assert all(len(e) == 5 for e in log)
    assert json.loads(json.dumps(log)) == log


def test_the_real_game_log_agrees_with_the_team_totals(feb_game_doc):
    snap = LiveEngine().update(feb_game_doc)
    log = snap["log"]
    assert log == sorted(log, key=lambda e: e[0]), "log must be chronological"
    assert all(len(e) == 5 for e in log)
    for tid, team in snap["teams"].items():
        s = team["stats"]
        mine = [e for e in log if e[1] == tid]
        for kind, made, att in (("fg2", "fg2m", "fg2a"), ("fg3", "fg3m", "fg3a"), ("ft", "ftm", "fta")):
            shots = [e for e in mine if e[2] == kind]
            assert len(shots) == s[att], f"{tid} {kind} attempts"
            assert sum(e[3] for e in shots) == s[made], f"{tid} {kind} makes"
        assert sum(e[3] for e in mine if e[2] == "pts") == s["pts"]
        assert sum(1 for e in mine if e[2] == "stl") == s["stl"]
        assert sum(1 for e in mine if e[2] == "timeout") == len(team["timeouts"])
        assert sum(1 for e in mine if e[2] == "tov" and e[4] is None) == s["tov_team"]


def test_every_made_shot_points_entry_names_a_player_of_its_team(feb_game_doc):
    snap = LiveEngine().update(feb_game_doc)
    for e in snap["log"]:
        if e[2] in ("pts", "fg2", "fg3", "ft", "orb", "stl"):
            assert e[4] in snap["players"] and snap["players"][e[4]]["team_id"] == e[1]
