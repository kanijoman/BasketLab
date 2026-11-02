"""The parity vectors of the quartiles of the players on the device (#707) are kept honest: any change in ``PlayerStatsService.get_quartiles`` or in the player tables shows up as a diff.

``python tests/local_vectors/generate.py`` regenerates ``player_quartiles.json``; the web (``frontend/src/localdata/playerQuartiles.test.ts``) must answer the same quartiles from the table.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import generate  # noqa: E402
import quartile_vectors  # noqa: E402


def _stored():
    return json.loads(generate.QUARTILES_OUT.read_text(encoding="utf-8"))


def test_the_stored_quartile_vectors_are_the_current_reference():
    assert json.loads(json.dumps(quartile_vectors.build(), sort_keys=True)) == _stored()


def test_the_quartile_vectors_cover_what_the_browser_has_to_get_right():
    awkward = _stored()["awkward"]
    assert any(p["games_played"] < 3 for p in awkward["players"])                              # players out for having played little
    assert any(p[field] is None for p in awkward["players"] for field in quartile_vectors.FIELDS)
    quartiles = awkward["quartiles"]
    assert "fg3_percentage" not in quartiles and len(quartiles) >= 10                          # a field with fewer than four values has no quartiles
    assert all(set(v) == {"min", "q1", "q2", "q3", "max", "count"} for v in quartiles.values())
    assert set(_stored()) == {"feb", "fbcyl", "awkward"}
