"""Characterization of the FEB and FBCYL historical normalizers (issue #452, block 3).

Both build the same two-team record from different raw data; the shared part lives once
(``build_team_docs``). The golden file was produced by the two separate implementations
before they were merged, so a change in what is stored for a team fails here.
"""
import json
from datetime import datetime
from pathlib import Path

import pytest

from tests.test_historical_ingestion import _make_fbcyl_doc, _make_feb_doc
from src.services.historical_ingestion_service import normalize_fbcyl_match, normalize_feb_match

GOLDEN = json.loads((Path(__file__).parent / "fixtures" / "historical_normalizers_golden.json").read_text(encoding="utf-8"))
T = datetime(2026, 1, 1)


def _feb_zeros():
    return {**_make_feb_doc(), "BOXSCORE": {"TEAM": [{"id": "T1", "name": "A", "TOTAL": {}}, {"id": "T2", "name": "B", "TOTAL": {}}]}}


CASES = {
    "feb": lambda: normalize_feb_match(_make_feb_doc(), "2024-25", "LF2", "A", "FEB_LF2_2025_A", scraped_at=T),
    "fbcyl": lambda: normalize_fbcyl_match(_make_fbcyl_doc(), "2024-25", "SE", "", "F", "FBCYL_SE_2025", scraped_at=T),
    "feb_empty_poss": lambda: normalize_feb_match(_feb_zeros(), "2024-25", "LF2", "A", "c", scraped_at=T),
    "fbcyl_empty": lambda: normalize_fbcyl_match({"_id": "x", "stats": {"teams": [{"id": "1"}, {"id": "2"}]}}, "2024-25", "SE", "", None, "c", scraped_at=T),
    "feb_one_team": lambda: normalize_feb_match({**_make_feb_doc(), "BOXSCORE": {"TEAM": []}}, "s", "c", "g", "c", scraped_at=T),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_normalizer_output_is_the_one_stored_before_the_merge(case):
    assert json.loads(json.dumps(CASES[case](), default=str)) == GOLDEN[case]
