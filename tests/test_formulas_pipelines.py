"""Every team table says what the registry says (#1153): the season pipelines of Mongo (FEB, FBCYL and the rival's table) compute each rate with the formula of ``config/formulas.json``,
whatever the way the pipeline reached the counters. The same league fixtures the local-first vectors use (stored and estimated possessions, overtime games)."""
import sys
from pathlib import Path

import pytest
from db_helpers import new_mock_db

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

from fbcyl_games import build_games as fbcyl_games  # noqa: E402
from games import build_games as feb_games  # noqa: E402
from src.database.aggregation.fbcyl_pipeline import FBCYLPipelineBuilder  # noqa: E402
from src.database.aggregation.pipeline_builder import AggregationPipelineBuilder  # noqa: E402
from src.stats.formulas import FORMULAS, evaluate  # noqa: E402

FEB_COUNTERS = {"points": "points_scored", "points_against": "points_received", "fg2m": "fg2_made", "fg2a": "fg2_attempted", "fg3m": "fg3_made", "fg3a": "fg3_attempted",
                "fta": "ft_attempted", "ast": "assists", "stl": "steals", "blk": "blocks", "tov": "turnovers", "orb": "rebounds_off", "drb": "rebounds_def",
                "opp_orb": "opponent_rebounds_off", "opp_drb": "opponent_rebounds_def", "poss": "total_possessions", "opp_poss": "opponent_possessions"}


def _check(team, counters):
    for name in FORMULAS:
        want = evaluate(name, counters)
        assert team[name] == pytest.approx(0 if want is None else want, rel=1e-9, abs=1e-9), f"{team.get('team_name')}: {name}"


def test_the_feb_season_table_says_what_the_registry_says_regression():
    col = new_mock_db("formulas_feb")["LEAGUE"]
    col.insert_many(feb_games())
    teams = list(col.aggregate(AggregationPipelineBuilder.build_team_stats_pipeline()))

    assert teams
    for team in teams:
        _check(team, {name: team[field] for name, field in FEB_COUNTERS.items()})


def test_the_fbcyl_season_table_says_what_the_registry_says_regression():
    col = new_mock_db("formulas_fbcyl")["FBCYL_LEAGUE"]
    col.insert_many(fbcyl_games())
    teams = list(col.aggregate(FBCYLPipelineBuilder.build_team_stats_pipeline()))

    assert teams
    for team in teams:
        _check(team, {name: team[field] for name, field in FEB_COUNTERS.items()})


def test_the_rival_table_says_what_the_registry_says_regression():
    """The table of what the rivals did to each team: the same formulas over the same counters, from the rival's point of view."""
    col = new_mock_db("formulas_rival")["LEAGUE"]
    col.insert_many(feb_games())
    teams = list(col.aggregate(AggregationPipelineBuilder.build_opponent_stats_pipeline()))

    assert teams
    for team in teams:
        _check(team, {name: team[field] for name, field in FEB_COUNTERS.items()})


def test_the_per_game_rates_say_what_the_registry_says_for_the_team_and_its_rival_regression():
    """The consistency (CV%) pairs the season value with the per-game ones: both come from the same formulas now (TOV% over FGA + 0.44 FTA + TOV, ROB% and TAP% over the rival's
    possessions, DER over the rival's possessions, #1153)."""
    from src.database.aggregation.pipeline_team_per_game import OWN_FIELDS, PER_GAME_FIELDS, RIVAL_FIELDS

    col = new_mock_db("formulas_per_game")["LEAGUE"]
    col.insert_many(feb_games())
    games = list(col.aggregate(AggregationPipelineBuilder.build_per_game_raw_pipeline()))

    assert games
    for game in games:
        for fields, prefix in ((OWN_FIELDS, ""), (RIVAL_FIELDS, "opp_")):
            counters = {name: game[field.lstrip("$")] for name, field in fields.items()}
            for name, field in PER_GAME_FIELDS.items():
                column = {"oreb_rate_game": "orb_rate_game", "dreb_rate_game": "drb_rate_game"}.get(field, field) if prefix else field
                assert game[prefix + column] == (pytest.approx(evaluate(name, counters), rel=1e-9) if evaluate(name, counters) is not None else None), prefix + column


def test_the_per_game_steal_and_block_rates_are_per_rival_possession_regression():
    col = new_mock_db("formulas_per_game_2")["LEAGUE"]
    col.insert_many(feb_games())
    games = list(col.aggregate(AggregationPipelineBuilder.build_per_game_raw_pipeline()))

    for game in games:
        assert game["steal_rate_game"] == pytest.approx(game["steals"] / game["opp_real_poss"] * 100)
        assert game["block_rate_game"] == pytest.approx(game["blocks"] / game["opp_real_poss"] * 100)
        assert game["der_game"] == pytest.approx(game["opponent_points"] / game["opp_real_poss"] * 100)
