"""Sanctions, timeouts and fouls in the finish (issue #245): F1 a player one sanction away from disqualification, F2 the timeout
budget, F4 a key player with four fouls in a close finish, V2 two rivals with three fouls on court.

FIBA: a player is disqualified with two unsportsmanlike fouls, two technical fouls, or one of each.
"""
import copy
import json

import pytest

from live_helpers import TABLE
from src.live_core.advice import RULES, AdviceEngine
from src.live_core.config import RULE_IDS, RuleConfig
from src.live_core.engine import LiveEngine
from tests.test_live_core_advice import OWN, RIVAL, snap

RULE_GROUPS = ("disqualification", "timeout_budget", "key_fouls_close", "rival_foul_pair")


def player(name, team, pf=0, on_court=True, unsportsmanlike=0, technical=0, minutes=600):
    return {"name": name, "team_id": team, "on_court": on_court, "minutes": minutes, "stint": 0, "pf": pf, "pts": 0,
            "pf_by_period": {}, "stats": {}, "unsportsmanlike": unsportsmanlike, "technical": technical}


def snapshot(players=None, elapsed=1000, period=2, remaining=0, score=None, timeouts=None):
    s = snap(elapsed=elapsed, period=period, players=players or {})
    s["remaining"] = remaining
    if score:
        s["score"] = score
    for team, times in (timeouts or {}).items():
        s["teams"][team]["timeouts"] = times
    return s


def evaluate(players=None, elapsed=1000, period=2, remaining=0, score=None, timeouts=None, eng=None, **kw):
    s = snapshot(players, elapsed, period, remaining, score, timeouts)
    return (eng or AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, **kw)).evaluate(s)


def by_id(advices, advice_id):
    return [a for a in advices if a.id == advice_id]


def test_the_rules_are_registered_and_can_be_switched_off():
    for rule_id in RULE_GROUPS:
        assert rule_id in RULE_IDS and rule_id in [rid for rid, _ in RULES]
    off = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, config=RuleConfig(rules_off=("disqualification",)))
    assert not by_id(evaluate({"p1": player("Ana", OWN, unsportsmanlike=1)}, eng=off), "disqualification_risk")


# --- F1: the counters of the state and the alert ------------------------------------------------------------------

def test_the_state_counts_unsportsmanlike_and_technical_fouls_per_player(feb_game_doc):
    snapshot = LiveEngine().update(feb_game_doc)
    counts = {pid: (p["unsportsmanlike"], p["technical"]) for pid, p in snapshot["players"].items()}
    assert counts["2010120"] == (1, 0)                       # the real FALTA Antideportiva of the sample game (4th period, 5:24)
    assert sum(u for u, _ in counts.values()) == 1 and sum(t for _, t in counts.values()) == 0
    assert all(set(p) >= {"unsportsmanlike", "technical"} for p in snapshot["players"].values())


def test_f1_the_sanction_of_the_real_game_is_an_alert_for_its_team(feb_game_doc):
    snapshot = LiveEngine().update(feb_game_doc)
    teams = [t["id"] for t in feb_game_doc["HEADER"]["TEAM"]]
    own, rival = "982047", next(t for t in teams if t != "982047")
    [alert] = by_id(AdviceEngine(own_team_id=own, rival_team_id=rival).evaluate(snapshot), "disqualification_risk")
    assert alert.evidence["player_id"] == "2010120" and "antideportiva" in alert.message and alert.severity == "warning"


@pytest.mark.parametrize("u, t, kind", [(1, 0, "antideportiva"), (0, 1, "técnica")])
def test_f1_one_sanction_means_one_more_and_the_player_is_disqualified(u, t, kind):
    [alert] = by_id(evaluate({"p1": player("Ana", OWN, unsportsmanlike=u, technical=t)}), "disqualification_risk")
    assert alert.severity == "warning" and alert.category == "faltas" and "Ana" in alert.message and kind in alert.message
    assert "descalifica" in alert.message and alert.proposal[0]["type"] == "tactic" and alert.proposal[0]["player_id"] == "p1"


def test_f1_the_rival_with_a_sanction_is_an_opportunity_not_a_warning():
    [alert] = by_id(evaluate({"r1": player("Rita", RIVAL, technical=1)}), "disqualification_risk")
    assert alert.severity == "info" and "Rita" in alert.message and alert.evidence["team_id"] == RIVAL


@pytest.mark.parametrize("u, t", [(0, 0), (2, 0), (0, 2), (1, 1)])
def test_f1_no_sanction_or_already_disqualified_says_nothing(u, t):
    assert not by_id(evaluate({"p1": player("Ana", OWN, unsportsmanlike=u, technical=t)}), "disqualification_risk")


def test_f1_it_is_said_once_for_the_same_sanctions():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL)
    players = {"p1": player("Ana", OWN, unsportsmanlike=1)}
    assert by_id(evaluate(players, eng=e), "disqualification_risk")
    assert not by_id(evaluate(players, elapsed=1100, eng=e), "disqualification_risk")


# --- F2: the timeout budget -----------------------------------------------------------------------------------------

FINISH = dict(period=4, elapsed=2200, remaining=200, score={OWN: 60, RIVAL: 58})


def test_f2_three_timeouts_left_before_the_last_two_minutes_says_to_use_one():
    [alert] = by_id(evaluate(**FINISH), "timeout_budget")
    assert alert.severity == "critical" and alert.evidence["base_severity"] == "warning"     # raised by the close finish
    assert alert.category == "gestion" and "3" in alert.message and "2:00" in alert.message
    assert alert.proposal[0]["type"] == "timeout" and alert.proposal[0]["left"] == 3
    [calm] = by_id(evaluate(**{**FINISH, "score": {OWN: 75, RIVAL: 58}}), "timeout_budget")   # a game that is not close
    assert calm.severity == "warning"


