"""Thresholds calibrated with three seasons of LF Challenge (issue #426) and the first-half timeout warning (issue #427).

The campaign replayed 753 games "as live" (latency 42 s, poll 10 s) and swept 21 configurations on 275 of them (see
``docs/evaluaciones/2026-10-20_calibracion-de-umbrales.md``). The new defaults cut the volume of the noisiest rules (a rule above
1 alert per 10 minutes, half of the alerts repeated within 10 minutes) with the same follow-up rate by the coaches.
"""
import pytest

from src.live_core.advice import RULES, AdviceEngine
from src.live_core.config import RULE_IDS, RuleConfig
from src.live_core.modes import MODES
from tests.builders import OWN, RIVAL, snap
from tests.test_live_core_sanctions import by_id, evaluate


@pytest.mark.parametrize("field, value", [
    ("fatigue_alert_index", 80.0),                                     # 5.265 -> 2.074 fatigue alerts (1,14 per 10 min), follow-up 33 -> 34 %
    ("turnover_streak", 5),                                            # 1.022 -> 463, duplicates -69 %, follow-up 14 -> 14 %
    ("hot_fg_min_made", 7), ("hot_3p_min_made", 5),                    # rival hot streaks: -300 / -169 alerts of the sweep
    ("cold_fg_max_made", 0), ("cold_3p_max_made", 0),                  # own cold streaks: -736 / -470
    ("zone_pps_excess", 0.7), ("zone_min_attempts", 7), ("paint_diff", 14),   # zones and paint: -1.197, paint duplicates -50 %
])
def test_the_defaults_are_the_calibrated_ones(field, value):
    assert getattr(RuleConfig(), field) == value


def test_four_turnovers_are_no_longer_a_streak_and_five_are_regression():
    """Before #426 four turnovers in five minutes raised the alert (43 % of them repeated within 10 minutes)."""
    log = lambda n: [[1000 + 30 * k, OWN, "tov", 1] for k in range(n)]  # noqa: E731
    engine = lambda: AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL)            # noqa: E731
    assert not by_id(engine().evaluate(snap(elapsed=1200, log=log(4))), "turnover_streak")
    assert by_id(engine().evaluate(snap(elapsed=1200, log=log(5))), "turnover_streak")


def test_the_modes_keep_the_stock_between_them():
    stock = RuleConfig()
    for key in MODES["aggressive"]:
        low, mid, high = MODES["aggressive"][key], getattr(stock, key), MODES["conservative"][key]
        assert low <= mid <= high or low >= mid >= high, key
    assert MODES["aggressive"]["fatigue_alert_index"] < stock.fatigue_alert_index < MODES["conservative"]["fatigue_alert_index"]
    assert MODES["aggressive"]["turnover_streak"] < stock.turnover_streak < MODES["conservative"]["turnover_streak"]


# --- #427: the first half ends and the timeouts that are left are lost --------------------------------------------------

CLOSE = dict(period=2, elapsed=1100, remaining=100)


def test_the_rule_is_registered_and_can_be_switched_off():
    assert "first_half_timeouts" in RULE_IDS and "first_half_timeouts" in [rid for rid, _ in RULES]
    off = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, config=RuleConfig(rules_off=("first_half_timeouts",)))
    assert not by_id(evaluate(eng=off, **CLOSE), "first_half_timeouts")


def test_both_timeouts_left_at_the_end_of_the_first_half_is_a_warning_to_use_one():
    [alert] = by_id(evaluate(**CLOSE), "first_half_timeouts")
    assert alert.severity == "warning" and alert.category == "gestion"
    assert "2" in alert.message and "descanso" in alert.message
    assert alert.proposal[0]["type"] == "timeout" and alert.proposal[0]["left"] == 2


def test_one_timeout_left_is_information():
    [alert] = by_id(evaluate(timeouts={OWN: [700]}, **CLOSE), "first_half_timeouts")
    assert alert.severity == "info" and alert.proposal[0]["left"] == 1


@pytest.mark.parametrize("override", [
    dict(timeouts={OWN: [700, 900]}),                  # none left: nothing is lost
    dict(remaining=200, elapsed=1000),                 # too early
    dict(period=1, elapsed=500, remaining=100),        # the 1st period: the timeouts of the half are still there
    dict(period=3, elapsed=1700, remaining=100),       # the 2nd half: they are not lost at the end of the 3rd
    dict(period=4, elapsed=2300, remaining=100),       # the end of the game is the business of timeout_budget
])
def test_it_only_says_it_at_the_end_of_the_first_half_with_timeouts_left(override):
    assert not by_id(evaluate(**{**CLOSE, **override}), "first_half_timeouts")


def test_it_is_said_once():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL)
    assert by_id(evaluate(eng=e, **CLOSE), "first_half_timeouts")
    assert not by_id(evaluate(eng=e, **{**CLOSE, "elapsed": 1110, "remaining": 90}), "first_half_timeouts")


def test_the_window_is_configurable():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, config=RuleConfig(half_close_s=60))
    assert not by_id(evaluate(eng=e, **CLOSE), "first_half_timeouts")
