"""Team shooting streaks (issue #243): T1 cold field goals, T2 cold threes, T3 hot rival, T4 hot rival threes, T5 cold free throws.

Each rule reads the shot results of the event log; a streak is the last N attempts (oldest first). A streak that goes on is
said once and again only after a whole new window of attempts (not at a timeout or a new period).
"""
import json

import pytest

from src.live_core.advice import RULES, AdviceEngine
from src.live_core.config import RULE_IDS, RuleConfig
from tests.test_live_core_advice import OWN, RIVAL, snap

KIND = {2: "fg2", 3: "fg3"}


def shots(team, results, points=2, start=100, step=10):
    """Log entries for consecutive attempts (1 made, 0 missed) of ``team``."""
    return [[start + i * step, team, KIND[points], r, "p1"] for i, r in enumerate(results)]


def free_throws(team, results, start=100, step=5):
    return [[start + i * step, team, "ft", r, "p1"] for i, r in enumerate(results)]


def engine(**cfg):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, config=RuleConfig(**cfg))


def by_id(advices, advice_id):
    return [a for a in advices if a.id == advice_id]


def run(log, **kw):
    return engine().evaluate(snap(elapsed=kw.pop("elapsed", 400), log=log, **kw))


def test_the_rules_are_registered_and_can_be_switched_off():
    for rule_id in ("cold_shooting", "rival_hot_shooting", "free_throw_cold"):
        assert rule_id in RULE_IDS and rule_id in [rid for rid, _ in RULES]
    log = shots(OWN, [1, 0, 0, 0, 0, 0, 0, 0]) + shots(OWN, [0] * 7, points=3, start=300)
    off = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, config=RuleConfig(rules_off=("cold_shooting",)))
    assert not by_id(off.evaluate(snap(elapsed=400, log=log)), "cold_fg_streak")


# --- T1: own cold field goals -------------------------------------------------------

def test_t1_one_of_eight_in_a_row_is_a_cold_streak_that_asks_for_inside_play_and_free_throws():
    [alert] = by_id(run(shots(OWN, [1, 0, 0, 0, 0, 0, 0, 0])), "cold_fg_streak")
    assert alert.severity == "warning" and alert.category == "four_factors"
    assert "1/8" in alert.message
    assert alert.proposal[0]["type"] == "tactic" and "interior" in alert.proposal[0]["message"]


@pytest.mark.parametrize("results", [[1, 1, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0, 0, 1]])
def test_t1_two_made_or_fewer_than_eight_attempts_is_not_a_streak(results):
    assert not by_id(run(shots(OWN, results)), "cold_fg_streak")


def test_t1_only_the_last_eight_attempts_count_and_threes_count_too():
    log = shots(OWN, [1, 1, 1, 1, 1, 1]) + shots(OWN, [0, 0, 0, 0], points=3, start=200) + shots(OWN, [0, 0, 0, 0], start=300)
    [alert] = by_id(run(log), "cold_fg_streak")
    assert alert.evidence["made"] == 0 and alert.evidence["attempts"] == 8


def test_t1_ignores_the_rival_and_free_throws():
    log = shots(RIVAL, [0] * 8) + free_throws(OWN, [0] * 8)
    assert not by_id(run(log), "cold_fg_streak")


def test_t1_a_streak_that_goes_on_is_said_once_not_again_at_a_timeout_or_a_new_period():
    e, log = engine(), shots(OWN, [0] * 8)
    assert by_id(e.evaluate(snap(elapsed=400, log=log)), "cold_fg_streak")
    assert not by_id(e.evaluate(snap(elapsed=420, log=log + shots(OWN, [0, 0], start=410))), "cold_fg_streak")
    after = snap(elapsed=700, period=2, log=log + shots(OWN, [0] * 3, start=410))
    after["teams"][OWN]["timeouts"] = [450]
    assert not by_id(e.evaluate(after), "cold_fg_streak")


def test_t1_comes_back_after_a_whole_new_window_of_attempts_when_the_team_is_still_cold():
    e, log = engine(), shots(OWN, [0] * 8)
    assert by_id(e.evaluate(snap(elapsed=400, log=log)), "cold_fg_streak")
    later = log + shots(OWN, [0] * 8, start=300)
    assert by_id(e.evaluate(snap(elapsed=600, log=later)), "cold_fg_streak")


