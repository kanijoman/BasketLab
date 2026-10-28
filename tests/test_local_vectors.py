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
    assert games(by_name["to date (the last day's games are left out: midnight bound)"]) < games(by_name["all"])


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
    assert any(p["player_name"].endswith("RENAMED") for p in by_name["all"])             # the same id under another name is another row
