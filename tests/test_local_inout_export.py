"""IN/OUT of every player of a competition, published for the web (#678): what ``GET /players/{collection}/inout/{player_id}`` answers, computed once at publication.

The endpoint plays every game of the competition for each player (a second for each one: minutes for the 240 players of a competition); there is nothing to merge on the device
(it takes no filter), so the published analysis is the answer itself, with the endpoint's own normalisation and advanced figures. Built over the real sample games of both leagues.
"""
import json
import sys
from pathlib import Path

import mongomock
import pymongo
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

from lineup_games import FBCYL, FEB, sample_games  # noqa: E402
from src.api.routers.players import get_inout_analysis  # noqa: E402
from src.local_data.export import FORMAT  # noqa: E402
from src.local_data.inout_export import export_inout  # noqa: E402


@pytest.fixture()
def handler(monkeypatch):
    from src.api import deps

    monkeypatch.setattr(pymongo, "MongoClient", mongomock.MongoClient)
    deps._create_handler.cache_clear()
    handler = deps._create_handler()
    db = handler.connection.client["BASKETBALL"]
    plan = [{"day": "2025-10-05"}, {"day": "2025-10-12", "periods": 3}]
    db[FEB].insert_many(sample_games("feb", plan))
    db[FBCYL].insert_many(sample_games("fbcyl", plan))
    yield handler
    deps._create_handler.cache_clear()


def test_each_player_has_what_the_endpoint_answers_for_them(handler):
    payload = export_inout(handler, FEB)
    assert (payload["format"], payload["league"], payload["collection"]) == (FORMAT, "feb", FEB)
    assert payload["players"], "the players of the competition are published"
    ids = [p["player_id"] for p in payload["players"]]
    assert len(ids) == len(set(ids))
    answered = 0
    for entry in payload["players"][:6]:
        expected = json.loads(json.dumps(get_inout_analysis(FEB, entry["player_id"], handler), default=str))
        assert entry["analysis"] == expected
        answered += bool(expected)
    assert answered > 0 and any("on" in p["analysis"] and "off" in p["analysis"] for p in payload["players"])
    json.dumps(payload)


def test_fbcyl_publishes_each_player_by_his_uuid_regression(handler):
    """#711. Bug it prevents: the page asked FBCYL's IN/OUT with the ``player_id`` of the table (the actorId of ONE game, which changes from game to game), and the analysis looks for the
    uuid, so every FBCYL player came out with no game analysed. A player is known by his uuid (``player_uuid`` of the rows, completed over the season), and that is what is published."""
    payload = export_inout(handler, FBCYL)
    assert payload["league"] == "fbcyl" and payload["players"], "the players of an FBCYL competition are published"
    ids = [p["player_id"] for p in payload["players"]]
    assert len(ids) == len(set(ids)) and all("-" in i for i in ids)                          # uuids, not the numeric actorIds of the table
    for entry in payload["players"][:6]:
        expected = json.loads(json.dumps(get_inout_analysis(FBCYL, entry["player_id"], handler), default=str))
        assert entry["analysis"] == expected
    assert any(p["analysis"].get("games_analyzed") for p in payload["players"])               # asked by uuid, the analysis finds the games
