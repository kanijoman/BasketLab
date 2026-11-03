"""The parity vectors of the DOCX of the individual scouting in the browser (#717) are kept honest: a change in ``player_tables`` or in the radar shows up as a diff.

``python tests/local_vectors/generate.py`` regenerates ``scouting_docx.json``; the web (``frontend/src/lib/scoutingDocx.test.ts``, ``radarChart.test.ts``) must answer the same.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import generate  # noqa: E402
import scouting_docx_vectors  # noqa: E402


def _stored():
    return json.loads(generate.SCOUTING_DOCX_OUT.read_text(encoding="utf-8"))


def test_the_stored_docx_vectors_are_the_current_reference():
    assert json.loads(json.dumps(scouting_docx_vectors.build(), sort_keys=True)) == json.loads(json.dumps(_stored(), sort_keys=True))


def test_the_docx_vectors_cover_what_the_browser_has_to_get_right():
    leagues = {league["name"]: league for league in _stored()["leagues"]}
    assert set(leagues) == {"sample", "awkward"}
    awkward = leagues["awkward"]
    cells = [cell for expected in awkward["expected"] for table in ("averages", "advanced") for cell in expected[table]["cells"]]
    assert any(cell["text"] == "-" and cell["fill"] is None for cell in cells)                    # a figure that is missing
    assert {cell["fill"] for cell in cells} >= {"C6EFCE", "FFEB9C", "FFD9B3", "FFC7CE", None}      # every colour of the quartiles and none
    assert any(expected["totals"]["cells"][1].endswith(":60") for expected in awkward["expected"])  # the minutes that round up to a whole minute, as Python rounds them
    assert all(len(r["values"]) == 16 == len(r["averages"]) for league in leagues.values() for r in league["radar"])
