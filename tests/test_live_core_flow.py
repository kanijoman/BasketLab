"""Game-flow rules (issue #242): scoring droughts (R2, P2), long runs (P3, P4) and window counts (G2, G3, G5).

All of them read the event log ``[elapsed, team_id, kind, value, player_id]``. Droughts and runs are said once per episode (the
stretch since the team's last timeout of the period) and not in the minute after the team's own timeout.
"""
import json

import pytest

from live_helpers import TABLE
from src.live_core.advice import RULES, AdviceEngine
from src.live_core.config import RULE_IDS, RuleConfig
from src.live_core.windows import points_after_turnovers
from tests.builders import OWN, RIVAL, snap

RULE_GROUPS = ("scoring_drought", "long_run", "game_flow_windows")


def pts(team, t, value=2):
    return [t, team, "pts", value, "p1"]


def fg(team, t, made=1, kind="fg2"):
    return [t, team, kind, made, "p1"]


def ft(team, t, made=1):
    return [t, team, "ft", made, "p1"]


def tov(team, t, pid="p1"):
    return [t, team, "tov", 1, pid]


def orb(team, t):
    return [t, team, "orb", 1, "p1"]


def scored(team, t, value=2):
    """A made basket: the attempt and its points, as the engine logs it."""
    return [fg(team, t, 1, "fg3" if value == 3 else "fg2"), pts(team, t, value)]


def flat(*groups):
    """One log from entries, lists of entries and lists of lists of entries."""
    out = []
    for g in groups:
        if g and isinstance(g[0], list):
            out.extend(flat(*g))
        else:
            out.append(g)
    return out


def evaluate(log, elapsed=400, period=1, engine=None, timeouts=None, **kw):
    s = snap(elapsed=elapsed, period=period, log=log)
    for team, times in (timeouts or {}).items():
        s["teams"][team]["timeouts"] = times
    return (engine or AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, **kw)).evaluate(s)


def by_id(advices, advice_id):
    return [a for a in advices if a.id == advice_id]


# --- the helper: rival points right after our turnovers -----------------------------------

def test_points_after_turnovers_counts_what_the_rival_scores_within_the_horizon_of_each_turnover():
    log = flat(tov(OWN, 100), pts(RIVAL, 103, 3), tov(OWN, 200), pts(RIVAL, 215, 2), pts(RIVAL, 300, 2))
    assert points_after_turnovers(log, OWN, RIVAL, 0, 400, horizon=8) == 3
    assert points_after_turnovers(log, OWN, RIVAL, 0, 400, horizon=20) == 5


def test_points_after_turnovers_counts_each_rival_basket_once_and_only_inside_the_window():
    log = flat(tov(OWN, 100), tov(OWN, 102), pts(RIVAL, 105, 2), tov(OWN, 500), pts(RIVAL, 503, 3))
    assert points_after_turnovers(log, OWN, RIVAL, 0, 400, horizon=8) == 2     # one basket after two turnovers; the later pair is outside
    assert points_after_turnovers([], OWN, RIVAL, 0, 400, horizon=8) == 0


def test_the_rules_are_registered_and_can_be_switched_off():
    for rule_id in RULE_GROUPS:
        assert rule_id in RULE_IDS and rule_id in [rid for rid, _ in RULES]
    log = flat(scored(OWN, 100))
    off = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, config=RuleConfig(rules_off=("scoring_drought",)))
    assert not by_id(evaluate(log, engine=off), "own_drought")


# --- R2: own drought ---------------------------------------------------------------------

def test_r2_four_minutes_without_scoring_asks_for_a_timeout_or_a_change_of_system():
    [alert] = by_id(evaluate(flat(scored(OWN, 100)), elapsed=340), "own_drought")
    assert alert.severity == "warning" and alert.category == "gestion"
    assert "4:00" in alert.message and alert.evidence["gap_s"] == 240
    kinds = [p["type"] for p in alert.proposal]
    assert kinds == ["timeout", "tactic"] and alert.proposal[0]["left"] == 2


@pytest.mark.parametrize("elapsed", [339, 100])
def test_r2_less_than_four_minutes_is_not_a_drought(elapsed):
    assert not by_id(evaluate(flat(scored(OWN, 100)), elapsed=elapsed), "own_drought")


def test_r2_six_minutes_is_critical_and_a_team_that_never_scored_counts_from_the_start():
    assert [a.severity for a in by_id(evaluate(flat(scored(OWN, 100)), elapsed=460), "own_drought")] == ["critical"]
    [alert] = by_id(evaluate([], elapsed=250), "own_drought")
    assert alert.evidence["gap_s"] == 250


def test_r2_free_throws_count_as_scoring():
    log = flat(scored(OWN, 100), pts(OWN, 300, 1))
    assert not by_id(evaluate(log, elapsed=400), "own_drought")


