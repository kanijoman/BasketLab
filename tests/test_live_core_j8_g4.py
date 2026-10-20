"""J8 (issue #251): an own player with several offensive rebounds is to stay on court; G4 (issue #252): static play, few assisted
baskets, move the ball."""
import json

import pytest

from src.live_core.advice import RULES, AdviceEngine
from src.live_core.config import RULE_IDS, RuleConfig
from tests.test_live_core_advice import OWN, RIVAL, snap

STATS0 = {k: 0 for k in ("fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta", "orb", "drb", "tov", "stl", "ast", "blk")}


def player(name, orb=0, minutes=900, on_court=True, team=OWN):
    return {"name": name, "team_id": team, "on_court": on_court, "minutes": minutes, "stint": 0, "pf": 0, "pts": 0,
            "pf_by_period": {}, "stats": {**STATS0, "orb": orb}}


USUAL = {"p1": {"rates": {"orb40": 1.5}, "avg_min": 1200, "z": {}}}


def engine(**kw):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, **kw)


def by_id(advices, advice_id):
    return [a for a in advices if a.id == advice_id]


def orb_snap(orb, minutes=900, on_court=True, elapsed=1000):
    s = snap(elapsed=elapsed, period=2, players={"p1": player("Ana", orb, minutes, on_court)})
    s["remaining"] = 200
    return s


# --- J8 ---------------------------------------------------------------------------------------------------------------

def test_the_rules_are_registered_and_can_be_switched_off():
    for rule_id in ("own_orb_player", "static_offense"):
        assert rule_id in RULE_IDS and rule_id in [rid for rid, _ in RULES]
    off = engine(baselines=USUAL, config=RuleConfig(rules_off=("own_orb_player",)))
    assert not by_id(off.evaluate(orb_snap(4)), "own_orb_player")


def test_j8_a_player_with_three_offensive_rebounds_well_above_her_usual_is_to_stay_on_court():
    [alert] = by_id(engine(baselines=USUAL).evaluate(orb_snap(4)), "own_orb_player")
    assert alert.severity == "info" and alert.category == "four_factors" and "Ana" in alert.message and "4 rebotes ofensivos" in alert.message
    assert "mantener" in alert.proposal[0]["message"].lower() and alert.proposal[0]["player_id"] == "p1"


@pytest.mark.parametrize("orb, minutes, on_court", [(2, 900, True), (3, 2200, True), (4, 900, False)])
def test_j8_it_needs_three_rebounds_above_the_usual_and_the_player_on_court(orb, minutes, on_court):
    assert not by_id(engine(baselines=USUAL).evaluate(orb_snap(orb, minutes, on_court)), "own_orb_player")


def test_j8_without_a_baseline_it_uses_the_league_rate_and_it_is_said_again_each_three_rebounds():
    e = engine()
    assert by_id(e.evaluate(orb_snap(4)), "own_orb_player")
    assert not by_id(e.evaluate(orb_snap(5, elapsed=1100)), "own_orb_player")
    assert by_id(e.evaluate(orb_snap(7, elapsed=1300)), "own_orb_player")


def test_j8_the_fatigue_warning_of_that_player_goes_down_a_level_and_says_why():
    from live_helpers import TABLE, snap as roster_snap

    cfg = RuleConfig(fatigue_alert_index=10, fatigue_warning_index=20, fatigue_critical_index=30)
    s = roster_snap(period=1, elapsed=580, overrides={"g1": {"stint": 560, "minutes": 560}})
    s["players"]["g1"]["stats"] = {**STATS0, "orb": 4}
    [alert] = by_id(AdviceEngine(own_team_id="T1", rival_team_id="T2", baselines=TABLE, config=cfg).evaluate(s), "fatigue_high")
    assert alert.severity == "warning" and "rebote ofensivo" in alert.message


# --- G4 ---------------------------------------------------------------------------------------------------------------

def team_snap(fgm, ast, period=2):
    s = snap(elapsed=1000, period=period)
    s["remaining"] = 200
    s["teams"][OWN]["stats"] = {**STATS0, "fg2m": fgm - 2, "fg3m": 2, "ast": ast}
    return s


def test_g4_few_assisted_baskets_say_to_move_the_ball():
    [alert] = by_id(engine().evaluate(team_snap(14, 4)), "static_offense")
    assert alert.severity == "info" and alert.category == "four_factors" and "4 asistencias en 14 canastas" in alert.message
    assert alert.proposal[0]["type"] == "tactic" and "balón" in alert.proposal[0]["message"].lower()
    assert alert.evidence == {"ast": 4, "fgm": 14, "share": 0.286}


@pytest.mark.parametrize("fgm, ast", [(9, 1), (14, 5), (20, 12)])
def test_g4_it_needs_ten_baskets_and_an_assist_share_below_a_third_and_a_bit(fgm, ast):
    assert not by_id(engine().evaluate(team_snap(fgm, ast)), "static_offense")


def test_g4_it_is_said_once_per_half_and_the_alert_is_json_serialisable():
    e = engine()
    [alert] = by_id(e.evaluate(team_snap(14, 4)), "static_offense")
    assert json.loads(json.dumps(alert.proposal)) == alert.proposal
    assert not by_id(e.evaluate(team_snap(16, 4)), "static_offense")
    assert by_id(e.evaluate(team_snap(30, 8, period=3)), "static_offense")
