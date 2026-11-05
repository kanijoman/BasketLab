"""The matchup of the scouting (our team against the rival, stat by stat) is computed on the device (issue #751: it was a job on the server).

``live_prep.scouting_compare.compare_teams`` is the reference; ``frontend/src/lib/scoutingCompare.ts`` must answer every case of ``tests/local_vectors/scouting_compare.json`` and carry the
same catalog of stats. ``python tests/local_vectors/generate.py`` regenerates the file: any change in the Python side shows up as a diff here.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import generate  # noqa: E402
import scouting_compare_vectors  # noqa: E402

from src.report_engine.catalog import CATALOG  # noqa: E402


def _stored():
    return json.loads(generate.SCOUTING_COMPARE_OUT.read_text(encoding="utf-8"))


def test_the_stored_vectors_are_the_current_reference():
    assert json.loads(json.dumps(scouting_compare_vectors.build(), sort_keys=True)) == _stored()


def test_the_catalog_of_the_vectors_is_the_one_of_the_report_engine():
    catalog = _stored()["catalog"]
    assert [(s["key"], s["label"], s["group"], s["higher_is_better"], s["pct"]) for s in catalog] == [(s.key, s.label, s.group, s.higher_is_better, s.pct) for s in CATALOG]


def test_the_cases_tell_every_kind_of_advantage_and_the_awkward_inputs_apart():
    cases = _stored()["cases"]
    seen = {row["advantage"] for case in cases for row in case["expected"]}
    assert seen == {"own", "rival", "even", "neutral"}
    assert any(not case["expected"] for case in cases)                                   # a team without row: nothing to compare
    assert any(any(row["key"] == "bench_pct" for row in case["expected"]) for case in cases)    # the play-by-play figures complete the rows
    assert any(len(case["expected"]) < len(CATALOG) and case["expected"] for case in cases)    # a stat missing on one side is left out
    assert any(case.get("threshold_pct") not in (None, 5.0) for case in cases)                  # the threshold is a parameter