def test_r2_says_why_with_the_causes_of_the_window():
    log = flat(scored(OWN, 100), tov(OWN, 150, "a"), tov(OWN, 200, "a"), tov(OWN, 250, "b"))
    [alert] = by_id(evaluate(log, elapsed=400), "own_drought")
    assert "3 pérdidas" in alert.message


def test_r2_without_timeouts_left_it_only_proposes_the_change_of_system():
    [alert] = by_id(evaluate(flat(scored(OWN, 100)), elapsed=400, timeouts={OWN: [150, 200]}), "own_drought")
    assert [p["type"] for p in alert.proposal] == ["tactic"]


def test_r2_is_silent_just_after_our_timeout_and_comes_back_if_the_drought_goes_on():
    e, log = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL), flat(scored(OWN, 100))
    assert by_id(evaluate(log, elapsed=345, engine=e), "own_drought")
    assert not by_id(evaluate(log, elapsed=360, engine=e), "own_drought")             # same episode
    assert not by_id(evaluate(log, elapsed=380, engine=e, timeouts={OWN: [350]}), "own_drought")   # 30 s after the timeout
    assert by_id(evaluate(log, elapsed=420, engine=e, timeouts={OWN: [350]}), "own_drought")       # still dry a minute later


# --- R2: rival drought ---------------------------------------------------------------------

def test_r2_the_rival_without_scoring_for_three_and_a_half_minutes_is_a_window_to_run():
    log = flat(scored(RIVAL, 100), scored(OWN, 300))
    [alert] = by_id(evaluate(log, elapsed=310), "rival_drought")
    assert alert.severity == "info" and alert.category == "rival" and "3:30" in alert.message
    assert alert.proposal[0]["type"] == "tactic"


def test_r2_it_is_not_a_window_to_run_if_we_are_not_scoring_either():
    assert not by_id(evaluate(flat(scored(RIVAL, 100)), elapsed=320), "rival_drought")
    assert not by_id(evaluate(flat(scored(RIVAL, 100), scored(OWN, 310)), elapsed=300), "rival_drought")


# --- P2: no field goal, only free throws -----------------------------------------------------

def test_p2_three_minutes_without_a_field_goal_but_with_free_throws_says_to_attack_the_rim():
    log = flat(scored(OWN, 100), ft(OWN, 250), pts(OWN, 250, 1))
    [alert] = by_id(evaluate(log, elapsed=300), "fg_drought")
    assert alert.severity == "warning" and "3:20" in alert.message
    assert "aro" in alert.proposal[0]["message"]


def test_p2_does_not_repeat_r2_when_the_team_did_not_score_at_all():
    assert not by_id(evaluate(flat(scored(OWN, 100)), elapsed=300), "fg_drought")


def test_p2_a_recent_field_goal_or_less_than_three_minutes_is_not_a_drought():
    log = flat(scored(OWN, 100), ft(OWN, 250), pts(OWN, 250, 1))
    assert not by_id(evaluate(log, elapsed=270), "fg_drought")
    assert not by_id(evaluate(log + scored(OWN, 290), elapsed=300), "fg_drought")


# --- P3 and P4: long runs ---------------------------------------------------------------------

def test_p3_minus_ten_net_in_five_minutes_asks_for_a_timeout():
    log = flat([scored(RIVAL, t) for t in (100, 140, 180, 220, 260, 300)], scored(OWN, 320))
    [alert] = by_id(evaluate(log, elapsed=330), "long_run")
    assert alert.severity == "warning" and alert.category == "gestion"
    assert "-10" in alert.message and alert.evidence["net"] == -10 and alert.evidence["window_s"] == 300
    assert alert.proposal[0]["type"] == "timeout"


def test_p3_threshold_is_ten_net():
    nine = flat([scored(RIVAL, t) for t in (100, 150, 200, 250, 300)], pts(OWN, 320, 1))
    assert not by_id(evaluate(nine, elapsed=330), "long_run")
    ten = flat([scored(RIVAL, t) for t in (100, 150, 200, 250, 300)])
    [alert] = by_id(evaluate(ten, elapsed=330), "long_run")
    assert alert.proposal[0]["type"] == "timeout" and alert.proposal[0]["left"] == 2 and alert.evidence["net"] == -10


def test_p3_only_the_last_five_minutes_count_and_it_is_silent_after_our_timeout():
    old = flat([scored(RIVAL, t) for t in (10, 30, 50, 70, 90)])
    assert not by_id(evaluate(old, elapsed=420), "long_run")
    recent = flat([scored(RIVAL, t) for t in (100, 150, 200, 250, 300)])
    assert not by_id(evaluate(recent, elapsed=330, timeouts={OWN: [310]}), "long_run")


