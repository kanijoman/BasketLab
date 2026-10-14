"""Clutch analytics (issue #274): what a player does in a close finish.

The window is the one of ``game_context``'s ``close_late``: a margin of 6 or less in the last 4:00 of the 4th period, or in
overtime. ``LiveGame`` adds up, per player and while it applies the events (with the score and the clock of that moment),
the field-goal attempts, free throws, turnovers, points and seconds on court inside the window, and the same for the whole 4th
period (the fallback when there is no clutch sample). The package summary (``clutch.summarize``) turns the totals of the season into
a responsibility and an accuracy, both shrunk to what the player does the rest of the time.
"""
import pytest

from src.live_core.clock import elapsed_seconds
from src.live_core.clutch import MIN_SECONDS, PPS_PRIOR_SHOTS, SHRINK_SECONDS, empty, in_window, summarize
from src.live_core.events import Event
from src.live_core.state import LiveGame

A, B = "A", "B"


def game():
    g = LiveGame([(A, "Team A"), (B, "Team B")], roster={"a1": ("Ana", A), "a2": ("Aza", A), "b1": ("Bea", B)})
    for n, pid in enumerate(("a1", "a2", "b1")):
        g.apply(ev(n, 1, 600, "sub_in", pid))
    return g


def ev(num, period, remaining, kind, pid, made=None, points=0):
    team = B if pid.startswith("b") else A
    return Event(num=num, period=period, remaining=remaining, elapsed=elapsed_seconds(period, remaining), kind=kind,
                 team_id=team, player_id=pid, name=pid, made=made, points=points)


def score(g, a, b):
    g.score[A], g.score[B] = a, b


def play(g, *events):
    for e in events:
        g.apply(e)
    return g.snapshot()["players"]


# --- the window ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("period, remaining, margin, expected", [
    (4, 240, 6, True), (4, 100, 0, True), (4, 241, 3, False), (4, 100, 7, False), (3, 100, 0, False), (5, 250, 4, True), (5, 250, 7, False),
])
def test_the_window_is_the_closing_stretch_of_a_close_game(period, remaining, margin, expected):
    assert in_window(period, elapsed_seconds(period, remaining), margin) is expected


# --- what the state adds up ---------------------------------------------------------------------------------------

def test_shots_free_throws_turnovers_and_points_inside_the_window_are_counted_for_the_player():
    g = game()
    score(g, 50, 48)
    p = play(g, ev(10, 4, 200, "fg3", "a1", made=True, points=3), ev(11, 4, 190, "fg2", "a1", made=False),
             ev(12, 4, 180, "ft", "a1", made=True, points=1), ev(13, 4, 170, "ft", "a1", made=False),
             ev(14, 4, 160, "turnover", "a1"))["a1"]
    assert p["clutch"]["fga"] == 2 and p["clutch"]["fta"] == 2 and p["clutch"]["ftm"] == 1
    assert p["clutch"]["tov"] == 1 and p["clutch"]["pts"] == 4


def test_what_happens_outside_the_window_is_not_clutch_but_the_fourth_period_keeps_it():
    g = game()
    score(g, 50, 40)                                                        # 10 points: not close
    p = play(g, ev(10, 4, 200, "fg2", "a1", made=True, points=2))["a1"]
    assert p["clutch"]["fga"] == 0 and p["q4"]["fga"] == 1 and p["q4"]["pts"] == 2
    g2 = game()
    score(g2, 50, 48)                                                       # close, but with more than 4:00 left
    p2 = play(g2, ev(10, 4, 300, "fg2", "a1", made=True, points=2))["a1"]
    assert p2["clutch"]["fga"] == 0 and p2["q4"]["fga"] == 1
    g3 = game()
    p3 = play(g3, ev(10, 3, 300, "fg2", "a1", made=True, points=2))["a1"]
    assert p3["q4"]["fga"] == 0 and p3["clutch"]["fga"] == 0


def test_the_margin_is_the_one_before_the_event_not_after_it():
    g = game()
    score(g, 43, 50)                                                        # 7 behind: the shot that makes it 5 is not clutch
    p = play(g, ev(10, 4, 200, "fg2", "a1", made=True, points=2), ev(11, 4, 190, "fg2", "a1", made=True, points=2))["a1"]
    assert g.score[A] == 47 and p["clutch"]["fga"] == 1 and p["clutch"]["pts"] == 2      # only the second one (margin 5 before it)


def test_overtime_counts_while_it_is_close():
    g = game()
    score(g, 80, 80)
    p = play(g, ev(10, 5, 200, "fg3", "a1", made=True, points=3))["a1"]
    assert p["clutch"]["fga"] == 1 and p["clutch"]["pts"] == 3 and p["q4"]["fga"] == 0


