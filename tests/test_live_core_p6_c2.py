"""P6 (issue #250): the starts or the ends of the quarters add up negative: prepare the way out of the quarter, said in the pause.
C2 (issue #253): the comeback plan: how many possessions are left and what net points per possession it takes.
"""
import json

import pytest

from src.live_core.advice import RULES, AdviceEngine
from src.live_core.config import RULE_IDS, RuleConfig
from tests.test_live_core_closing import OWN, POSSESSIONS, RIVAL, end_of, engine, flat, pace_snap, pts
from tests.builders import snap


def by_id(advices, advice_id):
    return [a for a in advices if a.id == advice_id]


def test_the_rules_are_registered_and_can_be_switched_off():
    for rule_id in ("period_edges", "comeback_plan"):
        assert rule_id in RULE_IDS and rule_id in [rid for rid, _ in RULES]
    off = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, config=RuleConfig(rules_off=("period_edges",)))
    assert not by_id(off.evaluate(end_of(2, [pts(RIVAL, 50, 3), pts(RIVAL, 100, 2), pts(RIVAL, 650, 2), pts(RIVAL, 700, 2)])), "period_edge_deficit")


# --- P6 ----------------------------------------------------------------------------------------------------------------

# first two minutes of quarters 1 and 2: -5 and -4; last two minutes of quarters 1 and 2: -3 and -4
STARTS = [pts(RIVAL, 50, 3), pts(RIVAL, 100, 2), pts(RIVAL, 650, 2), pts(RIVAL, 700, 2)]
ENDS = [pts(RIVAL, 500, 3), pts(RIVAL, 1100, 2), pts(RIVAL, 1150, 2)]


def edges(period, groups, **kw):
    return by_id(engine().evaluate(end_of(period, groups, **kw)), "period_edge_deficit")


def test_p6_two_quarters_that_start_badly_say_to_prepare_the_way_out_of_the_next_one():
    [alert] = edges(2, STARTS)
    assert alert.severity == "info" and alert.category == "resumen" and alert.key == "edges:start:2"
    assert "Inicios de cuarto" in alert.message and "-5" in alert.message and "-4" in alert.message and "-9" in alert.message
    assert alert.proposal[0]["type"] == "tactic" and "salida" in alert.proposal[0]["message"].lower()
    assert alert.evidence["kind"] == "start" and alert.evidence["nets"] == [-5, -4]


def test_p6_the_ends_of_the_quarters_are_the_same_with_their_own_message():
    [alert] = edges(2, ENDS)
    assert alert.key == "edges:end:2" and "Cierres de cuarto" in alert.message and alert.evidence["nets"] == [-3, -4]
    assert alert.proposal[0]["type"] == "tactic" and "2:00" in alert.proposal[0]["message"]


@pytest.mark.parametrize("groups, period", [
    (STARTS, 1),                                                          # one quarter is not an accumulation
    ([pts(RIVAL, 50, 3), pts(RIVAL, 100, 2), pts(RIVAL, 650, 2), pts(OWN, 700, 2), pts(OWN, 710, 3)], 2),   # -5 and +3
    ([pts(RIVAL, 50, 3), pts(RIVAL, 100, 3), pts(RIVAL, 150, 2), pts(OWN, 650, 2)], 2),   # -8 and +2: only one is negative
    ([pts(RIVAL, 50, 2), pts(RIVAL, 650, 2)], 2),                         # -2 and -2: too little
])
def test_p6_it_needs_two_negative_quarters_and_an_accumulated_deficit_of_six(groups, period):
    assert not edges(period, groups)


def test_p6_the_third_quarter_adds_to_the_first_two_and_it_is_said_once_per_pause():
    groups = STARTS + [pts(RIVAL, 1250, 3), pts(RIVAL, 1300, 3)]
    [alert] = edges(3, groups)
    assert alert.evidence["nets"] == [-5, -4, -6] and "-15" in alert.message
    e = engine()
    assert by_id(e.evaluate(end_of(2, STARTS)), "period_edge_deficit")
    assert not by_id(e.evaluate(end_of(2, STARTS)), "period_edge_deficit")


