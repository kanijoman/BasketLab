"""The parity vectors of the weekly report in the browser (#716) are kept honest: a change in a row builder of ``_weekly_report_helpers`` shows up as a diff.

``python tests/local_vectors/generate.py`` regenerates ``weekly_rows.json``; the web (``frontend/src/lib/weeklyRows.test.ts``) must answer the same.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import generate  # noqa: E402
import weekly_report_vectors  # noqa: E402


def _stored():
    return json.loads(generate.WEEKLY_ROWS_OUT.read_text(encoding="utf-8"))


def test_the_stored_weekly_rows_vectors_are_the_current_reference():
    assert json.loads(json.dumps(weekly_report_vectors.build(), sort_keys=True)) == json.loads(json.dumps(_stored(), sort_keys=True))


def test_the_weekly_rows_vectors_cover_what_the_browser_has_to_get_right():
    leagues = {league["name"]: league for league in _stored()["leagues"]}
    assert set(leagues) == {"sample", "awkward", "empty"}
    awkward = leagues["awkward"]
    colours = {c for table in ("basic", "advanced") for inv in ("False", "True") for row in awkward[table][inv]["colors"] for c in row}
    assert colours >= {"#500000", "#3d2000", "#5a3e00", "#14532d", "#0d1117"}                          # every quartile colour and the plain cell
    texts = [t for row in awkward["comparative_basic"]["False"]["texts"] for t in row]
    assert any(t.endswith("(0.0)") for t in texts) and any("(+" in t for t in texts) and any("(-" in t for t in texts)   # no difference, up and down
    assert any(t == "-" for row in awkward["consistency_rows"]["texts"] for t in row)                    # a missing coefficient
    assert awkward["player_rows"]["projection"]["texts"] and leagues["empty"]["player_rows"]["avg"]["texts"] == []
    assert "last_match" not in leagues["empty"]
