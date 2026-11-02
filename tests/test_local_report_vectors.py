"""The parity vectors of the PDF of the team report in the browser (#714) are kept honest: any change in ``render_report_html`` or in the report itself shows up as a diff of ``report_html.json``.

``python tests/local_vectors/generate.py`` regenerates it; the web (``frontend/src/lib/teamReportPdf.test.ts``) must write the same HTML from each report, string for string.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import generate  # noqa: E402
import report_vectors  # noqa: E402


def _stored():
    return json.loads(generate.REPORT_HTML_OUT.read_text(encoding="utf-8"))


def test_the_stored_report_vectors_are_the_current_reference():
    assert json.loads(json.dumps(report_vectors.build(), sort_keys=True)) == _stored()


def test_the_report_vectors_cover_what_the_browser_has_to_get_right():
    reports = [c["report"] for c in _stored()["cases"]]
    assert {r["mode"] for r in reports} == {"own", "rival"}
    assert any(r.get("zones") for r in reports) and any("zones" not in r for r in reports)          # zones, and none at all
    assert any(r["low_sample"] for r in reports) and any(not r["low_sample"] for r in reports)
    assert any(f["diff_pct"] is None for r in reports for f in r["weaknesses"])                      # a finding with no difference to the median
    assert any(not r["strengths"] for r in reports) and any(not r["training"] for r in reports)       # the empty-section sentences
    assert any(x["status"] == "inconsistent" for r in reports for x in r["consistency"])
    assert any("&" in r["team"] and "<" in r["team"] for r in reports)                                # what HTML escapes
    assert any(f["diff_pct"] is not None and abs(f["diff_pct"] * 10 % 1 - 0.5) < 1e-9 for r in reports for f in r["strengths"])      # an exact tie of the rounding (12.25 -> 12.2)
