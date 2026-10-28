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
