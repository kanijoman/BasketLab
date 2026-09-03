"""Regression test for the possession-stats Mongo projection.

Guards against dropping 'num' from the FEB projection: order_possession_moves()
uses it to break ties between same-timestamp events. Without it, same-second
sequences (rebound scrums, steal chains) sort unpredictably and fragment real
possessions into spurious extra ones, silently corrupting pace/OER.
"""
import sys
from pathlib import Path

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from database.repository_possession import _possession_projection


def test_feb_projection_includes_num_for_tie_breaking():
    projection = _possession_projection(is_fbcyl=False)
    assert projection.get("PLAYBYPLAY.LINES.num") == 1


def test_feb_projection_still_includes_required_fields():
    projection = _possession_projection(is_fbcyl=False)
    for field in (
        "PLAYBYPLAY.LINES.text", "PLAYBYPLAY.LINES.quarter",
        "PLAYBYPLAY.LINES.time", "PLAYBYPLAY.LINES.action",
        "PLAYBYPLAY.LINES.idTeam", "HEADER.TEAM.id",
    ):
        assert projection.get(field) == 1


def test_fbcyl_projection_unaffected():
    projection = _possession_projection(is_fbcyl=True)
    assert "PLAYBYPLAY.LINES.num" not in projection
    assert projection.get("moves.idTeam") == 1
