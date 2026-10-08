"""Alerts carry concrete proposals (who comes in for whom) from the recommender."""

import dataclasses
import json

from live_helpers import OWN, RIVAL, TABLE, snap
from src.live_core.advice import AdviceEngine


def engine(table=TABLE):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, baselines=table)


def by_id(advices, advice_id):
    return [a for a in advices if a.id == advice_id]


def _stats(**kw):
    base = dict(fg2m=20, fg2a=40, fg3m=6, fg3a=20, ftm=10, fta=14, orb=8, drb=25,
                tov=10, tov_team=0, stl=5, ast=12, blk=2, pts=0)
    base.update(kw)
    return base


def with_teams(s, own_stats, rival_stats=None):
    team = {"name": "x", "fouls_game": 0, "timeouts": [], "fouls_by_period": {}}
    s["teams"] = {OWN: {**team, "stats": own_stats}, RIVAL: {**team, "stats": rival_stats or _stats()}}
    s["score"] = {OWN: 40, RIVAL: 40}
    return s


def test_foul_trouble_proposes_a_role_similar_replacement():
    s = snap(period=2, overrides={"b1": {"pf": 3}})
    [alert] = by_id(engine().evaluate(s), "foul_trouble")
    assert alert.proposal and alert.proposal[0]["out_id"] == "b1"
    assert alert.proposal[0]["in_id"] in ("b2", "b3")
    assert all(p["type"] == "sub" for p in alert.proposal)


def test_fatigue_proposes_a_replacement_for_the_tired_player():
    s = snap(period=2, elapsed=1500, overrides={"g1": {"stint": 900, "minutes": 1400}})
    [alert] = by_id(engine().evaluate(s), "fatigue_high")
    assert alert.proposal[0]["out_id"] == "g1" and alert.proposal[0]["in_id"] == "g2"


def test_four_factors_lever_proposes_who_to_bring_in_for_that_lever():
    s = with_teams(snap(elapsed=1200), _stats(tov=22))
    [alert] = by_id(engine().evaluate(s), "four_factors_lever")
    assert alert.evidence["lever"] == "tov"
    assert alert.proposal and alert.proposal[0]["out_id"] == "g1" and alert.proposal[0]["in_id"] == "g2"
    assert all(p["lever"] == "tov" and p["lever_gain"] > 0 for p in alert.proposal)


def test_turnover_streak_proposes_ball_security():
    s = snap(elapsed=1200)
    s["log"] = [[1000 + 30 * i, OWN, "tov", 1] for i in range(4)]
    [alert] = by_id(engine().evaluate(s), "turnover_streak")
    assert alert.proposal and alert.proposal[0]["in_id"] == "g2"


def test_foul_swaps_are_ranked_by_the_current_lever_when_there_is_one():
    s = with_teams(snap(period=2, elapsed=1200, overrides={"g1": {"pf": 3}}), _stats(tov=22))
    [alert] = by_id(engine().evaluate(s), "foul_trouble")
    assert alert.proposal[0]["lever"] == "tov"


def test_a_scoring_run_gets_no_substitution_proposal():
    s = snap(elapsed=1110)
    s["log"] = [[1000, RIVAL, "pts", 3], [1040, RIVAL, "pts", 2], [1100, RIVAL, "pts", 3]]
    [alert] = by_id(engine().evaluate(s), "rival_run")
    assert alert.proposal == []


def test_without_player_baselines_alerts_still_fire_without_proposals():
    s = snap(period=2, overrides={"b1": {"pf": 3}})
    [alert] = by_id(AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL).evaluate(s), "foul_trouble")
    assert alert.proposal == []


def test_a_repeated_alert_is_not_emitted_again_with_its_proposal():
    eng = engine()
    s = snap(period=2, overrides={"b1": {"pf": 3}})
    assert by_id(eng.evaluate(s), "foul_trouble")
    assert eng.evaluate(s) == []


def test_proposals_are_json_serialisable():
    s = snap(period=2, overrides={"b1": {"pf": 3}})
    [alert] = by_id(engine().evaluate(s), "foul_trouble")
    json.dumps(dataclasses.asdict(alert))
