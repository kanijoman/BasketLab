"""Dean Oliver's Four Factors with Oliver's weights (eFG 40%, TOV 25%, ORB 20%, FT 15%),
shrinkage towards the season prior, the "main lever" and the final-margin projection.

Conventions (project-wide): possessions = FGA - ORB + TOV + 0.44*FTA; TOV% = TOV/(FGA +
0.44*FTA + TOV); FTr = FTA/FGA. Team turnovers (no player) count as turnovers here.
"""

import pytest

from src.live_core.config import RuleConfig
from src.live_core.four_factors import (
    WEIGHTS,
    FourFactorsModel,
    differentials,
    factors,
    possessions,
    shrink,
)


def stats(**kw):
    base = dict(fg2m=20, fg2a=40, fg3m=6, fg3a=20, ftm=10, fta=14, orb=8, drb=25,
                tov=10, tov_team=0, stl=5, ast=12, blk=2, pts=0)
    base.update(kw)
    return base


OWN, RIVAL = stats(), stats(fg2m=18, fg2a=38, fg3m=5, fg3a=18, ftm=8, fta=10, orb=6, drb=20, tov=12)


def test_weights_are_olivers_and_sum_to_one():
    assert WEIGHTS == {"efg": 0.40, "tov": 0.25, "orb": 0.20, "ftr": 0.15}
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_possessions_formula():
    # FGA 60 - ORB 8 + TOV 10 + 0.44 * 14
    assert possessions(OWN) == pytest.approx(60 - 8 + 10 + 0.44 * 14)


def test_team_turnovers_count_as_possessions_lost():
    assert possessions(stats(tov_team=2)) == pytest.approx(possessions(OWN) + 2)


def test_factors_by_hand():
    f = factors(OWN, RIVAL)
    assert f["efg"] == pytest.approx((26 + 0.5 * 6) / 60)
    assert f["tov"] == pytest.approx(10 / (60 + 0.44 * 14 + 10))
    assert f["orb"] == pytest.approx(8 / (8 + RIVAL["drb"]))
    assert f["ftr"] == pytest.approx(14 / 60)


def test_differentials_are_positive_when_good_for_own_team():
    d = differentials(OWN, RIVAL)
    assert d["efg"] > 0                      # own shoots better
    assert d["tov"] > 0                      # own turns it over LESS than the rival
    own_f, riv_f = factors(OWN, RIVAL), factors(RIVAL, OWN)
    assert d["tov"] == pytest.approx(riv_f["tov"] - own_f["tov"])
    assert d["orb"] == pytest.approx(own_f["orb"] - riv_f["orb"])
    assert d["ftr"] == pytest.approx(own_f["ftr"] - riv_f["ftr"])


def test_zero_attempts_do_not_crash():
    empty = stats(fg2m=0, fg2a=0, fg3m=0, fg3a=0, ftm=0, fta=0, orb=0, drb=0, tov=0)
    assert possessions(empty) == 0
    assert all(isinstance(v, float) for v in factors(empty, empty).values())


def test_shrink_blends_observation_and_prior_by_sample_size():
    assert shrink(obs=0.10, prior=0.02, n=0, n0=40) == pytest.approx(0.02)
    assert shrink(obs=0.10, prior=0.02, n=40, n0=40) == pytest.approx(0.06)
    assert shrink(obs=0.10, prior=0.02, n=10_000, n0=40) == pytest.approx(0.10, abs=1e-3)


# --- model on snapshots -------------------------------------------------------------

def snapshot(own, rival, elapsed=1200, score=(40, 40)):
    return {"elapsed": elapsed, "period": 3, "remaining": 0,
            "score": {"A": score[0], "B": score[1]},
            "teams": {"A": {"stats": own}, "B": {"stats": rival}}}


def model(**kw):
    return FourFactorsModel(own_team_id="A", rival_team_id="B", **kw)


def test_result_is_none_without_both_teams():
    assert FourFactorsModel(own_team_id="A", rival_team_id=None).evaluate(snapshot(OWN, RIVAL)) is None


def test_partial_snapshot_without_stats_returns_none():
    partial = {"elapsed": 100, "period": 1, "remaining": 500, "score": {"A": 0, "B": 0},
               "teams": {"A": {"stats": {}}, "B": {}}}
    assert model().evaluate(partial) is None