@pytest.mark.parametrize("override", [
    dict(timeouts={OWN: [1300]}),                       # only two left: nothing is lost
    dict(remaining=300, elapsed=2100),                  # too early
    dict(remaining=100, elapsed=2300),                  # inside the last two minutes: it is already lost
    dict(period=3, elapsed=1700, remaining=100),        # not the 4th period
])
def test_f2_it_only_warns_when_a_third_timeout_is_about_to_be_lost(override):
    assert not by_id(evaluate(**{**FINISH, **override}), "timeout_budget")


def test_f2_the_rival_without_timeouts_in_a_close_finish_is_a_reason_to_press():
    [alert] = by_id(evaluate(**FINISH, timeouts={RIVAL: [1300, 1500, 1700]}), "rival_no_timeouts")
    assert alert.severity == "info" and alert.category == "rival" and alert.proposal[0]["type"] == "tactic"
    assert not by_id(evaluate(**FINISH, timeouts={RIVAL: [1300, 1500]}), "rival_no_timeouts")
    far = {**FINISH, "score": {OWN: 70, RIVAL: 55}}
    assert not by_id(evaluate(**far, timeouts={RIVAL: [1300, 1500, 1700]}), "rival_no_timeouts")


def test_f2_each_warning_is_said_once():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL)
    assert by_id(evaluate(**FINISH, eng=e), "timeout_budget")
    assert not by_id(evaluate(**{**FINISH, "elapsed": 2210, "remaining": 190}, eng=e), "timeout_budget")


# --- F4: a key player with four fouls in a close finish ---------------------------------------------------------------

def key_snapshot(pf=4, avg_min=1500, margin=2, remaining=200):
    table = copy.deepcopy(TABLE)
    table["g1"]["avg_min"] = avg_min
    players = {"g1": player("Guard Uno", OWN, pf=pf)}
    return dict(players=players, baselines=table, period=4, elapsed=2200, remaining=remaining, score={OWN: 60, RIVAL: 60 - margin})


def test_f4_a_key_player_with_four_fouls_in_a_close_finish_defends_without_risk():
    [alert] = by_id(evaluate(**key_snapshot()), "key_fouls_close")
    assert alert.category == "faltas" and alert.severity == "critical"          # warning raised by the closing stretch
    assert "Guard Uno" in alert.message and "cierre" in alert.message
    assert alert.proposal[0]["type"] == "tactic" and "sin riesgo" in alert.proposal[0]["message"].lower()


@pytest.mark.parametrize("kw", [dict(pf=3), dict(avg_min=600), dict(margin=15), dict(remaining=400)])
def test_f4_it_needs_a_key_player_four_fouls_and_a_close_finish(kw):
    assert not by_id(evaluate(**key_snapshot(**kw)), "key_fouls_close")


# --- V2: two rivals with three fouls on court -----------------------------------------------------------------------------

def test_v2_two_rivals_with_three_fouls_on_court_are_to_be_attacked():
    players = {"r1": player("Rita", RIVAL, pf=3), "r2": player("Rosa", RIVAL, pf=4), "r3": player("Rut", RIVAL, pf=1)}
    [alert] = by_id(evaluate(players), "rival_foul_pair")
    assert alert.severity == "warning" and alert.category == "faltas" and "Rita" in alert.message and "Rosa" in alert.message
    assert alert.proposal[0]["type"] == "tactic"


@pytest.mark.parametrize("players", [
    {"r1": player("Rita", RIVAL, pf=3), "r2": player("Rosa", RIVAL, pf=2)},
    {"r1": player("Rita", RIVAL, pf=3), "r2": player("Rosa", RIVAL, pf=3, on_court=False)},
    {"p1": player("Ana", OWN, pf=3), "p2": player("Bea", OWN, pf=4)},
])
def test_v2_one_rival_with_fouls_on_court_or_our_own_players_are_not_a_pair(players):
    assert not by_id(evaluate(players), "rival_foul_pair")


def test_v2_a_new_pair_is_not_said_again_within_five_minutes_but_it_is_not_lost():
    """Reevaluation 22/10/2026: 61 % of the pair alerts repeated one a few minutes before (a third foul changes the pair)."""
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL)
    first = {"r1": player("Rita", RIVAL, pf=3), "r2": player("Rosa", RIVAL, pf=4), "r3": player("Rut", RIVAL, pf=1)}
    assert by_id(evaluate(first, elapsed=1000, eng=e), "rival_foul_pair")
    changed = {**first, "r3": player("Rut", RIVAL, pf=3)}                      # a third rival reaches three fouls: another pair
    assert not by_id(evaluate(changed, elapsed=1100, eng=e), "rival_foul_pair")
    assert not by_id(evaluate(changed, elapsed=1250, eng=e), "rival_foul_pair")
    assert by_id(evaluate(changed, elapsed=1300, eng=e), "rival_foul_pair")


def test_v2_the_same_pair_keeps_being_the_same_alert():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL)
    pair = {"r1": player("Rita", RIVAL, pf=3), "r2": player("Rosa", RIVAL, pf=4)}
    assert by_id(evaluate(pair, elapsed=1000, eng=e), "rival_foul_pair")
    assert not by_id(evaluate(pair, elapsed=2000, eng=e), "rival_foul_pair")


def test_the_alerts_are_json_serialisable():
    [alert] = by_id(evaluate({"p1": player("Ana", OWN, unsportsmanlike=1)}), "disqualification_risk")
    assert json.loads(json.dumps(alert.proposal)) == alert.proposal
