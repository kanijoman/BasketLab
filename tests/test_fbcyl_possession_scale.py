"""FBCYL scales its pace to 40 minutes like FEB (#1155): a minibasket game of four quarters of 8 minutes had its possessions per game compared as if it lasted 40.
The rating still divides by the real count; only the pace (``pace_possessions``, ``possessions_per_game``) is per 40 minutes (#1154)."""
import copy
import sys
from pathlib import Path

import pytest
from db_helpers import new_mock_db

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

from fbcyl_games import build_games  # noqa: E402
from src.database.aggregation.fbcyl_per_game_pipeline import build_fbcyl_season_rows_pipeline  # noqa: E402
from src.database.aggregation.fbcyl_pipeline import FBCYLPipelineBuilder  # noqa: E402


def _games(durations):
    games = copy.deepcopy(build_games())
    for game in games:
        if durations is None:
            game["stats"].pop("periodDurationList", None)
        else:
            game["stats"]["periodDurationList"] = durations
    return games


def _run(durations):
    col = new_mock_db("fbcyl_scale")["FBCYL_LEAGUE"]
    col.insert_many(_games(durations))
    rows = list(col.aggregate(build_fbcyl_season_rows_pipeline()))
    teams = list(col.aggregate(FBCYLPipelineBuilder.build_team_stats_pipeline()))
    return rows, teams


@pytest.mark.parametrize("durations, minutes", [([10, 10, 10, 10], 40), ([8, 8, 8, 8], 32), (None, 40), ([10, 10], 40), ([10, 10, 0, 10], 40)])
def test_each_row_carries_the_minutes_of_its_regulation(durations, minutes):
    """A list that does not give four real quarters says nothing: 40, as ``pbp.game_possessions.game_minutes``."""
    rows, _ = _run(durations)

    assert {r["game_minutes"] for r in rows} == {minutes}


def test_a_minibasket_pace_is_scaled_to_40_minutes_and_its_ratings_are_not_regression():
    rows, teams = _run([8, 8, 8, 8])
    for team in teams:
        mine = [r for r in rows if r["team_id"] == team["team_id"]]
        real = sum(r["possessions"] for r in mine)
        assert team["total_possessions"] == pytest.approx(real)
        assert team["pace_possessions"] == pytest.approx(real * 40 / 32)
        assert team["possessions_per_game"] == pytest.approx(real * 40 / 32 / len(mine))
        assert team["pace"] == pytest.approx(team["possessions_per_game"])
        assert team["offensive_rating"] == pytest.approx(team["points_scored"] / real * 100)
