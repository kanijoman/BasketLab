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


def test_the_package_carries_the_free_throw_percentage_shrunk_to_the_league_mean(feb_game_doc):
    """Issue #246 (C1): who to give the ball to and who to foul in a close finish needs the free-throw percentage of each
    player. With few attempts it must stay close to the league mean (a 1/1 night is not a 100 % shooter)."""
    from src.live_core.engine import LiveEngine
    from src.live_prep.package_builder import MIN_LEAGUE_SECONDS

    package = accumulated([feb_game_doc], A, B)
    played = LiveEngine().update(feb_game_doc)["players"]
    players = {**package.tables["players"], **package.tables["rival_players"]}
    league = [pid for pid, p in players.items() if p["seconds"] >= MIN_LEAGUE_SECONDS]    # the league population, as for the rates
    made = sum(played[pid]["stats"]["ftm"] for pid in league)
    attempts = sum(played[pid]["stats"]["fta"] for pid in league)
    mean = package.baselines["ft_league_pct"]
    assert mean == pytest.approx(made / attempts, abs=1e-3) and 0.4 < mean < 1.0
    for pid, p in players.items():
        ftm, fta = played[pid]["stats"]["ftm"], played[pid]["stats"]["fta"]
        assert p["fta"] == fta
        assert p["ft_pct"] == pytest.approx((ftm + 10 * mean) / (fta + 10), abs=1e-3)
    no_attempts = [p for p in players.values() if p["fta"] == 0]
    assert no_attempts and all(p["ft_pct"] == pytest.approx(mean, abs=1e-3) for p in no_attempts)


def test_the_free_throw_data_is_the_same_for_build_package(feb_game_doc):
    a = accumulated([feb_game_doc], A, B)
    b = build_package([feb_game_doc], "FEB_TEST", "2025-2026", A, B, created_at=STAMP)
    assert a.tables["players"] == b.tables["players"] and a.baselines["ft_league_pct"] == b.baselines["ft_league_pct"]


def test_the_package_carries_the_habitual_three_point_rate_of_both_teams(feb_game_doc):
    """Issue #291 (T2): the share of three-point attempts in all field-goal attempts, over the season, of our team and the rival's."""
    from src.live_core.engine import LiveEngine

    package = accumulated([feb_game_doc], A, B)
    stats = {tid: LiveEngine().update(feb_game_doc)["teams"][tid]["stats"] for tid in (A, B)}
    for key, tid in (("fg3_rate_own", A), ("fg3_rate_rival", B)):
        s = stats[tid]
        assert package.baselines[key] == pytest.approx(s["fg3a"] / (s["fg2a"] + s["fg3a"]), abs=1e-3)
    assert 0.1 < package.baselines["fg3_rate_own"] < 0.6


def test_a_team_without_games_has_no_three_point_rate(feb_game_doc):
    acc = SeasonAccumulator(track=(A, "999999"))
    acc.add_game(feb_game_doc)
    package = acc.to_package("FEB_TEST", "2025-2026", A, "999999", None, STAMP)
    assert "fg3_rate_own" in package.baselines and "fg3_rate_rival" not in package.baselines


def test_package_carries_the_net_rating_prior_for_the_win_probability(feb_game_doc):
    """#254, #567: expected margin per 100 possessions of team vs rival = the gap of their Bayesian (Kalman) ratings, at the pace of the matchup."""
    from src.live_prep.team_rating import TeamRatings

    from src.live_core.engine import LiveEngine

    snap = LiveEngine().update(feb_game_doc)
    home, away = [str(t["id"]) for t in feb_game_doc["HEADER"]["TEAM"]]
    ratings = TeamRatings()
    ratings.update(home, away, snap["score"][home] - snap["score"][away])
    package = accumulated([feb_game_doc], A, B)
    ab, ba = package.baselines["net_rtg_prior"], accumulated([feb_game_doc], B, A).baselines["net_rtg_prior"]
    assert ab == pytest.approx(ratings.gap_per_100(A, B, package.baselines["pace_per_40"]), abs=1e-3)
    assert ab == pytest.approx(-ba, abs=1e-3) and ab != 0


def test_the_rating_of_a_team_counts_the_games_of_teams_the_package_does_not_track(season):
    """The publisher tracks only the teams of the round; their rating still depends on who their opponents beat (C - D is not of a tracked team)."""
    everyone = accumulated(season, A, C).baselines["net_rtg_prior"]
    some = accumulated(season, A, C, track=(A, C)).baselines["net_rtg_prior"]
    assert some == pytest.approx(everyone)


def test_a_game_of_another_competition_does_not_move_the_ratings(feb_game_doc):
    """#456: the games of the teams in other competitions feed their tables, not the league; a cup game against a weaker division must not inflate a rating."""
    from src.live_prep.game_sources import LEAGUE_KEY

    other = {**feb_game_doc, LEAGUE_KEY: False}
    assert accumulated([other], A, B).baselines["net_rtg_prior"] == 0.0


def test_net_rating_prior_is_zero_without_games():
    acc = SeasonAccumulator()
    assert acc.to_package("FEB_TEST", "2025-2026", A, B, None, STAMP).baselines["net_rtg_prior"] == 0.0
