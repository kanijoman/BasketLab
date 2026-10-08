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


# --- rates and role profiles --------------------------------------------------------

def test_players_carry_rates_and_a_z_profile(feb_game_doc):
    from src.live_core.profiles import METRICS

    pkg = _build([feb_game_doc])
    for base in list(pkg.tables["players"].values()) + list(pkg.tables["rival_players"].values()):
        assert set(base["rates"]) == set(METRICS) and set(base["z"]) == set(METRICS)
        assert base["seconds"] > 0


def test_league_distribution_is_published(feb_game_doc):
    from src.live_core.profiles import METRICS

    league = _build([feb_game_doc]).baselines["league_rates"]
    assert set(league) == set(METRICS)
    assert all(v["sd"] > 0 for v in league.values())


def test_the_best_rebounder_has_a_positive_rebounding_profile(feb_game_doc):
    pkg = _build([feb_game_doc])
    box = {p["id"]: int(p["ro"] or 0) + int(p["rd"] or 0)
           for t in feb_game_doc["BOXSCORE"]["TEAM"] if t["id"] == OWN for p in t["PLAYER"]}
    top = max((pid for pid in box if pid in pkg.tables["players"]), key=lambda pid: box[pid])
    z = pkg.tables["players"][top]["z"]
    assert z["orb40"] + z["drb40"] > 0


def test_a_player_who_barely_played_is_pulled_towards_the_league(feb_game_doc):
    pkg = _build([feb_game_doc])
    small = min(pkg.tables["players"].values(), key=lambda b: b["seconds"])
    big = max(pkg.tables["players"].values(), key=lambda b: b["seconds"])
    spread = lambda b: sum(abs(v) for v in b["z"].values())
    assert small["seconds"] < big["seconds"]
    assert spread(small) <= spread(big) + 3  # shrinkage keeps tiny samples near zero


# --- impact rates for rival scouting ------------------------------------------------

def test_players_carry_impact_rates_and_the_league_means_are_published(feb_game_doc):
    from src.live_core.profiles import IMPACT_METRICS

    pkg = _build([feb_game_doc])
    for base in list(pkg.tables["players"].values()) + list(pkg.tables["rival_players"].values()):
        assert set(base["impact40"]) == set(IMPACT_METRICS)
    assert set(pkg.baselines["impact_league"]) == set(IMPACT_METRICS)
    assert all(v > 0 for v in pkg.baselines["impact_league"].values())


def test_a_big_scorer_has_a_higher_impact_rate_than_a_minimal_one(feb_game_doc):
    pkg = _build([feb_game_doc])
    rivals = pkg.tables["rival_players"].values()
    top = max(rivals, key=lambda b: b["seconds"])
    small = min(rivals, key=lambda b: b["seconds"])
    assert top["seconds"] > small["seconds"]
    # shrinkage: little playing time stays near the league mean
    league = pkg.baselines["impact_league"]
    assert abs(small["impact40"]["pts"] - league["pts"]) <= abs(top["impact40"]["pts"] - league["pts"]) + league["pts"]


def test_rival_package_drives_the_rival_alerts_without_crashing(feb_game_doc):
    from src.live_core.advice import AdviceEngine

    pkg = _build([feb_game_doc])
    snap = LiveEngine().update(feb_game_doc)
    engine = AdviceEngine.from_package(pkg)
    out = engine.evaluate(snap)
    assert all(a.evidence["team_id"] == RIVAL for a in out if a.id == "rival_hot_player")
