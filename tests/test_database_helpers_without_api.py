"""What only the tests of the API covered of the code that stays (epic #1199, audit of 27/11/2026): measured on the whole suite, the 36 test files that used the API added 60 lines of unique
coverage in 14 files of the surviving code. The ones that matter are tested here directly: the classification of a database failure (what ``/health/db`` said and the connection still stores), the
failed connection, the teams of a collection and the last game of a team. Real FEB and FBCYL games (the committed samples) over mongomock."""
import copy
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pymongo
import pymongo.errors as pme
import pytest
from db_helpers import new_mock_db

from src.database.connection import MongoDBConnection
from src.database.db_health import HINTS, classify_db_error, hint_for
from src.database.repository import BasketballRepository
from src.utils.team_utils import get_available_teams_from_collection, resolve_team_by_id

SAMPLES = Path(__file__).resolve().parents[1] / "src" / "JSON_samples"
FEB = "L_F_-2_2025_2026_Liga_Regular_B"
FBCYL = "FBCYL_1ª_2026_FASE-GRUPO_A-1"


def _unwrap(node):
    if isinstance(node, dict):
        if len(node) == 1:
            key, value = next(iter(node.items()))
            if key == "$numberInt":
                return int(value)
            if key in ("$numberDouble", "$numberLong"):
                return float(value) if key == "$numberDouble" else int(value)
        return {k: _unwrap(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_unwrap(v) for v in node]
    return node


def _sample(name):
    return _unwrap(json.loads((SAMPLES / name).read_text(encoding="utf-8")))


# ---------------------------------------------------------------- the classification of a failure

class _Failure(pme.OperationFailure):
    def __init__(self, message, code):
        super().__init__(message, code=code)


@pytest.mark.parametrize("failure, kind", [
    (RuntimeError("MONGODB_CONNECTION_STRING is not set"), "missing_config"),
    (_Failure("command find requires authentication", 13), "not_authorized"),
    (_Failure("user is not authorized on db", 8000), "not_authorized"),
    (_Failure("bad auth: Authentication failed", 18), "auth_failed"),
    (_Failure("auth error", 1), "auth_failed"),
    (_Failure("something else", 1), "error"),
    (pme.ServerSelectionTimeoutError("no servers"), "unreachable"),
    (pme.ConnectionFailure("reset"), "unreachable"),
    (pme.ConfigurationError("bad option"), "invalid_config"),
    (pme.InvalidURI("bad uri"), "invalid_config"),
    (ValueError("whatever"), "error"),
])
def test_a_database_failure_is_classified_by_what_the_operator_can_do(failure, kind):
    assert classify_db_error(failure) == kind


def test_every_kind_has_a_hint_and_an_unknown_one_has_the_generic_hint():
    for kind in ("missing_config", "auth_failed", "not_authorized", "unreachable", "invalid_config", "error"):
        assert hint_for(kind) and hint_for(kind) == HINTS[kind]
    assert hint_for(None) == hint_for("nonsense") == HINTS["error"]


def test_a_failed_connection_says_why_and_is_not_connected_regression():
    with patch.object(pymongo, "MongoClient", side_effect=pme.ServerSelectionTimeoutError("no servers")):
        connection = MongoDBConnection("mongodb://nowhere.invalid")

    assert connection.last_error_kind == "unreachable"
    assert connection.client is None and connection.db is None and not connection.is_connected()


# ---------------------------------------------------------------- the teams of a collection

def _collection_handler(database, name):
    handler = MagicMock()
    handler.connection.get_collection.side_effect = lambda n: database[n]
    return handler


def test_the_teams_of_a_feb_collection_come_from_its_real_games_and_resolve_by_id():
    database = new_mock_db("teams_feb")
    game = _sample("feb_game.json")
    database[FEB].insert_one({**copy.deepcopy(game), "_id": 1})
    teams = get_available_teams_from_collection(_collection_handler(database, FEB), FEB)
    team = game["HEADER"]["TEAM"][0]

    assert teams and {t["name"] for t in teams} >= {team["name"]}
    assert resolve_team_by_id(database[FEB], str(team["id"]), False) == {"id": str(team["id"]), "name": team["name"]}
    assert resolve_team_by_id(database[FEB], "999999999", False) is None


def test_a_feb_game_with_only_its_header_still_gives_its_teams():
    database = new_mock_db("teams_header")
    header_only = {"_id": 1, "HEADER": {"TEAM": [{"teamCode": "AAA", "name": "ALPHA", "id": "11"}, {"teamCode": "BBB", "name": "BRAVO", "id": "22"}, {"teamCode": "AAA", "name": "ALPHA DUPLICADO", "id": "33"}]}}
    database[FEB].insert_one(header_only)

    teams = get_available_teams_from_collection(_collection_handler(database, FEB), FEB)

    assert [t["name"] for t in teams] == ["ALPHA", "BRAVO"] and teams[0]["id"] == "11"


def test_the_teams_of_an_fbcyl_collection_resolve_by_their_stable_id():
    database = new_mock_db("teams_fbcyl")
    game = _sample("fbcyl_game.json")
    database[FBCYL].insert_one({**copy.deepcopy(game), "_id": "u1"})
    extern = game["stats"]["teams"][0]["teamIdExtern"]

    found = resolve_team_by_id(database[FBCYL], str(extern), True)

    assert found == {"id": str(extern), "name": game["stats"]["teams"][0]["name"]}
    assert resolve_team_by_id(database[FBCYL], "123456789", True) is None


def test_a_collection_that_cannot_be_read_has_no_teams():
    handler = MagicMock()
    handler.connection.get_collection.side_effect = RuntimeError("no database")

    assert get_available_teams_from_collection(handler, FEB) == []


# ---------------------------------------------------------------- the last game of a team

def _repository(collection):
    connection = MagicMock()
    connection.is_connected.return_value = True
    connection.get_collection.return_value = collection
    return BasketballRepository(connection)


@pytest.mark.parametrize("name, parse_key", [(FEB, "_parsedDate"), (FBCYL, "_parsedDate")])
def test_the_last_game_of_a_team_is_chosen_inside_mongo_and_only_one_document_comes_back(name, parse_key):
    collection = MagicMock()
    collection.aggregate.return_value = iter([{"_id": "last"}])

    found = _repository(collection).get_last_game_for_team(name, "10", projection={"HEADER": 1})
    pipeline = collection.aggregate.call_args[0][0]

    assert found == [{"_id": "last"}]
    assert {"$limit": 1} in pipeline and {"$sort": {parse_key: -1}} in pipeline and {"$project": {"HEADER": 1}} == pipeline[-1]
    assert {"$match": {parse_key: {"$ne": None}}} in pipeline                                  # a game with an unreadable date is ignored


def test_the_last_game_of_a_team_is_empty_when_mongo_fails_or_there_is_no_connection():
    collection = MagicMock()
    collection.aggregate.side_effect = pme.PyMongoError("boom")
    assert _repository(collection).get_last_game_for_team(FEB, "10") == []

    offline = _repository(MagicMock())
    offline.connection.is_connected.return_value = False
    assert offline.get_last_game_for_team(FEB, "10") == []
