"""How coaches behave, from the finished games (issue #238): the evidence the rules are built on.

Replaces the provisional analysis scripts: timeouts and what preceded them, voluntary stint lengths, how fouls are
handled and scoring droughts. ``game_behaviour`` reads one game; ``summarize_coach`` aggregates many.
"""
import pytest

from src.live_core.clock import period_and_remaining
from src.live_core.events import Event
from src.live_prep.eval_coach import game_behaviour, simulate_run_rule, summarize_coach
from src.live_prep.eval_labels import Actions

A, B = "T1", "T2"


def ev(elapsed, kind, team=A, player=None, made=None, points=0, pf=None, foul_type=None):
    period, remaining = period_and_remaining(elapsed)   # the real clock: a quarter ends at 0:00 / opens at 10:00
    return Event(num=int(elapsed * 10), period=period, remaining=remaining, elapsed=elapsed, kind=kind,
                 team_id=team, player_id=player, made=made, points=points, pf_count=pf, foul_type=foul_type)


def basket(elapsed, team, points=2, player="x"):
    return ev(elapsed, "fg2" if points == 2 else "fg3", team=team, player=player, made=True, points=points)


def behaviour(events):
    return game_behaviour(Actions(events), (A, B))


# --- timeouts ----------------------------------------------------------------------------

def test_each_timeout_records_what_the_five_minutes_and_the_last_two_and_a_half_looked_like():
    events = [basket(30, B), basket(60, B), basket(90, B, 3), basket(100, A),
              ev(40, "turnover"), ev(50, "turnover"), ev(95, "turnover"), ev(98, "turnover"), ev(120, "timeout")]
    [t] = behaviour(events)["timeouts"]
    assert (t["team"], t["elapsed"]) == (A, 120)
    assert t["opp_150"] == 7 and t["own_150"] == 2 and t["own_tov_300"] == 4


def test_timeouts_without_a_team_are_ignored():
    assert behaviour([ev(100, "timeout", team=None)])["timeouts"] == []


# --- stints ------------------------------------------------------------------------------

def test_voluntary_stints_are_measured_and_period_boundaries_are_left_out():
    events = [ev(0, "sub_in", player="p1"), ev(300, "sub_out", player="p1"),        # 5:00, mid period: voluntary
              ev(300, "sub_in", player="p2"), ev(600, "sub_out", player="p2")]      # at the end of the quarter: not a decision
    stints = behaviour(events)["stints"]
    assert [s["stint_s"] for s in stints] == [300]


def test_a_stint_closed_by_the_fifth_foul_is_not_voluntary():
    events = [ev(0, "sub_in", player="p1"), ev(200, "foul", player="p1", pf=5, foul_type="personal"),
              ev(200, "sub_out", player="p1")]
    assert behaviour(events)["stints"] == []


# --- fouls -------------------------------------------------------------------------------

def test_a_personal_foul_records_whether_the_player_was_subbed_out_within_two_minutes():
    events = [ev(100, "foul", player="p1", pf=2, foul_type="personal"), ev(150, "sub_out", player="p1"),
              ev(700, "foul", player="p2", pf=3, foul_type="personal"), ev(900, "sub_out", player="p2")]
    cases = behaviour(events)["foul_cases"]
    assert [(c["pf"], c["period"], c["subbed_120"]) for c in cases] == [(2, 1, True), (3, 2, False)]


def test_only_second_third_and_fourth_personal_fouls_are_cases():
    events = [ev(10, "foul", player="p1", pf=1, foul_type="personal"), ev(20, "foul", player="p1", pf=2, foul_type="technical"),
              ev(30, "foul", player="p1", pf=5, foul_type="personal"), ev(40, "foul", player="p1", pf=4, foul_type="personal")]
    assert [c["pf"] for c in behaviour(events)["foul_cases"]] == [4]


# --- droughts ----------------------------------------------------------------------------

def test_a_drought_of_four_minutes_or_more_notes_whether_the_team_called_a_timeout_during_it():
    events = [basket(10, A), ev(200, "timeout"), basket(300, A), basket(310, B), basket(900, A)]
    own = [x for x in behaviour(events)["droughts"] if x["team"] == A]
    assert own[0] == {"team": A, "start": 10, "length": 290, "timeout": True}
    assert own[1] == {"team": A, "start": 300, "length": 600, "timeout": False}


def test_short_gaps_are_not_droughts():
    assert [d for d in behaviour([basket(10, A), basket(200, A)])["droughts"] if d["team"] == A] == []


# --- aggregation -------------------------------------------------------------------------

def make_games():
    g1 = {"timeouts": [{"team": A, "elapsed": 100, "opp_150": 9, "own_150": 0, "own_tov_300": 1},
                       {"team": B, "elapsed": 500, "opp_150": 2, "own_150": 4, "own_tov_300": 5}],
          "stints": [{"team": A, "stint_s": 200}, {"team": A, "stint_s": 300}, {"team": B, "stint_s": 500}],
          "foul_cases": [{"pf": 2, "period": 1, "subbed_120": True}, {"pf": 3, "period": 4, "subbed_120": False},
                         {"pf": 3, "period": 4, "subbed_120": True}],
          "droughts": [{"team": A, "start": 0, "length": 300, "timeout": True}]}
    return [g1, {"timeouts": [], "stints": [], "foul_cases": [], "droughts": []}]


def test_summary_counts_timeouts_per_team_game_and_their_context():
    s = summarize_coach(make_games(), team_games=4)
    assert s["games"] == 2 and s["timeouts"]["total"] == 2 and s["timeouts"]["per_team_game"] == 0.5
    assert s["timeouts"]["after_rival_net_run_6"] == 0.5 and s["timeouts"]["after_four_turnovers"] == 0.5


def test_summary_describes_stints_fouls_and_droughts():
    s = summarize_coach(make_games(), team_games=4)
    assert s["stints"]["n"] == 3 and s["stints"]["median_s"] == 300 and s["stints"]["share_over_420"] == pytest.approx(1 / 3)
    assert s["fouls"]["2"]["H1"] == {"n": 1, "subbed_120": 1.0}
    assert s["fouls"]["3"]["Q4"] == {"n": 2, "subbed_120": 0.5}
    assert s["droughts"] == {"n": 1, "per_team_game": 0.25, "with_timeout": 1.0}


def test_summary_of_nothing_is_empty_instead_of_failing():
    s = summarize_coach([], team_games=0)
    assert s["timeouts"]["total"] == 0 and s["stints"]["n"] == 0 and s["droughts"]["n"] == 0


# --- the run threshold simulation --------------------------------------------------------

def test_the_simulation_counts_fires_followed_timeouts_and_covered_timeouts():
    # B scores 8 unanswered by second 80 (20, 40, 60, 80); A calls a timeout at 150; B calls one with no run behind it
    events = [basket(20 + 20 * i, B) for i in range(4)] + [ev(150, "timeout", team=A), ev(900, "timeout", team=B)]
    table = simulate_run_rule([Actions(events)], [(A, B)], [(8, 150, "unanswered"), (6, 150, "net")])
    unanswered, net = table
    assert unanswered["spec"] == "8 sin respuesta en 150 s" and unanswered["fires"] == 1
    assert unanswered["per_team_game"] == 0.5                       # one fire over the two team-games
    assert unanswered["followed"] == 1.0 and unanswered["covered"] == 0.5   # 1 of the 2 timeouts had a fire before it
    assert net["spec"] == "6 netos en 150 s" and net["fires"] == 1   # it fires earlier, at 60, and is followed too
    assert net["followed"] == 1.0
