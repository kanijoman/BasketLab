"""Rival players "doing damage": production well above what their season rate predicts.

Expected count = (season rate per 40, shrunk to the league) x minutes played; an alert needs
a minimum count AND an excess of `rival_sigma` Poisson standard deviations. Only players on
court are flagged. Without matchup data the response is tactical text, plus replacement
proposals where own-team data supports them (defensive rebounding, ball security).
"""

import math

import pytest

from live_helpers import OWN, RIVAL, TABLE, snap
from src.live_core.advice import AdviceEngine
from src.live_core.config import RuleConfig
from src.live_core.profiles import (
    DEFAULT_IMPACT_LEAGUE,
    IMPACT_METRICS,
    impact_league,
    impact_rates,
    shrink_impact,
)

STATS = dict(fg2m=5, fg2a=10, fg3m=2, fg3a=5, ftm=3, fta=4, orb=2, drb=6, tov=3, stl=1, ast=4, blk=1)


# --- impact rates -------------------------------------------------------------------

def test_impact_rates_by_hand():
    r = impact_rates(STATS, seconds=1200)  # x2 to per-40
    assert r["pts"] == pytest.approx((2 * 5 + 3 * 2 + 3) * 2)
    assert r["orb"] == pytest.approx(4) and r["stl"] == pytest.approx(2) and r["ast"] == pytest.approx(8)
    assert r["fg3m"] == pytest.approx(4) and r["fta"] == pytest.approx(8)
    assert impact_rates(STATS, seconds=0) is None
    assert set(r) == set(IMPACT_METRICS)


def test_impact_shrinkage_and_league_defaults():
    league = {m: 10.0 for m in IMPACT_METRICS}
    raw = {m: 30.0 for m in IMPACT_METRICS}
    assert shrink_impact(raw, 0, league)["pts"] == pytest.approx(10.0)
    assert shrink_impact(raw, 100_000, league)["pts"] == pytest.approx(30.0, abs=0.2)
    assert impact_league([]) == DEFAULT_IMPACT_LEAGUE
    many = [impact_rates({**STATS, "orb": i}, 1200) for i in range(12)]
    assert impact_league(many)["orb"] == pytest.approx(sum(r["orb"] for r in many) / 12)


# --- the rule -----------------------------------------------------------------------

BASELINES = {"r1": {"name": "Rival Uno", "impact40": {"pts": 14.0, "orb": 1.5, "stl": 1.4, "ast": 3.5, "fg3m": 1.7, "fta": 3.5}}}


def rival_snap(stats_over=None, minutes=840, pts=None, on_court=True, pid="r1", elapsed=1500):
    s = snap(elapsed=elapsed)
    stats = {k: 0 for k in ("fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta", "orb", "drb", "tov", "stl", "ast", "blk")}
    stats.update(stats_over or {})
    s["players"][pid] = {"name": "Rival Uno", "team_id": RIVAL, "on_court": on_court, "pf": 0, "minutes": minutes,
                         "stint": 300, "pts": pts if pts is not None else 0, "pf_by_period": {}, "stats": stats}
    return s


def eng(**kw):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, rival_baselines=BASELINES, **kw)


def hot(advices):
    return [a for a in advices if a.id == "rival_hot_player"]


def test_offensive_rebounds_well_above_the_season_rate_raise_an_alert():
    # 14 min played: expected ORB = 1.5 * 840/2400 = 0.53; four is far above
    [a] = hot(eng().evaluate(rival_snap({"orb": 4})))
    assert a.severity == "warning" and a.category == "rival" and a.evidence["metric"] == "orb"
    assert a.evidence["observed"] == 4 and a.evidence["expected"] == pytest.approx(0.525, abs=0.01)
    assert "Rival Uno" in a.message and "rebotes ofensivos" in a.message.lower()


def test_scoring_alert_uses_the_player_points():
    [a] = hot(eng().evaluate(rival_snap(pts=17)))   # expected 14 * 0.35 = 4.9
    assert a.evidence["metric"] == "pts" and "pts" in a.message


@pytest.mark.parametrize("metric,count", [("stl", 4), ("ast", 6), ("fg3m", 4), ("fta", 7)])
def test_each_metric_can_trigger(metric, count):
    assert [a.evidence["metric"] for a in hot(eng().evaluate(rival_snap({metric: count})))] == [metric]


def test_two_metrics_two_alerts():
    out = hot(eng().evaluate(rival_snap({"orb": 4, "stl": 4}, pts=18)))
    assert {a.evidence["metric"] for a in out} == {"pts", "orb", "stl"}


def test_no_alert_when_production_is_normal_or_below_the_minimum_count():
    assert hot(eng().evaluate(rival_snap({"orb": 1, "stl": 1, "ast": 2}, pts=5))) == []
    assert hot(eng().evaluate(rival_snap({"orb": 2}))) == []          # above expected but under the minimum of 3


def test_a_high_expected_rate_needs_a_bigger_excess():
    busy = {"r1": {"name": "Rival Uno", "impact40": {**BASELINES["r1"]["impact40"], "orb": 6.0}}}
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, rival_baselines=busy)
    assert hot(e.evaluate(rival_snap({"orb": 4}))) == []   # expected 2.1: 4 is not unusual for this player


def test_only_players_on_court_with_enough_minutes_are_flagged():
    assert hot(eng().evaluate(rival_snap({"orb": 4}, on_court=False))) == []
    assert hot(eng().evaluate(rival_snap({"orb": 4}, minutes=120))) == []


def test_own_players_are_never_flagged_as_rival_threats():
    s = rival_snap({"orb": 4}, pid="o9")
    s["players"]["o9"]["team_id"] = OWN
    assert hot(AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL).evaluate(s)) == []


def test_without_a_player_baseline_the_league_average_is_used():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL)   # no rival baselines at all
    [a] = hot(e.evaluate(rival_snap({"orb": 5})))
    assert a.evidence["expected"] == pytest.approx(DEFAULT_IMPACT_LEAGUE["orb"] * 840 / 2400, abs=0.01)
    assert a.evidence["has_baseline"] is False


def test_each_alert_is_emitted_once():
    e = eng()
    s = rival_snap({"orb": 4})
    assert hot(e.evaluate(s)) and hot(e.evaluate(s)) == []


def test_poisson_threshold_comes_from_the_config():
    strict = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, rival_baselines=BASELINES,
                          config=RuleConfig(rival_sigma=9.0))
    assert hot(strict.evaluate(rival_snap({"orb": 4}))) == []
    excess = 4 - 0.525
    assert excess / math.sqrt(1.0) > RuleConfig().rival_sigma


# --- proposals ----------------------------------------------------------------------

def test_offensive_rebounding_threat_proposes_better_defensive_rebounders():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, baselines=TABLE, rival_baselines=BASELINES)
    [a] = hot(e.evaluate(rival_snap({"orb": 4})))
    for p in a.proposal:
        assert p["lever"] == "def_reb" and p["lever_gain"] > 0
    assert "bloque" in a.message.lower() or "rebote" in a.message.lower()


def test_threats_without_data_to_support_a_swap_get_tactical_text_only():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, baselines=TABLE, rival_baselines=BASELINES)
    [a] = hot(e.evaluate(rival_snap(pts=17)))
    assert a.proposal == [] and ("ayuda" in a.message.lower() or "doblar" in a.message.lower())