def test_seconds_on_court_inside_the_window_are_credited_from_the_start_of_the_window():
    g = game()
    score(g, 50, 48)
    p = play(g, ev(9, 4, 600, "rebound", "a2"), ev(10, 4, 300, "rebound", "a2"), ev(11, 4, 200, "rebound", "a2"))   # opens at 4:00 left
    assert p["a1"]["clutch"]["sec"] == 40 and p["b1"]["clutch"]["sec"] == 40            # 240 -> 200 left, on court since the start
    assert p["a1"]["q4"]["sec"] == 400                                                  # the 4th period from its start (10:00 -> 2:20 left)
    p = play(g, ev(12, 4, 150, "sub_out", "a1"), ev(13, 4, 100, "rebound", "a2"))
    assert p["a1"]["clutch"]["sec"] == 90 and p["a2"]["clutch"]["sec"] == 140           # a1 left at 150; a2 stayed until 100


def test_no_seconds_are_credited_while_the_game_is_not_close():
    g = game()
    score(g, 60, 48)
    p = play(g, ev(9, 4, 600, "rebound", "a2"), ev(10, 4, 300, "rebound", "a2"), ev(11, 4, 100, "rebound", "a2"))
    assert p["a1"]["clutch"]["sec"] == 0 and p["a1"]["q4"]["sec"] == 500


def test_the_snapshot_carries_the_totals_of_every_player_even_without_a_close_finish():
    p = game().snapshot()["players"]
    assert all(set(v["clutch"]) == set(empty()) and set(v["q4"]) == set(empty()) for v in p.values())
    assert p["a1"]["clutch"] == empty()


# --- the summary for the package ------------------------------------------------------------------------------------

SEASON = dict(usage_per10=8.0, pps_season=1.0, ft_pct_season=0.75)


def totals(sec, fga, fta=0, ftm=0, tov=0, pts=0):
    return {"fga": fga, "fta": fta, "ftm": ftm, "tov": tov, "pts": pts, "sec": sec}


def test_responsibility_is_shrunk_to_the_normal_usage_and_follows_the_clutch_one_with_more_time():
    short = summarize(totals(MIN_SECONDS, 6, tov=2), empty(), **SEASON)
    long = summarize(totals(4 * SHRINK_SECONDS, 48, tov=16), empty(), **SEASON)
    raw_short, raw_long = 8 / MIN_SECONDS * 600, 64 / (4 * SHRINK_SECONDS) * 600
    assert SEASON["usage_per10"] < short["usage"] < raw_short and SEASON["usage_per10"] < long["usage"] < raw_long
    assert abs(long["usage"] - raw_long) < abs(short["usage"] - raw_short)


def test_accuracy_has_a_much_stronger_prior_than_the_responsibility_and_effective_means_above_the_season():
    hot = summarize(totals(600, 10, pts=14), empty(), **SEASON)           # 1.4 points per shot against 1.0
    assert 1.0 < hot["pps"] < 1.4 and hot["effective"] is True
    w = 10 / (10 + PPS_PRIOR_SHOTS)
    assert hot["pps"] == pytest.approx(w * 1.4 + (1 - w) * 1.0, abs=1e-3)
    cold = summarize(totals(600, 10, pts=6), empty(), **SEASON)
    assert cold["pps"] < 1.0 and cold["effective"] is False


def test_free_throws_count_as_shots_with_the_possession_cost_and_the_percentage_is_shrunk():
    s = summarize(totals(600, 5, fta=5, ftm=5, pts=15), empty(), **SEASON)
    assert s["ft_pct"] == pytest.approx((5 + 10 * 0.75) / (5 + 10), abs=1e-3) and s["fta"] == 5 and s["ftm"] == 5


def test_without_enough_clutch_time_it_falls_back_to_the_fourth_period_and_says_it_is_a_small_sample():
    s = summarize(totals(MIN_SECONDS - 1, 3), totals(900, 12, pts=12), **SEASON)
    assert s["basis"] == "q4" and s["sample"] == "small" and s["sec"] == 900
    ok = summarize(totals(MIN_SECONDS, 3), totals(900, 12, pts=12), **SEASON)
    assert ok["basis"] == "clutch" and ok["sample"] == "ok"


def test_without_a_sample_in_either_there_is_nothing_to_say():
    assert summarize(empty(), empty(), **SEASON) == {"basis": "none", "sample": "none", "sec": 0}
    assert summarize(totals(100, 2), totals(100, 2), **SEASON)["basis"] == "none"


def test_a_player_without_season_shots_is_never_effective():
    s = summarize(totals(600, 4, pts=6), empty(), usage_per10=0.0, pps_season=0.0, ft_pct_season=0.72)
    assert s["effective"] is False