def test_p4_plus_eight_net_in_the_window_says_not_to_break_the_lineup():
    log = flat([scored(OWN, t) for t in (300, 320, 340, 360)])
    [alert] = by_id(evaluate(log, elapsed=370), "own_run")
    assert alert.severity == "info" and alert.category == "gestion" and "+8" in alert.message
    assert "quinteto" in alert.message


def test_p4_seven_net_or_an_old_run_is_not_a_run():
    assert not by_id(evaluate(flat([scored(OWN, t) for t in (300, 320, 340)], pts(OWN, 350, 1)), elapsed=370), "own_run")
    assert not by_id(evaluate(flat([scored(OWN, t) for t in (100, 120, 140, 160)]), elapsed=370), "own_run")
    assert not by_id(evaluate(flat([scored(OWN, t) for t in (300, 320, 340, 360)], scored(RIVAL, 365)), elapsed=370), "own_run")


# --- G2, G3, G5: counts in the last three minutes ---------------------------------------------

def test_g2_three_rival_offensive_rebounds_in_three_minutes_says_to_close_the_rebound():
    log = [orb(RIVAL, 250), orb(RIVAL, 300), orb(RIVAL, 340)]
    [alert] = by_id(evaluate(log, elapsed=350), "rival_orb_window")
    assert alert.severity == "warning" and alert.category == "four_factors" and "3" in alert.message
    assert alert.proposal[0]["type"] == "tactic"


def test_g2_gets_the_rebounders_of_the_bench_as_substitutions_when_the_package_has_players():
    import copy

    from live_helpers import OWN as HOWN, RIVAL as HRIVAL, snap as hsnap
    table = copy.deepcopy(TABLE)
    table["b3"]["z"]["drb40"] = 2.5          # a bench big who rebounds better than the one on court
    s = hsnap(period=1, elapsed=350)
    s["log"] = [orb(HRIVAL, 250), orb(HRIVAL, 300), orb(HRIVAL, 340)]
    out = AdviceEngine(own_team_id=HOWN, rival_team_id=HRIVAL, baselines=table).evaluate(s)
    [alert] = by_id(out, "rival_orb_window")
    assert alert.proposal[0]["type"] == "tactic"
    subs = [p for p in alert.proposal if p["type"] == "sub"]
    assert subs and subs[0]["in_id"] == "b3" and subs[0]["lever"] == "def_reb"


@pytest.mark.parametrize("log, elapsed", [([orb(RIVAL, 300), orb(RIVAL, 340)], 350), ([orb(RIVAL, 100), orb(RIVAL, 110), orb(RIVAL, 120)], 350)])
def test_g2_two_rebounds_or_old_ones_are_not_a_problem(log, elapsed):
    assert not by_id(evaluate(log, elapsed=elapsed), "rival_orb_window")


def test_g3_six_rival_points_right_after_our_turnovers_says_to_get_back_in_defence():
    log = flat(tov(OWN, 250), pts(RIVAL, 254, 3), tov(OWN, 300), pts(RIVAL, 302, 3))
    [alert] = by_id(evaluate(log, elapsed=310), "points_off_turnovers")
    assert alert.severity == "warning" and alert.category == "four_factors" and "6" in alert.message
    assert "balance defensivo" in alert.proposal[0]["message"].lower()


def test_g3_five_points_or_points_that_do_not_follow_a_turnover_are_not_a_problem():
    assert not by_id(evaluate(flat(tov(OWN, 250), pts(RIVAL, 254, 3), tov(OWN, 300), pts(RIVAL, 302, 2)), elapsed=310), "points_off_turnovers")
    assert not by_id(evaluate(flat(tov(OWN, 250), pts(RIVAL, 270, 3), tov(OWN, 300), pts(RIVAL, 320, 3)), elapsed=330), "points_off_turnovers")


def test_g5_four_rival_turnovers_in_three_minutes_says_to_keep_the_pressure():
    [alert] = by_id(evaluate([tov(RIVAL, t) for t in (220, 260, 300, 340)], elapsed=350), "rival_turnovers")
    assert alert.severity == "info" and alert.category == "rival" and "4" in alert.message
    assert "presión" in alert.proposal[0]["message"].lower()
    assert not by_id(evaluate([tov(RIVAL, t) for t in (260, 300, 340)], elapsed=350), "rival_turnovers")


def test_the_flow_alerts_are_said_once_per_episode():
    e, log = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL), [orb(RIVAL, 250), orb(RIVAL, 300), orb(RIVAL, 340)]
    assert by_id(evaluate(log, elapsed=350, engine=e), "rival_orb_window")
    assert not by_id(evaluate(log, elapsed=360, engine=e), "rival_orb_window")


def test_flow_alerts_are_json_serialisable():
    log = flat(scored(OWN, 100))
    for alert in by_id(evaluate(log, elapsed=400), "own_drought"):
        assert json.loads(json.dumps(alert.proposal)) == alert.proposal
