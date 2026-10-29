"""The contract rows of the local player tables (#327): one row per player and game played, the exact input of the season aggregation.

Rankings and the player table will be computed on the device from these rows; they carry what the Mongo ``$group`` reads plus the venue, the
result, the date and the match, so that the same filters (venue, result, dates, team) can be applied without the server.
"""
import sys
from pathlib import Path

import pytest
from db_helpers import new_mock_db

sys.path.insert(0, str(Path(__file__).resolve().parent))

from local_vectors.games import build_games, for_mongomock  # noqa: E402
from src.database.aggregation import AggregationPipelineBuilder  # noqa: E402


@pytest.fixture()
def collection():
    col = new_mock_db("player_rows")["LEAGUE"]
    col.insert_many(build_games())
    return col


def _rows(collection):
    return list(collection.aggregate(AggregationPipelineBuilder.build_season_player_rows_pipeline()))


def test_a_player_who_did_not_play_has_no_row(collection):
    rows = _rows(collection)
    assert rows and all(r["minutes"] > 0 for r in rows)
    played = sum(1 for g in build_games() for t in g["BOXSCORE"]["TEAM"] for p in t["PLAYER"] if int(p["min"]) > 0)
    assert len(rows) == played


def test_each_row_carries_who_where_when_and_with_what_result(collection):
    row = next(r for r in _rows(collection) if r["match_id"] == 9001 and r["is_local"])
    game = build_games()[0]
    assert row["starttime"] == game["HEADER"]["starttime"]
    assert row["team_id"] == game["BOXSCORE"]["TEAM"][0]["id"] and row["team_name"] == game["BOXSCORE"]["TEAM"][0]["name"]
    assert row["won"] is (int(game["BOXSCORE"]["TEAM"][0]["TOTAL"]["pts"]) > int(game["BOXSCORE"]["TEAM"][1]["TOTAL"]["pts"]))
    assert {"player_id", "player_name", "minutes", "pts", "p2m", "p3a", "p1a", "to", "pllss", "val"} <= set(row)


def test_summing_the_rows_gives_the_season_pipeline_totals(collection):
    """Nothing is lost between the rows and the ``$group`` of the season."""
    rows = _rows(collection)
    for player in collection.aggregate(for_mongomock(AggregationPipelineBuilder.build_player_stats_pipeline())):
        mine = [r for r in rows if (r["player_id"], r["team_id"]) == (player["player_id"], player["team_id"])]      # the identity: the player within his team (#652)
        assert player["games_played"] == len(mine)
        assert player["total_pts"] == sum(r["pts"] for r in mine)
        assert player["total_minutes"] == pytest.approx(sum(r["minutes"] for r in mine) / 60)
