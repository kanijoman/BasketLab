"""Package builder: season baselines computed with the SAME engine used live, from stored
games (pure function over documents; a thin adapter reads them from MongoDB)."""

import copy

import pytest

from src.live_core.advice import AdviceEngine
from src.live_core.engine import LiveEngine
from src.live_core.package import PreparationPackage
from src.live_prep.package_builder import (
    FEATURE_MIN_GAMES_FOR_SPREAD,
    build_package,
    league_spread,
    matchup_prior,
)

OWN, RIVAL = "982047", "981204"


def _build(games, **kw):
    return build_package(games, collection="FEB_TEST", season="2025-2026",
                         team_id=OWN, rival_id=RIVAL, created_at="2026-10-08T00:00:00Z", **kw)


def test_builds_a_valid_serialisable_package(feb_game_doc):
    pkg = _build([feb_game_doc])
    assert isinstance(pkg, PreparationPackage)
    assert PreparationPackage.loads(pkg.dumps()) == pkg
    assert pkg.team == {"id": OWN, "name": "ACEITES ABRIL ADBA SANFER"}
    assert pkg.rival["id"] == RIVAL


def test_player_baselines_match_the_engine_on_a_one_game_season(feb_game_doc):
    pkg = _build([feb_game_doc])
    snap = LiveEngine().update(feb_game_doc)
    players = pkg.tables["players"]
    assert players and all(p["team_id"] == OWN for p in players.values())
    for pid, base in players.items():
        assert base["games"] == 1
        assert base["avg_min"] == snap["players"][pid]["minutes"]
        assert base["name"]
    long_stint = max(players.values(), key=lambda b: b["avg_stint"])
    assert long_stint["avg_stint"] > 300


def test_rival_players_are_kept_separately(feb_game_doc):
    pkg = _build([feb_game_doc])
    assert pkg.tables["rival_players"] and all(p["team_id"] == RIVAL for p in pkg.tables["rival_players"].values())
    assert not set(pkg.tables["players"]) & set(pkg.tables["rival_players"])


def test_averages_over_several_games(feb_game_doc):
    other = copy.deepcopy(feb_game_doc)
    for line in other["PLAYBYPLAY"]["LINES"]:  # same players, a game where they never play
        if line["idTeam"] == OWN:
            line["action"] = "timeout"
    pkg = _build([feb_game_doc, other])
    some = next(iter(pkg.tables["players"].values()))
    assert some["games"] == 1  # players with no minutes in the second game do not count as having played it


def test_games_without_the_team_do_not_contribute(feb_game_doc):
    stranger = copy.deepcopy(feb_game_doc)
    stranger["HEADER"]["TEAM"] = [{"id": "1", "name": "X", "pts": "0"}, {"id": "2", "name": "Y", "pts": "0"}]
    assert _build([feb_game_doc, stranger]).baselines["sample_games"]["own"] == 1


def test_pace_and_sample_sizes_are_reported(feb_game_doc):
    pkg = _build([feb_game_doc])
    assert 40 < pkg.baselines["pace_per_40"] < 110
    assert pkg.baselines["sample_games"] == {"own": 1, "rival": 1, "league": 1}


def test_league_spread_needs_enough_games_and_has_a_floor():
    few = [{"efg": 0.05, "tov": 0.01, "orb": 0.02, "ftr": 0.03}] * (FEATURE_MIN_GAMES_FOR_SPREAD - 1)
    assert league_spread(few) == {}
    flat = [{"efg": 0.0, "tov": 0.0, "orb": 0.0, "ftr": 0.0}] * FEATURE_MIN_GAMES_FOR_SPREAD
    sd = league_spread(flat)
    assert set(sd) == {"efg", "tov", "orb", "ftr"} and all(v > 0 for v in sd.values())
    varied = [{"efg": x, "tov": x, "orb": x, "ftr": x} for x in (-0.2, 0.2) * FEATURE_MIN_GAMES_FOR_SPREAD]
    assert league_spread(varied)["efg"] == pytest.approx(0.2, rel=0.2)


def test_matchup_prior_is_the_strength_gap_shrunk_by_the_sample():
    own_diffs = [{"efg": 0.06, "tov": 0.0, "orb": 0.0, "ftr": 0.0}] * 12
    rival_diffs = [{"efg": -0.02, "tov": 0.0, "orb": 0.0, "ftr": 0.0}] * 12
    full = matchup_prior(own_diffs, rival_diffs)
    assert 0 < full["efg"] < 0.08
    few = matchup_prior(own_diffs[:1], rival_diffs[:1])
    assert 0 < few["efg"] < full["efg"], "less data -> closer to zero"
    assert matchup_prior([], [])["efg"] == 0.0


def test_package_drives_the_advice_engine_end_to_end(feb_game_doc):
    """The builder's output is exactly what AdviceEngine.from_package expects."""
    pkg = _build([feb_game_doc])
    engine = AdviceEngine.from_package(pkg)
    snap = LiveEngine().update(feb_game_doc)
    assert engine.analyze(snap)["four_factors"]["reliable"] is True
    long_stint_player = max(pkg.tables["players"], key=lambda p: pkg.tables["players"][p]["avg_stint"])
    assert long_stint_player in pkg.tables["players"]
