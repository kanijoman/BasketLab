"""Alert of a flip of the win probability (issue #258): it falls ``wp_flip_drop`` (20 points) or more within ``wp_flip_window_s`` (5 min).

The rule remembers the probability of each evaluation (``ctx.memory``), compares the current one with the highest of the last
five minutes and, when it fell that much, warns with the main lever of the win probability (and, for a Four Factors lever, the
recommender's proposal). The probability is experimental in the app (#257): the threshold is provisional, to confirm with the staff.
"""
import pytest

from src.live_core.advice import AdviceEngine
from src.live_core.config import RULE_IDS, RuleConfig
from tests.builders import OWN, RIVAL, _stats, snap


def board(margin, elapsed, period=None, remaining=300):
    s = snap(elapsed=elapsed, period=period or min(4, 1 + elapsed // 600))
    s["remaining"] = remaining
    s["score"] = {OWN: 50 + margin, RIVAL: 50}
    return s


def engine(**cfg):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, config=RuleConfig(**cfg))


def flips(eng, *snapshots):
    return [a for s in snapshots for a in eng.evaluate(s) if a.id == "win_flip"]


def test_it_is_a_registered_rule_with_provisional_thresholds_in_the_config():
    assert "win_flip" in RULE_IDS
    cfg = RuleConfig()
    assert cfg.wp_flip_drop == pytest.approx(0.20) and cfg.wp_flip_window_s == 300


def test_a_fall_of_twenty_points_in_five_minutes_is_a_warning_with_the_numbers():
    eng = engine()
    assert flips(eng, board(6, 1200)) == []                     # first evaluation: nothing to compare with
    [a] = flips(eng, board(-8, 1380))                           # three minutes later: from ~76 % to ~15 %
    assert a.severity == "warning" and a.category == "probabilidad"
    assert a.evidence["p_before"] > 0.7 and a.evidence["p_now"] < 0.2
    assert a.evidence["drop"] >= 0.20 and a.evidence["window_s"] == 300
    assert "probabilidad de victoria" in a.message.lower() and "%" in a.message


def test_a_fall_that_takes_longer_than_the_window_does_not_count():
    eng = engine()
    # the same drop spread over twenty minutes, one point every minute and a half: no five-minute stretch loses 20 points
    margins = list(range(6, -9, -1))
    assert flips(eng, *[board(m, 600 + 90 * i) for i, m in enumerate(margins)]) == []


def test_a_small_fall_or_a_rise_says_nothing():
    eng = engine()
    assert flips(eng, board(6, 1200), board(3, 1260), board(8, 1320), board(12, 1380)) == []


def test_the_same_fall_is_said_once_and_a_new_one_after_the_window():
    eng = engine()
    assert len(flips(eng, board(6, 1200), board(-8, 1380))) == 1
    assert flips(eng, board(-9, 1440), board(-10, 1500)) == []                # still down: nothing new
    assert flips(eng, board(8, 1560)) == []                                    # recovers...
    assert len(flips(eng, board(-8, 1740))) == 1                               # ...and falls again


def test_the_threshold_is_in_the_config_and_the_rule_can_be_switched_off():
    assert flips(engine(wp_flip_drop=0.95), board(6, 1200), board(-8, 1380)) == []
    assert flips(engine(rules_off=("win_flip",)), board(6, 1200), board(-8, 1380)) == []


def test_it_names_the_main_lever_of_the_win_probability_when_there_is_one():
    eng = engine()
    eng._win_prob.levers = lambda s, f: [{"id": "pace", "direction": "up", "gain": 0.08, "gain_pts": 1.5}]
    flips(eng, board(6, 1200))
    [a] = flips(eng, board(-8, 1380))
    assert a.evidence["lever"] == "pace" and a.evidence["lever_gain"] == pytest.approx(0.08)
    assert "ritmo" in a.message.lower()


def test_a_four_factors_lever_brings_the_recommenders_proposal():
    eng = engine()
    eng._win_prob.levers = lambda s, f: [{"id": "tov", "gain": 0.05, "gain_pts": 1.0}]
    eng._recommender = type("R", (), {"suggest_for_lever": lambda self, s, lever: [{"type": "sub", "out_id": "a", "in_id": "b", "lever": lever}]})()
    flips(eng, board(6, 1200))
    [a] = flips(eng, board(-8, 1380))
    assert a.evidence["lever"] == "tov" and "pérdidas" in a.message.lower()
    assert a.proposal and a.proposal[0]["lever"] == "tov"


def test_without_a_lever_it_still_warns():
    eng = engine()
    eng._win_prob.levers = lambda s, f: []
    flips(eng, board(6, 1200))
    [a] = flips(eng, board(-8, 1380))
    assert a.evidence["lever"] is None and "palanca" not in a.message.lower()


def test_a_decided_game_silences_it():
    eng = engine()
    first = board(4, 1980, period=3, remaining=0)
    last = board(-22, 2280, period=4, remaining=120)
    assert flips(eng, first, last) == []


def test_going_back_in_time_or_repeating_a_moment_does_not_break_the_memory():
    eng = engine()
    flips(eng, board(6, 1200), board(6, 1200))                  # the same snapshot twice
    assert flips(eng, board(6, 600)) == []                      # a replay that jumped back
    assert flips(eng, board(-9, 780))[0].evidence["p_before"] > 0.5


def test_without_a_rival_there_is_no_probability_and_no_alert():
    eng = AdviceEngine(own_team_id=OWN, rival_team_id=None, config=RuleConfig())
    assert flips(eng, board(6, 1200), board(-8, 1380)) == []


def test_the_main_lever_is_a_diagnosis_without_a_promised_gain_regression():
    """Study of #567 (26/10/2026): what the game shows in a factor does not predict the next minutes, so «+8 % si vuelve a su nivel habitual» promised an effect nobody measured."""
    import re

    eng = engine()
    eng._win_prob.levers = lambda s, f: [{"id": "efg", "gain": 0.08, "gain_pts": 1.5}]
    flips(eng, board(6, 1200))
    [a] = flips(eng, board(-8, 1380))
    assert a.evidence["lever"] == "efg" and "Palanca principal: tiro" in a.message
    assert not re.search(r"\+\d+ ?%|nivel habitual", a.message)
