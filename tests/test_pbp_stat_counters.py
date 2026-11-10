"""The counters both the IN/OUT and the lineup calculators write to: one definition of the empty bucket and of how a team/rival stat is bumped (#200, #452)."""
import pytest

from src.database.pbp_stat_counters import STAT_KEYS, add_points, bump, count_rebound, count_shot, empty_stats


def test_the_empty_bucket_has_every_stat_for_the_team_and_for_the_rival_and_the_points():
    stats = empty_stats()
    assert set(stats) == {"points_for", "points_against", *STAT_KEYS, *(f"opp_{k}" for k in STAT_KEYS)}
    assert set(stats.values()) == {0}
    assert empty_stats() is not stats                       # a new dict each time: the IN and the OUT buckets must not share counters


@pytest.mark.parametrize("is_team, key", [(True, "ast"), (False, "opp_ast")])
def test_bump_writes_the_team_key_or_the_rival_key(is_team, key):
    stats = empty_stats()
    bump(stats, "ast", is_team)
    assert {k: v for k, v in stats.items() if v} == {key: 1}


@pytest.mark.parametrize("kind, made, is_team, expected", [
    (2, True, True, {"fga_2": 1, "fgm_2": 1}),
    (2, False, True, {"fga_2": 1}),
    (3, True, False, {"opp_fga_3": 1, "opp_fgm_3": 1}),
    (3, False, False, {"opp_fga_3": 1}),
    (1, True, True, {"fta": 1, "ftm": 1}),
    (1, False, False, {"opp_fta": 1}),
])
def test_count_shot_counts_the_attempt_and_the_make_by_kind(kind, made, is_team, expected):
    stats = empty_stats()
    count_shot(stats, kind, made, is_team)
    assert {k: v for k, v in stats.items() if v} == expected


@pytest.mark.parametrize("offensive, is_team, key", [(True, True, "orb"), (False, True, "drb"), (True, False, "opp_orb"), (False, False, "opp_drb")])
def test_count_rebound(offensive, is_team, key):
    stats = empty_stats()
    count_rebound(stats, offensive, is_team)
    assert {k: v for k, v in stats.items() if v} == {key: 1}


def test_add_points_goes_to_for_or_against_and_ignores_zero():
    stats = empty_stats()
    add_points(stats, 3, True)
    add_points(stats, 2, False)
    add_points(stats, 0, True)
    assert (stats["points_for"], stats["points_against"]) == (3, 2)
