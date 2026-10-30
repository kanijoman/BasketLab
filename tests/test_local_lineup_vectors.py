"""The parity vectors of Combinaciones on the device (#686) are kept honest: any change in the lineup code or in the exporter shows up as a diff of the files.

``python tests/local_vectors/generate.py`` regenerates ``lineups_feb.json`` and ``lineups_fbcyl.json``; the web (``frontend/src/localdata/lineups.test.ts``) must answer every case
from the published counters. The cases the browser has to get right (a lineup that played one game, several, none in the period…) are asserted here so that the files cannot go blind.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import generate  # noqa: E402
import lineup_vectors  # noqa: E402

LEAGUES = [("feb", "LINEUPS_OUT"), ("fbcyl", "LINEUPS_FBCYL_OUT")]


@pytest.mark.parametrize("kind, path", LEAGUES)
def test_the_stored_lineup_vectors_are_the_current_reference(kind, path):
    stored = json.loads(getattr(generate, path).read_text(encoding="utf-8"))
    assert json.loads(json.dumps(lineup_vectors.build(kind), sort_keys=True)) == stored


def _case(vectors, name, size):
    return next(c for c in vectors["cases"] if c["config"]["name"].startswith(name) and c["size"] == size)["rows"]


@pytest.mark.parametrize("kind, path", LEAGUES)
def test_the_lineup_vectors_cover_the_branches_of_the_merge(kind, path):
    vectors = json.loads(getattr(generate, path).read_text(encoding="utf-8"))
    team = vectors["published"]["teams"][0]
    assert len(team["games"]) == 5 and set(team["sizes"]) == {"2", "3", "4", "5"}
    free = _case(vectors, "no minimums", 5)
    assert {r["games_played"] for r in free} >= {1, 3}                                    # a lineup of one game and one that merges several
    assert all(r["games_played"] >= 5 for r in _case(vectors, "defaults", 5)) and len(_case(vectors, "defaults", 5)) < len(free)
    logged = _case(vectors, "game log", 5)
    assert any(len(r["game_log"]) >= 3 and r["ifq"] is not None for r in logged) and any(r["ifq"] is None for r in logged)
    assert all("game_log" not in r for r in free)
    assert _case(vectors, "nothing in the period", 5) == []
    assert 0 < len(_case(vectors, "last 7 days", 5)) and all(r["games_played"] == 1 for r in _case(vectors, "last 7 days", 5))
    assert all(r["games_played"] == 1 for r in _case(vectors, "the last game", 3))
    assert 0 < len(_case(vectors, "the minimum of games is capped", 5))                   # the default 5 games cannot be met in a period of one
    drtg = [r["drtg"] for r in _case(vectors, "by DRtg", 5)]
    assert drtg == sorted(drtg)                                                           # lower is better: ascending
    assert [r["net_rating"] for r in free] == sorted((r["net_rating"] for r in free), reverse=True)
