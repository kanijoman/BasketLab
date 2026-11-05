"""The evolution vectors are built from per-game pipelines on mongomock (about 1.4 s each on the CI runner), so the cache of the generator has to work (issue #741).

Bug it prevents: the cache read ``self._rows.setdefault(key, super()._evolution_fbcyl(...))``; ``setdefault`` evaluates its argument first, so the pipeline ran again for EVERY stat and window
(264 times instead of once per team) and four tests of the suite took 80-180 seconds each, the longest of the whole backend.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import generate  # noqa: E402
from src.services.evolution_service import EvolutionService  # noqa: E402

STATS = ("points", "assists", "offensive_rating")                 # three stats: a cache that does not work runs the pipeline three times per team


def _fbcyl():
    games = generate.build_fbcyl_games()
    for game in games:
        game["parsedDate"] = generate._fbcyl_day(game)
    return games, "FBCYL_LEAGUE", lambda docs: sorted({t["teamIdExtern"] for g in docs for t in g["stats"]["teams"]}), "_evolution_fbcyl"


def _feb():
    games = generate.build_games()
    for game in games:
        game["parsedDate"] = generate._played(game)
    return games, "LEAGUE", lambda docs: sorted({t["id"] for g in docs for t in g["HEADER"]["TEAM"]}), "_evolution_feb"


@pytest.mark.parametrize("fixture", [_fbcyl, _feb], ids=["fbcyl", "feb"])
def test_the_pipeline_of_a_team_runs_once_however_many_stats_and_windows_are_asked_regression(fixture):
    games, collection, team_ids, method = fixture()
    service = generate._evolution_service(games, collection, team_ids)
    teams = len(team_ids(games))
    with patch.object(EvolutionService, method, autospec=True, side_effect=getattr(EvolutionService, method)) as pipeline:
        for stat in STATS:
            for window in generate.EVOLUTION_WINDOWS:
                service.get_competition_evolution(collection, stat=stat, rolling_window=window)
    assert pipeline.call_count == teams                     # the vectors themselves are guarded by the tests that compare them with the stored ones
