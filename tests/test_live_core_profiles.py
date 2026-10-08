"""Player rates, shrinkage and z-scored role profiles.

There is no position data in the feed, so a player's ROLE is inferred from what they do
(rebounding, passing, shot mix, blocks, usage), standardised against the league.
"""

import pytest

from src.live_core.profiles import (
    DEFAULT_LEAGUE,
    METRICS,
    ROLE_DIMS,
    SD_FLOOR_FRACTION,
    league_distribution,
    raw_rates,
    role_distance,
    shrink_rates,
    z_scores,
)

STATS = dict(fg2m=5, fg2a=10, fg3m=2, fg3a=5, ftm=3, fta=4, orb=2, drb=6, tov=3, stl=1, ast=4, blk=1)


def test_raw_rates_by_hand_over_twenty_minutes():
    r = raw_rates(STATS, seconds=1200)  # x2 to per-40
    assert r["orb40"] == pytest.approx(4) and r["drb40"] == pytest.approx(12)
    assert r["ast40"] == pytest.approx(8) and r["tov40"] == pytest.approx(6)
    assert r["fg3a40"] == pytest.approx(10) and r["fg2a40"] == pytest.approx(20)
    assert r["usage40"] == pytest.approx((15 + 0.44 * 4 + 3) * 2)
    assert r["efg"] == pytest.approx((7 + 0.5 * 2) / 15)
    assert r["ftr"] == pytest.approx(4 / 15)


def test_raw_rates_without_minutes_is_none_and_without_shots_is_safe():
    assert raw_rates(STATS, seconds=0) is None
    empty = {k: 0 for k in STATS}
    r = raw_rates(empty, seconds=600)
    assert r["efg"] == 0.0 and r["ftr"] == 0.0 and set(r) == set(METRICS)


def test_shrinkage_pulls_small_samples_towards_the_league():
    league = {m: {"mean": 1.0, "sd": 1.0} for m in METRICS}
    raw = {m: 5.0 for m in METRICS}
    nothing = shrink_rates(raw, seconds=0, fga=0, league=league)
    lots = shrink_rates(raw, seconds=100_000, fga=5_000, league=league)
    assert nothing["orb40"] == pytest.approx(1.0) and nothing["efg"] == pytest.approx(1.0)
    assert lots["orb40"] == pytest.approx(5.0, abs=0.05) and lots["efg"] == pytest.approx(5.0, abs=0.05)
    mid = shrink_rates(raw, seconds=600, fga=30, league=league)
    assert 1.0 < mid["orb40"] < 5.0 and 1.0 < mid["efg"] < 5.0


def test_z_scores_and_sd_floor():
    league = {m: {"mean": 2.0, "sd": DEFAULT_LEAGUE[m]["sd"]} for m in METRICS}
    z = z_scores({m: 2.0 + 2 * DEFAULT_LEAGUE[m]["sd"] for m in METRICS}, league)
    assert all(v == pytest.approx(2.0) for v in z.values())
    flat = {m: {"mean": 2.0, "sd": 0.0} for m in METRICS}
    z_flat = z_scores({m: 3.0 for m in METRICS}, flat)
    for m in METRICS:  # a degenerate spread falls back to a fraction of the default one
        assert z_flat[m] == pytest.approx(1.0 / (SD_FLOOR_FRACTION * DEFAULT_LEAGUE[m]["sd"]))


def test_league_distribution_needs_a_population_else_falls_back_to_defaults():
    few = [raw_rates(STATS, 1200)] * 3
    assert league_distribution(few) == DEFAULT_LEAGUE
    many = [raw_rates({**STATS, "orb": i}, 1200) for i in range(12)]
    dist = league_distribution(many)
    assert set(dist) == set(METRICS)
    assert dist["orb40"]["mean"] == pytest.approx(sum(r["orb40"] for r in many) / 12)
    assert dist["orb40"]["sd"] > 0


def test_role_distance_is_symmetric_zero_for_equal_and_larger_for_different_roles():
    guard = {d: 0.0 for d in ROLE_DIMS} | {"ast40": 2.0, "fg3a40": 1.5, "orb40": -1.0}
    big = {d: 0.0 for d in ROLE_DIMS} | {"orb40": 2.0, "blk40": 1.5, "fg2a40": 1.0, "ast40": -1.0}
    other_guard = {d: 0.0 for d in ROLE_DIMS} | {"ast40": 1.6, "fg3a40": 1.2, "orb40": -0.8}
    assert role_distance(guard, guard) == 0
    assert role_distance(guard, big) == pytest.approx(role_distance(big, guard))
    assert role_distance(guard, other_guard) < role_distance(guard, big)


def test_role_dims_exclude_outcome_quality():
    """Roles describe what a player DOES, not how well: efficiency/turnovers are not role dims."""
    assert "efg" not in ROLE_DIMS and "tov40" not in ROLE_DIMS and "ftr" not in ROLE_DIMS
