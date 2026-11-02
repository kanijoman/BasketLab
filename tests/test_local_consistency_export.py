"""The consistency of every player of a competition, published for the web (#709): what ``GET /players/{collection}/consistency`` answers, computed once at publication.

The endpoint takes no filter, so the answer is the published payload: the browser reads it as it is. Its per-game figures (the 26 FEB stats and 18 FBCYL ones, the six shares of the team
among them) come out of the real per-game pipelines of each league, not of anything the rows of the contract hold, which is why it is precomputed with the endpoint's own function.
Built over the real sample games of FBCYL (the FEB pipeline needs operators mongomock does not have: FEB is checked against a given answer).
"""
import json
import sys
from pathlib import Path

import mongomock
import pymongo
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

from lineup_games import FBCYL, FEB, sample_games  # noqa: E402
from src.local_data.consistency_export import export_consistency  # noqa: E402
from src.local_data.export import FORMAT  # noqa: E402
from src.services.player_stats_service import PlayerStatsService  # noqa: E402


@pytest.fixture()
def handler(monkeypatch):
    from src.api import deps

    monkeypatch.setattr(pymongo, "MongoClient", mongomock.MongoClient)
    deps._create_handler.cache_clear()
    handler = deps._create_handler()
    db = handler.connection.client["BASKETBALL"]
    plan = [{"day": "2025-10-05"}, {"day": "2025-10-12", "periods": 3}, {"day": "2025-10-19"}]
    db[FEB].insert_many(sample_games("feb", plan))
    db[FBCYL].insert_many(sample_games("fbcyl", plan))
    yield handler
    deps._create_handler.cache_clear()


def test_each_player_has_what_the_endpoint_answers_for_them_in_fbcyl(handler):
    payload = export_consistency(handler, FBCYL)
    assert (payload["format"], payload["league"], payload["collection"]) == (FORMAT, "fbcyl", FBCYL)
    expected = json.loads(json.dumps(PlayerStatsService(handler).get_consistency(FBCYL), default=str))
    assert payload["players"] == expected and payload["players"]
    sample = next(iter(payload["players"].values()))
    assert all(set(v) == {"mean", "std", "cv", "n"} for v in sample.values())
    json.dumps(payload)


def test_a_feb_competition_publishes_the_answer_of_the_endpoint(handler, monkeypatch):
    answer = {"9": {"points_per_game": {"mean": 10.5, "std": 2.0, "cv": 19.0, "n": 5}}}
    monkeypatch.setattr(PlayerStatsService, "get_consistency", lambda self, name: answer)
    payload = export_consistency(handler, FEB)
    assert payload["league"] == "feb" and payload["players"] == answer


def test_a_competition_the_endpoint_cannot_answer_publishes_no_players(handler):
    """The FEB pipeline needs what mongomock lacks and answers ``{}``: the same as an unreachable database (nothing to publish)."""
    assert export_consistency(handler, FEB)["players"] == {}
