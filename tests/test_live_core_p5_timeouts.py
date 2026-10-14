"""P5 (issue #249): the rival scores right after coming out of its timeouts: prepare a special defence of the inbound pass.

A timeout of the rival is a ``timeout`` entry of the log; it "scores after it" if the rival scores within ``timeout_score_window_s``
seconds. It is said when that happened after ``timeout_score_n`` timeouts (at least ``timeout_score_min`` timeouts counted).
"""
import json

import pytest

from src.live_core.advice import RULES, AdviceEngine
from src.live_core.config import RULE_IDS, RuleConfig
from src.live_core.windows import scores_after_timeouts
from tests.test_live_core_advice import OWN, RIVAL, snap


def timeout(team, t):
    return [t, team, "timeout", 1, None]


def pts(team, t, value=2):
    return [t, team, "pts", value, "p1"]


def run(log, elapsed=1500, eng=None):
    s = snap(elapsed=elapsed, period=3, log=log)
    s["remaining"] = 300
    return (eng or AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL)).evaluate(s)


def by_id(advices, advice_id):
    return [a for a in advices if a.id == advice_id]


def test_the_helper_counts_the_timeouts_of_a_team_and_those_followed_by_its_points():
    log = [timeout(RIVAL, 100), pts(RIVAL, 112), timeout(RIVAL, 400), pts(OWN, 410), pts(RIVAL, 500), timeout(OWN, 600), pts(RIVAL, 610)]
    assert scores_after_timeouts(log, RIVAL, window_s=30, now=700) == (2, 1)
    assert scores_after_timeouts(log, OWN, window_s=30, now=700) == (1, 0)
    assert scores_after_timeouts([], RIVAL, 30, 700) == (0, 0)


def test_a_timeout_whose_window_has_not_passed_yet_does_not_count_as_a_failure_nor_a_success():
    log = [timeout(RIVAL, 680)]
    assert scores_after_timeouts(log, RIVAL, window_s=30, now=700) == (0, 0)
    assert scores_after_timeouts(log + [pts(RIVAL, 690)], RIVAL, window_s=30, now=700) == (1, 1)


def test_the_rules_is_registered_and_can_be_switched_off():
    assert "after_timeout_scoring" in RULE_IDS and "after_timeout_scoring" in [rid for rid, _ in RULES]
    log = [timeout(RIVAL, 100), pts(RIVAL, 112), timeout(RIVAL, 400), pts(RIVAL, 420)]
    off = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, config=RuleConfig(rules_off=("after_timeout_scoring",)))
    assert not by_id(run(log, eng=off), "rival_scores_after_timeout")


def test_p5_the_rival_that_scores_after_two_of_its_timeouts_says_to_prepare_the_inbound_defence():
    log = [timeout(RIVAL, 100), pts(RIVAL, 112), timeout(RIVAL, 400), pts(RIVAL, 420), timeout(RIVAL, 900), pts(OWN, 910)]
    [alert] = by_id(run(log), "rival_scores_after_timeout")
    assert alert.severity == "info" and alert.category == "rival" and "2 de 3" in alert.message
    assert alert.proposal[0]["type"] == "tactic" and "saque" in alert.proposal[0]["message"].lower()
    assert alert.evidence == {"timeouts": 3, "scored": 2, "window_s": 30, "team_id": RIVAL}


@pytest.mark.parametrize("log", [
    [timeout(RIVAL, 100), pts(RIVAL, 112)],                                                       # only one timeout: too little
    [timeout(RIVAL, 100), pts(RIVAL, 112), timeout(RIVAL, 400), pts(OWN, 420)],                   # one of two
    [timeout(OWN, 100), pts(OWN, 112), timeout(OWN, 400), pts(OWN, 420), timeout(OWN, 900)],       # our own timeouts
    [timeout(RIVAL, 100), pts(RIVAL, 145), timeout(RIVAL, 400), pts(RIVAL, 440)],                 # too late to be "after the timeout"
])
def test_p5_it_needs_at_least_two_timeouts_and_two_of_them_followed_by_a_basket_of_theirs(log):
    assert not by_id(run(log), "rival_scores_after_timeout")


def test_p5_it_is_said_once_per_number_of_timeouts_counted_and_again_when_it_grows():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL)
    two = [timeout(RIVAL, 100), pts(RIVAL, 112), timeout(RIVAL, 400), pts(RIVAL, 420)]
    assert by_id(run(two, eng=e), "rival_scores_after_timeout")
    assert not by_id(run(two, elapsed=1600, eng=e), "rival_scores_after_timeout")
    three = two + [timeout(RIVAL, 900), pts(RIVAL, 915)]
    assert by_id(run(three, elapsed=1700, eng=e), "rival_scores_after_timeout")


def test_the_alert_is_json_serialisable():
    log = [timeout(RIVAL, 100), pts(RIVAL, 112), timeout(RIVAL, 400), pts(RIVAL, 420)]
    [alert] = by_id(run(log), "rival_scores_after_timeout")
    assert json.loads(json.dumps(alert.proposal)) == alert.proposal