# --- T2: own cold threes ------------------------------------------------------------

def test_t2_one_of_seven_threes_in_a_row_says_to_attack_the_rim():
    [alert] = by_id(run(shots(OWN, [1, 0, 0, 0, 0, 0, 0], points=3)), "cold_3p_streak")
    assert alert.severity == "info" and "1/7" in alert.message
    assert alert.proposal[0]["type"] == "tactic" and "aro" in alert.proposal[0]["message"]


@pytest.mark.parametrize("results", [[1, 1, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]])
def test_t2_two_made_or_fewer_than_seven_threes_is_not_a_streak(results):
    assert not by_id(run(shots(OWN, results, points=3)), "cold_3p_streak")


def test_t2_twos_do_not_count_as_threes():
    log = shots(OWN, [0] * 7, points=3) + shots(OWN, [1] * 5, start=300)
    assert by_id(run(log), "cold_3p_streak")
    assert not by_id(run(shots(OWN, [0] * 7)), "cold_3p_streak")


# --- T3: hot rival ------------------------------------------------------------------

def test_t3_six_of_eight_by_the_rival_asks_to_change_the_defence_or_the_pressure():
    [alert] = by_id(run(shots(RIVAL, [1, 1, 0, 1, 1, 1, 0, 1])), "rival_hot_streak")
    assert alert.severity == "warning" and alert.category == "rival" and "6/8" in alert.message
    assert alert.proposal[0]["type"] == "tactic" and "defensa" in alert.proposal[0]["message"].lower()


@pytest.mark.parametrize("results", [[1, 1, 0, 1, 1, 0, 0, 1], [1, 1, 1, 1, 1, 1, 1]])
def test_t3_five_of_eight_or_fewer_than_eight_attempts_is_not_a_streak(results):
    assert not by_id(run(shots(RIVAL, results)), "rival_hot_streak")


# --- T4: hot rival threes -----------------------------------------------------------

def test_t4_four_of_the_last_six_rival_threes_says_to_close_the_three_point_line():
    [alert] = by_id(run(shots(RIVAL, [0, 1, 1, 0, 1, 1], points=3)), "rival_3p_streak")
    assert alert.severity == "info" and alert.category == "rival" and "4/6" in alert.message
    assert "3" in alert.proposal[0]["message"]


@pytest.mark.parametrize("results", [[1, 1, 0, 0, 1, 0], [1, 1, 1, 1, 1]])
def test_t4_three_of_six_or_fewer_than_six_threes_is_not_a_streak(results):
    assert not by_id(run(shots(RIVAL, results, points=3)), "rival_3p_streak")


# --- T5: cold free throws -----------------------------------------------------------

def test_t5_half_of_eight_free_throws_or_worse_says_to_give_the_ball_to_the_good_shooters():
    [alert] = by_id(run(free_throws(OWN, [1, 0, 1, 0, 0, 1, 0, 1])), "ft_cold")
    assert alert.severity == "info" and "4/8" in alert.message
    assert "tiradores" in alert.proposal[0]["message"]


@pytest.mark.parametrize("results", [[1, 1, 1, 0, 1, 0, 1, 1], [0, 0, 0, 0, 0, 0, 0]])
def test_t5_over_half_or_fewer_than_eight_attempts_is_not_cold(results):
    assert not by_id(run(free_throws(OWN, results)), "ft_cold")


def test_t5_counts_the_whole_game_and_is_a_warning_in_a_close_finish():
    log = free_throws(OWN, [0, 1, 0, 1, 0, 0, 1, 0])
    e = engine()
    normal = snap(elapsed=2000, period=3, log=log)
    assert [a.severity for a in by_id(e.evaluate(normal), "ft_cold")] == ["info"]
    close = snap(elapsed=2300, period=4, log=log)
    close["remaining"], close["score"] = 100, {OWN: 70, RIVAL: 72}
    [late] = by_id(e.evaluate(close), "ft_cold")
    assert late.severity == "warning" and late.key != "ft_cold:normal"


def test_streak_alerts_are_json_serialisable():
    for advice in by_id(run(shots(OWN, [0] * 8) + shots(RIVAL, [1] * 8)), "cold_fg_streak") + by_id(
            run(shots(RIVAL, [1] * 8)), "rival_hot_streak"):
        assert json.loads(json.dumps(advice.proposal)) == advice.proposal
