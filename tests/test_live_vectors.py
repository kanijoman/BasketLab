"""Shared test vectors: Python is the reference, Pyodide must reproduce it exactly.

``tests/live_vectors/vectors.json`` holds inputs and the results the reference produced.
This test keeps the file honest: any change in behaviour shows up as a diff of that file
(regenerate with ``python tests/live_vectors/generate.py`` and review it), and the same
runner (``src.live_core.vectors``) is executed inside Pyodide by ``tests/pyodide``.
"""

import json
from pathlib import Path

import pytest

from src.live_core.vectors import (
    canonical,
    digest,
    run_suite,
    to_jsonable,
    unwrap_extended_json,
)

ROOT = Path(__file__).resolve().parent.parent
VECTORS = ROOT / "tests" / "live_vectors" / "vectors.json"
GAME = ROOT / "src" / "JSON_samples" / "feb_game.json"


@pytest.fixture(scope="module")
def suite():
    return json.loads(VECTORS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def game():
    return unwrap_extended_json(json.loads(GAME.read_text(encoding="utf-8")))


def test_the_stored_expectations_match_the_current_reference(suite, game):
    actual = run_suite({k: v for k, v in suite.items() if k != "expected"}, game)
    assert actual["unit"] == suite["expected"]["unit"]
    assert actual["engine"]["checkpoints"] == suite["expected"]["engine"]["checkpoints"]


def test_the_vector_file_covers_every_area(suite):
    fns = {case["fn"] for case in suite["unit"]}
    for prefix in ("clock.", "events.", "fouls.", "fatigue.", "four_factors.", "profiles.", "zones.",
                   "recommender.", "advice."):
        assert any(f.startswith(prefix) for f in fns), f"no vectors for {prefix}"
    assert len(suite["engine"]["checkpoints"]) >= 8


def test_engine_vectors_follow_the_whole_game(suite):
    cps = suite["expected"]["engine"]["checkpoints"]
    scores = [sum(c["score"].values()) for c in cps]
    assert scores == sorted(scores) and scores[-1] > scores[0]
    assert all(set(c["digests"]) == {"snapshot", "alerts", "analysis"} for c in cps)


def test_the_runner_is_deterministic(suite, game):
    spec = {k: v for k, v in suite.items() if k != "expected"}
    assert canonical(run_suite(spec, game)) == canonical(run_suite(spec, game))


def test_digest_is_sensitive_to_any_change():
    base = {"a": [1, 2, {"b": 3.5}]}
    assert digest(base) == digest({"a": [1, 2, {"b": 3.5}]})
    assert digest(base) != digest({"a": [1, 2, {"b": 3.6}]})
    assert digest({"x": 1, "y": 2}) == digest({"y": 2, "x": 1}), "key order must not matter"


def test_to_jsonable_handles_dataclasses_tuples_and_none():
    from dataclasses import dataclass

    @dataclass
    class P:
        a: int
        b: tuple

    assert to_jsonable(P(1, (2, 3))) == {"a": 1, "b": [2, 3]}
    assert to_jsonable(None) is None and to_jsonable((1, (2,))) == [1, [2]]


def test_unwrap_extended_json():
    assert unwrap_extended_json({"a": {"$numberInt": "4"}, "b": [{"$numberInt": "7"}, "x"]}) == {"a": 4, "b": [7, "x"]}


def test_a_changed_behaviour_would_be_caught(suite, game, monkeypatch):
    import src.live_core.rules_fouls as fouls

    monkeypatch.setattr(fouls, "WARNING_CAP", 5)
    actual = run_suite({k: v for k, v in suite.items() if k != "expected"}, game)
    assert actual["unit"] != suite["expected"]["unit"] or \
        actual["engine"]["checkpoints"] != suite["expected"]["engine"]["checkpoints"]
