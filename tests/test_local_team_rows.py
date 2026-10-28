"""The contract rows of the local-first data (#327): one row per team and game, the exact input of the season aggregation.

The web will compute the team tables from these rows on the device instead of asking the API, so the rows must carry everything the Mongo
``$group`` stage reads (own and rival figures, venue, result, date, the stored or estimated possessions) and nothing may be lost in between.
"""
import sys
from pathlib import Path

import pytest
from db_helpers import new_mock_db

sys.path.insert(0, str(Path(__file__).resolve().parent))

from local_vectors.games import TEAMS, build_games  # noqa: E402
from src.database.aggregation import AggregationPipelineBuilder  # noqa: E402


@pytest.fixture()
def collection():
    col = new_mock_db("rows")["LEAGUE"]
    col.insert_many(build_games())
    return col


def test_there_is_one_row_per_team_and_game(collection):
    rows = list(collection.aggregate(AggregationPipelineBuilder.build_season_rows_pipeline()))
    assert len(rows) == 24
    assert {r["team_id"] for r in rows} == {t[0] for t in TEAMS}
    assert len({(r["match_id"], r["team_id"]) for r in rows}) == 24


def test_each_row_carries_venue_result_date_and_the_rival_figures(collection):
    rows = list(collection.aggregate(AggregationPipelineBuilder.build_season_rows_pipeline()))
    first = next(r for r in rows if r["match_id"] == 9001 and r["is_local"])
    rival = next(r for r in rows if r["match_id"] == 9001 and not r["is_local"])
    assert first["starttime"] == build_games()[0]["HEADER"]["starttime"]
    assert first["won"] is (first["points"] > first["opponent_points"]) and rival["won"] is not first["won"]
    assert first["opponent_points"] == rival["points"] and first["opponent_fg3_made"] == rival["fg3_made"]
    assert first["opponent_def_rebounds"] == rival["def_rebounds"] and first["opponent_possessions"] == rival["possessions"]


def test_a_game_with_derived_uses_its_stored_possessions_regression(collection):
    """The rows are built by the same expressions as the season pipeline: the exact count of ``DERIVED`` (scaled to 40 minutes) wins over the estimate."""
    rows = {(r["match_id"], r["team_id"]): r for r in collection.aggregate(AggregationPipelineBuilder.build_season_rows_pipeline())}
    stored = build_games()[1]["DERIVED"]["TEAM"][0]
    assert rows[(9002, stored["id"])]["possessions"] == pytest.approx(stored["possessions"])


def test_summing_the_rows_gives_the_season_pipeline_totals(collection):
    """Nothing is lost between the rows and the ``$group`` of the season: the totals are the same."""
    rows = list(collection.aggregate(AggregationPipelineBuilder.build_season_rows_pipeline()))
    for team in collection.aggregate(AggregationPipelineBuilder.build_team_stats_pipeline()):
        mine = [r for r in rows if r["team_id"] == team["_id"]]
        assert team["total_games"] == len(mine)
        assert team["points_scored"] == sum(r["points"] for r in mine)
        assert team["fg3_attempted"] == sum(r["fg3_attempts"] for r in mine)
        assert team["total_possessions"] == pytest.approx(sum(r["possessions"] for r in mine))
        assert team["opponent_possessions"] == pytest.approx(sum(r["opponent_possessions"] for r in mine))
