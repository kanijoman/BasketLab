"""The parity vectors of the local team tables (#327) are kept honest: any change in the season pipelines shows up as a diff of the file.

``python tests/local_vectors/generate.py`` regenerates ``team_stats_feb.json``; the web (``frontend/src/localdata/aggregateTeams.test.ts``) must
reproduce its figures from its rows. Corner cases the filters tell apart are asserted here so that the file cannot go blind.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import generate  # noqa: E402


@pytest.fixture(scope="module")
def vectors():
    return generate.build_vectors()


def test_the_stored_vectors_are_the_current_reference(vectors):
    stored = json.loads(generate.OUT.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(vectors, sort_keys=True)) == stored


def test_the_filters_tell_something_apart(vectors):
    by_name = {c["name"]: c for c in vectors["cases"]}
    games = lambda case: sum(t["total_games"] for t in case["team_stats"])  # noqa: E731
    assert games(by_name["all"]) == 24
    assert games(by_name["home"]) == games(by_name["away"]) == 12
    assert games(by_name["won"]) == games(by_name["lost"]) == 12
    assert 0 < games(by_name["date range"]) < 24
    assert games(by_name["empty range"]) == 0
    assert 0 < games(by_name["to date (the games of the last day are in)"]) < games(by_name["all"])


@pytest.fixture(scope="module")
def player_vectors():
    return generate.build_player_vectors()


def test_the_stored_player_vectors_are_the_current_reference(player_vectors):
    stored = json.loads(generate.PLAYERS_OUT.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(player_vectors, sort_keys=True)) == stored


def test_the_player_filters_tell_something_apart(player_vectors):
    by_name = {c["name"]: c["players"] for c in player_vectors["cases"]}
    games = lambda case: sum(p["games_played"] for p in case)  # noqa: E731
    assert games(by_name["home"]) + games(by_name["away"]) == games(by_name["all"]) > 0
    assert games(by_name["won"]) + games(by_name["lost"]) == games(by_name["all"])
    assert {p["team_name"] for p in by_name["one team"]} == {"BRAVO"} and by_name["unknown team"] == []
    assert all("usage_pct" in p and "pie" in p for p in by_name["all"])                  # enriched from the whole season even when filtered
    ids = [(p["team_id"], p["player_id"]) for p in by_name["all"]]
    assert len(ids) == len(set(ids))                                                       # one row per player within his team, whatever name he was written under (#652)


@pytest.fixture(scope="module")
def fbcyl_vectors():
    return generate.build_fbcyl_vectors()


def test_the_stored_fbcyl_vectors_are_the_current_reference(fbcyl_vectors):
    stored = json.loads(generate.FBCYL_OUT.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(fbcyl_vectors, sort_keys=True)) == stored


def test_the_fbcyl_filters_tell_something_apart_and_the_day_bound_is_inclusive(fbcyl_vectors):
    by_name = {c["name"]: c["team_stats"] for c in fbcyl_vectors["cases"]}
    games = lambda case: sum(t["total_games"] for t in case)  # noqa: E731
    assert games(by_name["all"]) == 24 and games(by_name["empty range"]) == 0
    assert games(by_name["won"]) + games(by_name["lost"]) == 22                         # the tied game is in neither
    assert games(by_name["to date (the games of the last day are in)"]) > 0


# FBCYL players (#644): the rows are regenerated everywhere (the exporter runs on mongomock); the API side of the vectors needs the real season
# pipeline, which uses operators mongomock does not have (``$substrCP``, ``$reduce``, ``$getField``), so it is generated on a real mongod, committed,
# and only recomputed here when one is reachable.
import generate_fbcyl_players as fbcyl_players  # noqa: E402


@pytest.fixture(scope="module")
def stored_fbcyl_players():
    return json.loads(fbcyl_players.OUT.read_text(encoding="utf-8"))


def test_the_stored_fbcyl_player_rows_are_the_current_exporter_output(stored_fbcyl_players):
    assert json.loads(json.dumps(fbcyl_players.build_rows(), sort_keys=True, default=str)) == stored_fbcyl_players["rows"]


def test_the_fbcyl_player_filters_tell_something_apart(stored_fbcyl_players):
    by_name = {c["name"]: c["players"] for c in stored_fbcyl_players["cases"]}
    games = lambda case: sum(p["games_played"] for p in case)  # noqa: E731
    assert games(by_name["home"]) + games(by_name["away"]) == games(by_name["all"]) > 0
    assert games(by_name["won"]) + games(by_name["lost"]) < games(by_name["all"])        # the tied game is neither
    assert {p["team_name"] for p in by_name["one team"]} == {"BRAVO"} and by_name["unknown team"] == []
    assert all("usage_pct" in p and "pie" in p and p["player_uuid"] for p in by_name["all"])
    assert any(" " in str(p["player_uuid"]) for c in stored_fbcyl_players["cases"] for p in c["players"])   # the divergence of the date filter is in the file


def _real_mongod():
    try:
        from pymongo import MongoClient

        client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=1000)
        client.admin.command("ping")
        return client
    except Exception:  # noqa: BLE001
        return None


def test_the_stored_fbcyl_player_cases_are_what_the_real_pipeline_answers(stored_fbcyl_players):
    client = _real_mongod()
    if client is None:
        pytest.skip("needs a real mongod: FBCYL's player pipeline uses operators mongomock does not implement")
    assert json.loads(json.dumps(fbcyl_players.build_cases(client), sort_keys=True, default=str)) == stored_fbcyl_players["cases"]
