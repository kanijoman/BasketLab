"""FBCYL dates on a REAL MongoDB (#681): the pipelines that filter and sort by the date of a game parse what FBCYL really writes.

``stats.time`` is ``Oct 3, 2026, 6:30:00 PM`` in the current data (a comma after the year and a narrow no-break space, U+202F, before ``PM``); the older games were
``Oct 4, 2025 7:00:00 PM``. The pipelines used to split on spaces and parse ``%b %d, %Y``, which fails on ``2026,``: every date filter answered NO team (and Comparativas
by stretch, the date filters of the tables and the evolution were empty). ``mongomock`` has no ``$dateFromString``, so this test needs a real ``mongod``: it is skipped when
there is none (the CI), and runs against ``BASKETLAB_TEST_MONGODB`` or ``mongodb://localhost:27017`` in a scratch database that is dropped.
"""
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import fbcyl_games  # noqa: E402
from src.database.aggregation.fbcyl_pipeline import FBCYLPipelineBuilder  # noqa: E402
from src.database.repository import BasketballRepository  # noqa: E402
from src.services.evolution_service import EvolutionService  # noqa: E402
from src.utils.time_utils import fbcyl_game_day  # noqa: E402

pymongo = pytest.importorskip("pymongo")
URI = os.environ.get("BASKETLAB_TEST_MONGODB", "mongodb://localhost:27017")
SCRATCH = "BASKETLAB_TEST_681"


def _current(time: str) -> str:
    """The fixtures already write the date as FBCYL does today (``Oct 4, 2025, 7:00:00 PM``: a comma after the year and U+202F before the meridiem)."""
    return time


def _older(time: str) -> str:
    """``Oct 4, 2025 7:00:00 PM``: how FBCYL wrote it before."""
    return time.replace(" ", " ").replace("2025,", "2025")


@pytest.fixture(scope="module")
def client():
    mongo = pymongo.MongoClient(URI, serverSelectionTimeoutMS=500)
    try:
        mongo.admin.command("ping")
    except Exception:
        pytest.skip("no MongoDB to run the real pipelines on")
    yield mongo
    mongo.drop_database(SCRATCH)
    mongo.close()


def _collection(client, name, transform):
    col = client[SCRATCH][name]
    col.drop()
    games = fbcyl_games.build_games()
    for game in games:
        game["stats"]["time"] = transform(game["stats"]["time"])
    col.insert_many(games)
    return col, games


FORMATS = [("current", _current), ("older", _older)]
LAST_OCTOBER = datetime(2025, 11, 1)


@pytest.mark.parametrize("label, transform", FORMATS)
def test_a_date_filter_finds_the_games_of_the_range_in_both_formats(client, label, transform):
    col, games = _collection(client, f"G_{label}", transform)
    after = [g for g in games if datetime.strptime(fbcyl_game_day(g["stats"]["time"]), "%Y-%m-%d") >= LAST_OCTOBER]
    assert 0 < len(after) < len(games)
    for build in (FBCYLPipelineBuilder.build_team_stats_pipeline, FBCYLPipelineBuilder.build_opponent_stats_pipeline):
        rows = list(col.aggregate(build({"$gte": LAST_OCTOBER}, None, None)))
        assert sum(r["games_played"] for r in rows) == 2 * len(after), (label, build.__name__)      # two teams per game


@pytest.mark.parametrize("label, transform", FORMATS)
def test_the_rest_of_the_season_is_the_complement_of_the_stretch(client, label, transform):
    col, games = _collection(client, f"R_{label}", transform)
    stretch = {"$gte": LAST_OCTOBER}
    inside = sum(r["games_played"] for r in col.aggregate(FBCYLPipelineBuilder.build_team_stats_pipeline(stretch, None, None)))
    outside = sum(r["games_played"] for r in col.aggregate(FBCYLPipelineBuilder.build_team_stats_pipeline({"$not": stretch}, None, None)))
    assert inside + outside == 2 * len(games) and inside > 0 and outside > 0


@pytest.mark.parametrize("label, transform", FORMATS)
def test_the_games_are_sorted_by_their_date_for_the_evolution(client, label, transform):
    col, games = _collection(client, f"E_{label}", transform)

    class _Collection:
        def aggregate(self, pipeline, **kwargs):
            return col.aggregate(pipeline, **kwargs)

    team = games[0]["stats"]["teams"][0]["teamIdExtern"]
    rows = EvolutionService(None)._evolution_fbcyl(_Collection(), str(team))
    assert len(rows) > 2 and "unknown" not in {r["game_date"] for r in rows}
    assert [r["game_date"] for r in rows] == sorted(r["game_date"] for r in rows)


@pytest.mark.parametrize("label, transform", FORMATS)
def test_the_parsed_date_of_a_game_is_there_for_the_other_pipelines_too(client, label, transform):
    col, games = _collection(client, f"P_{label}", transform)
    stages = BasketballRepository._parsed_date_pipeline({}, True)
    parsed = list(col.aggregate(stages))
    assert len(parsed) == len(games) and all(doc["_parsedDate"] is not None for doc in parsed)