def test_p6_if_the_poll_missed_the_end_it_comes_in_the_first_minute_of_the_next_period():
    [alert] = edges(3, STARTS, remaining=560)
    assert alert.key == "edges:start:2"
    assert not edges(3, STARTS, remaining=450)


def test_p6_the_last_period_has_no_pause():
    assert not edges(4, STARTS + [pts(RIVAL, 1250, 3), pts(RIVAL, 1300, 3)])


# --- C2 ----------------------------------------------------------------------------------------------------------------

def comeback_snap(margin, remaining=300, period=4):
    elapsed = (period - 1) * 600 + 600 - remaining
    s = pace_snap(margin=margin, period=period, elapsed=elapsed)
    s["remaining"] = remaining
    for team in s["teams"].values():       # the possessions of pace_snap are those of minute 20: scale them to the clock (73.7 per 40)
        team["stats"] = {k: v * elapsed / 1200 for k, v in team["stats"].items()}
    return s


def comeback(margin, remaining=300, period=4, **kw):
    return by_id(engine(**kw).evaluate(comeback_snap(margin, remaining, period)), "comeback_plan")


def test_c2_nine_down_with_five_minutes_says_how_many_possessions_are_left_and_what_it_takes():
    [alert] = comeback(-9)
    assert alert.severity == "info" and alert.category == "gestion" and "perdemos por 9" in alert.message
    assert "9 posesiones" in alert.message and "+0.98" in alert.message and "-0.14" in alert.message
    assert alert.proposal[0]["type"] == "tactic" and "extra" in alert.proposal[0]["message"].lower()
    assert alert.evidence["deficit"] == 9 and alert.evidence["need"] == pytest.approx(0.98, abs=0.01)


def test_c2_a_deficit_that_normal_play_can_close_says_so():
    [alert] = comeback(-8, remaining=590)
    assert alert.evidence["need"] < 0.5 and "ritmo normal" in alert.message


@pytest.mark.parametrize("kw", [dict(margin=-7), dict(margin=-9, remaining=601), dict(margin=-9, period=3, remaining=100), dict(margin=5), dict(margin=-9, remaining=0)])
def test_c2_it_needs_a_deficit_of_eight_and_less_than_ten_minutes_of_the_last_period(kw):
    assert not comeback(**kw)


def test_c2_when_it_takes_more_than_one_and_a_half_net_points_per_possession_it_is_no_plan_and_it_says_nothing_regression():
    """In Zamora-Leon (lost by 20+) it said 'hace falta +3.76 netos por posesión' three times: an impossible comeback is not advice."""
    assert comeback(-9, remaining=300)               # +0.98 per possession: a hard but real plan
    assert not comeback(-17, remaining=300)          # +1.85
    assert not comeback(-25, remaining=100)


def test_c2_without_a_reliable_pace_it_says_nothing():
    s = pace_snap(margin=-9, period=4, elapsed=200)
    s["remaining"] = 300
    assert not by_id(engine().evaluate(s), "comeback_plan")


def test_c2_it_is_said_once_per_block_of_six_minutes_so_twice_at_most_in_the_last_ten():
    """Reevaluation 22/10/2026: every four minutes repeated 49 % of the alerts; at most two reminders in the last ten minutes."""
    e = engine()
    assert by_id(e.evaluate(comeback_snap(-9, 450)), "comeback_plan")
    assert not by_id(e.evaluate(comeback_snap(-10, 400)), "comeback_plan")        # the same block of six minutes
    assert by_id(e.evaluate(comeback_snap(-9, 300)), "comeback_plan")             # the next block, still a real plan
    assert not by_id(e.evaluate(comeback_snap(-9, 120)), "comeback_plan")


def test_c2_the_alert_is_json_serialisable():
    [alert] = comeback(-9)
    assert json.loads(json.dumps(alert.proposal)) == alert.proposal
