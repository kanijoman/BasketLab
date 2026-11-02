"""The parity vectors of the PDF of the rival scouting in the browser (#715) are kept honest: any change in the layout of ``scouting_pdf`` or in the report shows up as a diff of ``scouting_pdf.json``.

``python tests/local_vectors/generate.py`` regenerates it; the web (``frontend/src/lib/scoutingPdf.test.ts``) must ask for the same calls, in the same order, for each report.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import generate  # noqa: E402
import scouting_pdf_vectors  # noqa: E402


def _stored():
    return json.loads(generate.SCOUTING_PDF_OUT.read_text(encoding="utf-8"))


def test_the_stored_scouting_pdf_vectors_are_the_current_reference():
    assert json.loads(json.dumps(scouting_pdf_vectors.build(), sort_keys=True)) == _stored()


def test_the_scouting_pdf_vectors_cover_what_the_browser_has_to_get_right():
    cases = _stored()["cases"]
    methods = {call[0] for case in cases for call in case["calls"]}
    assert methods == {"h1", "h2", "para", "bullet", "ln", "image", "table"}
    tables = [call for case in cases for call in case["calls"] if call[0] == "table"]
    assert any(call[5] and any(c for row in call[5] for c in row) for call in tables)                 # coloured cells (zones, origin and comparison)
    assert any(call[4] for call in tables) and any(not call[4] for call in tables)                    # custom aligns, and the default ones
    assert any(call[0] == "h2" and call[2] == 35 for case in cases for call in case["calls"])
    assert any(call[0] == "h2" and call[2] == 120 for case in cases for call in case["calls"])         # the heading that travels with the chart
    assert any(not any(c[0] == "image" for c in case["calls"]) for case in cases)                       # a report without zones has no chart
    assert any("Jugadoras" in json.dumps(case["calls"]) for case in cases)                              # the women's wording
    assert any(call[0] == "para" and call[4] == [180, 40, 40] for case in cases for call in case["calls"])   # the notices, in red
    assert [value for value, _ in _stored()["safe"]][-1] == 42
