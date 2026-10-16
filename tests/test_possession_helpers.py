"""Tests for the pbp timestamp helper (regular time and overtimes)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from src.pbp.event_helpers import get_timestamp


# ---------------------------------------------------------------------------
# Move helpers
# ---------------------------------------------------------------------------

def _feb_move(quarter: int, time: str, action: str = "fthrow", text: str = "TIRO DE 1 ANOTADO") -> dict:
    return {"quarter": str(quarter), "time": time, "idTeam": "T1", "action": action, "text": text}


def _fbcyl_move(period: int, min_: int, sec: int, team: str = "T1") -> dict:
    return {"period": period, "min": min_, "sec": sec, "idTeam": team,
            "action": "fthrow", "move": "Canasta de 1"}


# ---------------------------------------------------------------------------
# RC3 — Regular-time timestamps (regression guard, must pass before and after)
# ---------------------------------------------------------------------------

class TestGetTimestampRegular:
    def test_feb_q1_start_is_0(self):
        assert get_timestamp(_feb_move(1, "10:00"), False) == 0

    def test_feb_q1_end_is_600(self):
        assert get_timestamp(_feb_move(1, "0:00"), False) == 600

    def test_feb_q2_start_is_600(self):
        assert get_timestamp(_feb_move(2, "10:00"), False) == 600

    def test_feb_q4_end_is_2400(self):
        assert get_timestamp(_feb_move(4, "0:00"), False) == 2400

    def test_fbcyl_p1_start_is_0(self):
        assert get_timestamp(_fbcyl_move(1, 10, 0), True) == 0

    def test_fbcyl_p1_end_is_600(self):
        assert get_timestamp(_fbcyl_move(1, 0, 0), True) == 600

    def test_fbcyl_p5_start_is_2400(self):
        """Period 5 (1st OT) 5:00 remaining → 2400. Already correct in current code."""
        assert get_timestamp(_fbcyl_move(5, 5, 0), True) == 2400


# ---------------------------------------------------------------------------
# RC3 — OT timestamps (all FAIL before fix)
# ---------------------------------------------------------------------------

class TestGetTimestampOT:
    """RC3 — overtime periods are 5 min (300s), not 10 min (600s)."""

    # --- FEB ---

    def test_feb_ot1_start_is_2400(self):
        """Q5 countdown 5:00 = start of 1st OT → 2400s total elapsed."""
        assert get_timestamp(_feb_move(5, "5:00"), False) == 2400

    def test_feb_ot1_one_second_in_is_2401(self):
        """Q5 countdown 4:59 → 2401s total elapsed."""
        assert get_timestamp(_feb_move(5, "4:59"), False) == 2401

    def test_feb_ot1_end_is_2700(self):
        """Q5 countdown 0:00 = end of 1st OT → 2700s total elapsed."""
        assert get_timestamp(_feb_move(5, "0:00"), False) == 2700

    def test_feb_ot2_start_is_2700(self):
        """Q6 countdown 5:00 = start of 2nd OT → 2700s total elapsed."""
        assert get_timestamp(_feb_move(6, "5:00"), False) == 2700

    def test_feb_ot2_end_is_3000(self):
        """Q6 countdown 0:00 = end of 2nd OT → 3000s total elapsed."""
        assert get_timestamp(_feb_move(6, "0:00"), False) == 3000

    # --- FBCYL ---

    def test_fbcyl_ot2_start_is_2700(self):
        """Period 6 (2nd OT) 5:00 remaining → 2700s. BUG: current gives 3000."""
        assert get_timestamp(_fbcyl_move(6, 5, 0), True) == 2700

    def test_fbcyl_ot2_mid_is_2850(self):
        """Period 6 2:30 remaining → 2700 + 150 = 2850."""
        assert get_timestamp(_fbcyl_move(6, 2, 30), True) == 2850

    def test_fbcyl_ot2_end_is_3000(self):
        """Period 6 0:00 remaining → 3000s."""
        assert get_timestamp(_fbcyl_move(6, 0, 0), True) == 3000

    def test_fbcyl_ot3_start_is_3000(self):
        """Period 7 (3rd OT) 5:00 remaining → 3000s. BUG: current gives 3600."""
        assert get_timestamp(_fbcyl_move(7, 5, 0), True) == 3000
