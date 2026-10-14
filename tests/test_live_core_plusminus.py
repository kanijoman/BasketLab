"""Quintets and plus/minus (issue #248): R9 the quintet on court is losing, J7 a player on court has a very negative +/-.

Both read the stint of the quintet / the player (what happened since they came in), not the whole game.
"""
import json

import pytest

from live_helpers import OWN, RIVAL, TABLE, snap
from src.live_core.advice import RULES, AdviceEngine
from src.live_core.config import RULE_IDS, RuleConfig
from src.live_core.lineups import lineup_key

FIVE = ["g1", "w1", "w2", "b1", "g3"]          # the five on court of live_helpers.snap


def stage(net=-6, seconds=180, since=1000, elapsed=1200, stint_pm=None, stint=None, rival_net=None):
    """A snapshot where our quintet has ``net`` points (for - against) in ``seconds`` and the players have their stint +/-."""
    s = snap(period=3, elapsed=elapsed)
    s["lineup_now"] = {OWN: {"players": sorted(FIVE), "since": since, "seconds": seconds,
                             "pts_for": max(net, 0), "pts_against": max(-net, 0)}, RIVAL: None}
    if rival_net is not None:
        s["lineup_now"][RIVAL] = {"players": ["r1", "r2", "r3", "r4", "r5"], "since": since, "seconds": seconds,
                                  "pts_for": 0, "pts_against": 20}
    for pid, p in s["players"].items():
        p["pm"], p["stint_pm"] = 0, (stint_pm or {}).get(pid, 0)
        if pid in FIVE and stint is not None:
            p["stint"] = stint
    return s


def engine(**kw):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, **kw)


def by_id(advices, advice_id):
    return [a for a in advices if a.id == advice_id]


def test_the_rules_are_registered_and_can_be_switched_off():
    for rule_id in ("lineup_net", "player_plus_minus"):
        assert rule_id in RULE_IDS and rule_id in [rid for rid, _ in RULES]
    off = engine(config=RuleConfig(rules_off=("lineup_net",)))
    assert not by_id(off.evaluate(stage()), "lineup_net")


# --- R9: the quintet --------------------------------------------------------------------------------------------------

def test_r9_a_quintet_six_down_after_three_minutes_says_to_consider_a_change_with_who_could_come_in():
    [alert] = by_id(engine(baselines=TABLE).evaluate(stage(stint_pm={"b1": -6})), "lineup_net")
    assert alert.severity == "warning" and alert.category == "rotacion"
    assert "-6" in alert.message and "3:00" in alert.message and "cambio" in alert.message.lower()
    assert alert.evidence["net"] == -6 and alert.evidence["players"] == sorted(FIVE)
    assert any(p["type"] == "sub" and p["out_id"] == "b1" for p in alert.proposal)          # the worst of the five goes out


@pytest.mark.parametrize("kw", [dict(net=-5), dict(seconds=179), dict(net=4)])
def test_r9_it_needs_at_least_six_down_and_three_minutes(kw):
    assert not by_id(engine(baselines=TABLE).evaluate(stage(**kw)), "lineup_net")


def test_r9_it_is_said_once_per_stint_of_the_quintet_and_again_in_a_new_one():
    e = engine()
    assert by_id(e.evaluate(stage()), "lineup_net")
    assert not by_id(e.evaluate(stage(seconds=200, net=-8)), "lineup_net")
    assert by_id(e.evaluate(stage(since=1500, elapsed=1700)), "lineup_net")


def test_r9_only_our_quintet_counts():
    s = stage(net=0, seconds=60, rival_net=-20)
    assert not by_id(engine().evaluate(s), "lineup_net")
    s["lineup_now"] = {OWN: None, RIVAL: s["lineup_now"][RIVAL]}
    assert not by_id(engine().evaluate(s), "lineup_net")


def test_r9_the_season_of_the_quintet_in_the_package_is_added_when_it_has_enough_minutes():
    row = {"team_id": OWN, "players": sorted(FIVE), "seconds": 1500, "pts_for": 40, "pts_against": 30, "stints": 9, "games": 4, "net40": 16.0}
    [alert] = by_id(engine(lineups=[row]).evaluate(stage()), "lineup_net")
    assert "temporada" in alert.message and "+16.0" in alert.message and "25 min" in alert.message
    small = {**row, "seconds": 300}
    [plain] = by_id(engine(lineups=[small]).evaluate(stage()), "lineup_net")
    assert "temporada" not in plain.message


# --- J7: the player -----------------------------------------------------------------------------------------------------

def test_j7_a_player_very_negative_in_his_stint_is_to_be_replaced_with_the_recommender_proposal():
    s = stage(net=0, seconds=60, stint_pm={"g1": -9}, stint=300)
    [alert] = by_id(engine(baselines=TABLE).evaluate(s), "player_plus_minus")
    assert alert.severity == "info" and alert.category == "rotacion" and "Guard Uno" in alert.message and "-9" in alert.message
    assert alert.evidence["player_id"] == "g1" and any(p["type"] == "sub" and p["out_id"] == "g1" for p in alert.proposal)


@pytest.mark.parametrize("pm, stint", [(-7, 300), (-9, 239), (3, 300)])
def test_j7_it_needs_eight_down_in_a_stint_of_four_minutes(pm, stint):
    s = stage(net=0, seconds=60, stint_pm={"g1": pm}, stint=stint)
    assert not by_id(engine(baselines=TABLE).evaluate(s), "player_plus_minus")


def test_j7_the_bench_does_not_count_and_it_is_said_once_per_stint():
    s = stage(net=0, seconds=60, stint_pm={"g2": -12}, stint=300)
    assert not by_id(engine(baselines=TABLE).evaluate(s), "player_plus_minus")
    e = engine(baselines=TABLE)
    bad = stage(net=0, seconds=60, stint_pm={"g1": -9}, stint=300)
    assert by_id(e.evaluate(bad), "player_plus_minus")
    assert not by_id(e.evaluate(stage(net=0, seconds=70, stint_pm={"g1": -10}, stint=310, elapsed=1210)), "player_plus_minus")


def test_the_alerts_are_json_serialisable():
    [alert] = by_id(engine(baselines=TABLE).evaluate(stage()), "lineup_net")
    assert json.loads(json.dumps(alert.proposal)) == alert.proposal


def test_the_lineup_key_is_the_sorted_ids_joined():
    assert lineup_key(["b", "a", "c"]) == "a|b|c"


# --- J7 refined: an individual problem, not a slump of the whole quintet -----------------------------------------------------

def test_j7_if_the_whole_quintet_is_down_it_is_a_lineup_problem_and_nobody_is_singled_out():
    s = stage(net=0, seconds=60, stint_pm={pid: -9 for pid in FIVE}, stint=300)
    assert not by_id(engine(baselines=TABLE).evaluate(s), "player_plus_minus")


def test_j7_a_player_only_a_little_worse_than_his_teammates_is_not_singled_out():
    s = stage(net=0, seconds=60, stint_pm={"g1": -9, "w1": -8, "w2": -8, "b1": -7, "g3": -8}, stint=300)
    assert not by_id(engine(baselines=TABLE).evaluate(s), "player_plus_minus")


def test_j7_it_stays_quiet_while_the_quintet_alert_is_already_there():
    s = stage(net=-8, seconds=240, stint_pm={"g1": -12}, stint=300)
    out = engine(baselines=TABLE).evaluate(s)
    assert by_id(out, "lineup_net") and not by_id(out, "player_plus_minus")
