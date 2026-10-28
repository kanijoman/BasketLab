"""The contract rows of the FBCYL local team tables (#327): the same row as FEB's (one per team and game), built from FBCYL's box.

FBCYL differs from FEB in where everything is (``stats.teams[].data``), how the date is written and that a game can end tied, but the web must
sum ONE kind of row. Possessions are the stored count of ``DERIVED`` or the box estimate, exactly as the season pipeline takes them.
"""
import sys
from pathlib import Path

import pytest
from db_helpers import new_mock_db

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

from fbcyl_games import TEAMS, build_games  # noqa: E402
from src.database.aggregation.fbcyl_per_game_pipeline import build_fbcyl_season_rows_pipeline  # noqa: E402
from src.database.aggregation.fbcyl_pipeline import FBCYLPipelineBuilder  # noqa: E402


@pytest.fixture()
def collection():
    col = new_mock_db("fbcyl_rows")["FBCYL_LEAGUE"]
    col.insert_many(build_games())
    return col


def _rows(collection):
    return list(collection.aggregate(build_fbcyl_season_rows_pipeline()))


def test_there_is_one_row_per_team_and_game_with_the_stable_team_id(collection):
    rows = _rows(collection)
    assert len(rows) == 24 and {r["team_id"] for r in rows} == {t[0] for t in TEAMS}
    assert len({(r["match_id"], r["team_id"]) for r in rows}) == 24


def test_each_row_carries_venue_result_date_and_the_rival_figures(collection):
    rows = _rows(collection)
    game = build_games()[0]
    home = next(r for r in rows if r["match_id"] == game["_id"] and r["is_local"])
    away = next(r for r in rows if r["match_id"] == game["_id"] and not r["is_local"])
    assert home["starttime"] == game["stats"]["time"]
    assert home["opponent_points"] == away["points"] and home["opponent_fg3_made"] == away["fg3_made"] and home["opponent_turnovers"] == away["turnovers"]
    assert home["opponent_def_rebounds"] == away["def_rebounds"] and home["opponent_possessions"] == away["possessions"]
    assert home["won"] is (home["points"] > away["points"])


def test_a_tied_game_is_neither_won_nor_lost_regression(collection):
    """FBCYL's pipeline has a third result, ``tied``: filtering by 'lost' must not return a team that did not lose."""
    tied = [r for r in _rows(collection) if r["match_id"] == build_games()[5]["_id"]]
    assert len(tied) == 2 and all(r["tied"] is True and r["won"] is False for r in tied)
    assert not any(r["tied"] for r in _rows(collection) if r["match_id"] != build_games()[5]["_id"])


def test_summing_the_rows_gives_the_season_pipeline_totals(collection):
    rows = _rows(collection)
    for team in collection.aggregate(FBCYLPipelineBuilder.build_team_stats_pipeline()):
        mine = [r for r in rows if r["team_id"] == team["team_id"]]
        assert team["total_games"] == len(mine)
        assert team["points_scored"] == sum(r["points"] for r in mine)
        assert team["total_rebounds"] == sum(r["total_rebounds"] for r in mine)
        assert team["fouls"] == sum(r["fouls"] for r in mine)
        assert team["total_possessions"] == pytest.approx(sum(r["possessions"] for r in mine))
        assert team["opponent_possessions"] == pytest.approx(sum(r["opponent_possessions"] for r in mine))
        assert team["games_won"] == sum(1 for r in mine if r["won"])
