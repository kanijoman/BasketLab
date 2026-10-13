"""SeasonAccumulator (issue #238): one pass over the season feeds the package of ANY pair of teams.

The rule evaluator needs the package a team would have had before each game of the competition, for both sides, so
the accumulator tracks every team. ``build_package`` stays a thin wrapper and must give byte-identical packages.
"""
import json

import pytest

from src.live_prep.package_builder import SeasonAccumulator, build_package

A, B = "982047", "981204"
C, D = "900003", "900004"
STAMP = "2026-10-08T00:00:00Z"


def remap(doc, mapping):
    text = json.dumps(doc)
    for old, new in mapping.items():
        text = text.replace(f'"{old}"', f'"{new}"')
    return json.loads(text)


@pytest.fixture()
def season(feb_game_doc):
    """Four teams over three games: A-B, A-C (B's side remapped to C) and C-D (a player of A turns up in C)."""
    return [feb_game_doc, remap(feb_game_doc, {B: C}), remap(feb_game_doc, {A: C, B: D})]


def kwargs(team, rival):
    return dict(collection="FEB_TEST", season="2025-2026", team_id=team, rival_id=rival, created_at=STAMP)


def accumulated(games, team, rival, **acc_kw):
    acc = SeasonAccumulator(**acc_kw)
    for g in games:
        acc.add_game(g)
    return acc.to_package(collection="FEB_TEST", season="2025-2026", team_id=team, rival_id=rival,
                          competition_meta=None, created_at=STAMP)


@pytest.mark.parametrize("team,rival", [(A, B), (B, A), (A, C), (C, D), (D, C), (B, D)])
def test_any_pair_gives_the_same_package_as_build_package(season, team, rival):
    expected = build_package(season, **kwargs(team, rival))
    assert accumulated(season, team, rival).dumps() == expected.dumps()


def test_the_package_is_the_one_of_the_games_added_so_far(season):
    acc = SeasonAccumulator()
    for k, game in enumerate(season, 1):
        acc.add_game(game)
        got = acc.to_package("FEB_TEST", "2025-2026", A, B, None, STAMP)
        assert got.dumps() == build_package(season[:k], **kwargs(A, B)).dumps()


def test_asking_for_a_package_does_not_change_the_accumulator(season):
    acc = SeasonAccumulator()
    for g in season[:2]:
        acc.add_game(g)
    first = acc.to_package("FEB_TEST", "2025-2026", A, C, None, STAMP).dumps()
    acc.to_package("FEB_TEST", "2025-2026", C, A, None, STAMP)
    assert acc.to_package("FEB_TEST", "2025-2026", A, C, None, STAMP).dumps() == first


def test_played_counts_the_games_of_each_team(season):
    acc = SeasonAccumulator()
    for g in season:
        acc.add_game(g)
    assert (acc.played(A), acc.played(B), acc.played(C), acc.played(D), acc.played("nobody")) == (2, 1, 2, 1, 0)


def test_tracking_only_two_teams_gives_their_package_with_less_memory(season):
    expected = build_package(season, **kwargs(A, B))
    tracked = accumulated(season, A, B, track={A, B})
    assert tracked.dumps() == expected.dumps()
    acc = SeasonAccumulator(track={A, B})
    for g in season:
        acc.add_game(g)
    with pytest.raises(ValueError):
        acc.to_package("FEB_TEST", "2025-2026", C, D, None, STAMP)


def test_a_game_that_is_not_between_two_teams_is_ignored(feb_game_doc):
    broken = json.loads(json.dumps(feb_game_doc))
    broken["HEADER"]["TEAM"] = broken["HEADER"]["TEAM"][:1]
    acc = SeasonAccumulator()
    acc.add_game(broken)
    assert acc.played(A) == 0 and acc.total_games == 0