def test_balanced_game_has_no_lever_and_no_edge():
    res = model().evaluate(snapshot(OWN, dict(OWN)))
    assert res["score"] == pytest.approx(0.0, abs=1e-9)
    assert res["lever"] is None
    assert res["expected_net_rtg"] == pytest.approx(0.0, abs=1e-9)


def test_reliability_needs_enough_possessions():
    tiny = stats(fg2m=2, fg2a=4, fg3m=0, fg3a=1, ftm=0, fta=0, orb=0, drb=2, tov=1)
    assert model().evaluate(snapshot(tiny, tiny))["reliable"] is False
    assert model().evaluate(snapshot(OWN, RIVAL))["reliable"] is True


def test_main_lever_is_the_most_damaging_weighted_deficit():
    careless = stats(tov=22)        # only turnovers are bad
    res = model().evaluate(snapshot(careless, dict(OWN, tov=10)))
    assert res["lever"] == "tov"
    assert res["contributions"]["tov"] < 0
    assert res["pts100"]["tov"] < 0


def test_shooting_lever_when_efg_is_the_problem():
    cold = stats(fg2m=10, fg3m=2, ftm=10)
    res = model().evaluate(snapshot(cold, dict(OWN)))
    assert res["lever"] == "efg"


def test_prior_pulls_early_differentials_towards_the_season_expectation():
    early = snapshot(stats(fg2m=0, fg2a=6, fg3m=0, fg3a=2, ftm=0, fta=0, orb=0, drb=3, tov=3), dict(OWN), elapsed=240)
    cold = model().evaluate(early)
    prior = {"four_factors_prior": {"efg": 0.06, "tov": 0.0, "orb": 0.0, "ftr": 0.0}}
    warmed = model(baselines=prior).evaluate(early)
    assert warmed["shrunk"]["efg"] > cold["shrunk"]["efg"]


def test_projection_with_no_edge_keeps_the_current_margin():
    res = model().evaluate(snapshot(OWN, dict(OWN), elapsed=1200, score=(40, 45)))
    assert res["projection"]["margin_now"] == -5
    assert res["projection"]["projected_margin"] == pytest.approx(-5, abs=1e-6)


def test_projection_moves_with_the_edge_and_the_time_left():
    ahead_in_factors = snapshot(OWN, RIVAL, elapsed=1200, score=(40, 45))
    late = snapshot(OWN, RIVAL, elapsed=2200, score=(40, 45))
    p_mid = model().evaluate(ahead_in_factors)["projection"]
    p_late = model().evaluate(late)["projection"]
    assert p_mid["projected_margin"] > p_mid["margin_now"]
    assert p_mid["poss_remaining"] > p_late["poss_remaining"]
    assert abs(p_late["projected_margin"] - p_late["margin_now"]) < abs(p_mid["projected_margin"] - p_mid["margin_now"])


def test_no_time_left_means_the_projection_is_the_score():
    res = model().evaluate(snapshot(OWN, RIVAL, elapsed=2400, score=(80, 77)))
    assert res["projection"]["poss_remaining"] == 0
    assert res["projection"]["projected_margin"] == 3


def test_result_is_json_serialisable():
    import json
    json.dumps(model().evaluate(snapshot(OWN, RIVAL)))


def test_config_exposes_the_tuning_knobs():
    cfg = RuleConfig()
    assert cfg.ff_min_possessions > 0 and cfg.ff_beta > 0 and cfg.ff_lever_min_pts100 > 0


# --- agreement with the official box score of the real sample game ------------------

def test_engine_stats_reproduce_the_box_score_four_factors(feb_game_doc):
    from src.live_core.engine import LiveEngine

    snap = LiveEngine().update(feb_game_doc)
    ids = [t["id"] for t in feb_game_doc["HEADER"]["TEAM"]]
    box = {t["id"]: t["TOTAL"] for t in feb_game_doc["BOXSCORE"]["TEAM"]}
    for tid in ids:
        f = factors(snap["teams"][tid]["stats"], snap["teams"][[i for i in ids if i != tid][0]]["stats"])
        b = box[tid]
        efg_box = (int(b["fgm"]) + 0.5 * int(b["p3m"])) / int(b["fga"])
        assert f["efg"] == pytest.approx(efg_box)
        assert f["ftr"] == pytest.approx(int(b["p1a"]) / int(b["fga"]))
