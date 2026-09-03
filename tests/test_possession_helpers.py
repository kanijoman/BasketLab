"""Tests for _possession_helpers: OT timestamp fix (RC3) and FT interleaving fix (RC1)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from database._possession_helpers import ft_sequence_info, get_timestamp


# ---------------------------------------------------------------------------
# Move helpers
# ---------------------------------------------------------------------------

def _feb_ft(team: str = "T1", made: bool = True, quarter: int = 1, time: str = "8:31") -> dict:
    text = "TIRO DE 1 ANOTADO" if made else "TIRO DE 1 FALLADO"
    return {"action": "fthrow", "idTeam": team, "text": text, "quarter": str(quarter), "time": time}


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
        assert get_timestamp(_fbcyl_move(1, 0, 0), True) == 0

    def test_fbcyl_p1_end_is_600(self):
        assert get_timestamp(_fbcyl_move(1, 10, 0), True) == 600

    def test_fbcyl_p5_start_is_2400(self):
        """Period 5 (1st OT) elapsed 0:00 → 2400. Already correct in current code."""
        assert get_timestamp(_fbcyl_move(5, 0, 0), True) == 2400


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
        """Period 6 (2nd OT) elapsed 0:00 → 2700s. BUG: current gives 3000."""
        assert get_timestamp(_fbcyl_move(6, 0, 0), True) == 2700

    def test_fbcyl_ot2_mid_is_2850(self):
        """Period 6 elapsed 2:30 → 2700 + 150 = 2850."""
        assert get_timestamp(_fbcyl_move(6, 2, 30), True) == 2850

    def test_fbcyl_ot2_end_is_3000(self):
        """Period 6 elapsed 5:00 → 3000s."""
        assert get_timestamp(_fbcyl_move(6, 5, 0), True) == 3000

    def test_fbcyl_ot3_start_is_3000(self):
        """Period 7 (3rd OT) elapsed 0:00 → 3000s. BUG: current gives 3600."""
        assert get_timestamp(_fbcyl_move(7, 0, 0), True) == 3000


# ---------------------------------------------------------------------------
# RC1 — ft_sequence_info: same-timestamp other-team FT interleaving (all FAIL before fix)
# ---------------------------------------------------------------------------

class TestFtSequenceInfoInterleaving:
    """RC1 — ft_sequence_info forward scan must skip other-team FTs at identical timestamps."""

    def test_forward_scan_skips_same_ts_other_team_ft_is_last_false(self):
        """FT_A1, FT_B (technical, same ts), FT_A2 → FT_A1 must NOT be last."""
        moves = [
            _feb_ft("A", made=True,  time="8:31"),   # idx 0: FT_A1
            _feb_ft("B", made=True,  time="8:31"),   # idx 1: FT_B technical (same ts)
            _feb_ft("A", made=True,  time="8:31"),   # idx 2: FT_A2
        ]
        is_last, made_pts = ft_sequence_info(0, moves, False)
        assert is_last is False, "FT_A1 cannot be last when FT_A2 exists at same timestamp"

    def test_forward_scan_skips_same_ts_other_team_ft_made_pts(self):
        """FT_A1, FT_B (technical, same ts), FT_A2 → 2 pts total for team A sequence."""
        moves = [
            _feb_ft("A", made=True,  time="8:31"),
            _feb_ft("B", made=True,  time="8:31"),
            _feb_ft("A", made=True,  time="8:31"),
        ]
        _, made_pts = ft_sequence_info(0, moves, False)
        assert made_pts == 2

    def test_backward_scan_skips_same_ts_other_team_ft(self):
        """FT_A2 (idx=2) must find FT_A1 (idx=0) as sequence start, skipping FT_B (idx=1)."""
        moves = [
            _feb_ft("A", made=True, time="8:31"),    # idx 0: FT_A1
            _feb_ft("B", made=True, time="8:31"),    # idx 1: FT_B (same ts)
            _feb_ft("A", made=True, time="8:31"),    # idx 2: FT_A2
        ]
        is_last, made_pts = ft_sequence_info(2, moves, False)
        assert is_last is True, "FT_A2 is the last in team A's sequence"
        assert made_pts == 2, "Full sequence for team A is 2 made FTs"

    def test_missed_ft_in_interleaved_sequence(self):
        """FT_A1 missed, FT_B (technical), FT_A2 made → team A made=1, not last at idx 0."""
        moves = [
            _feb_ft("A", made=False, time="8:31"),   # idx 0: FT_A1 missed
            _feb_ft("B", made=True,  time="8:31"),   # idx 1: FT_B technical
            _feb_ft("A", made=True,  time="8:31"),   # idx 2: FT_A2 made
        ]
        is_last, made_pts = ft_sequence_info(0, moves, False)
        assert is_last is False
        assert made_pts == 1

    def test_normal_sequence_unaffected(self):
        """Two consecutive FTs from same team at slightly different timestamps still works."""
        moves = [
            _feb_ft("A", made=True, time="8:31"),   # FT_A1
            _feb_ft("A", made=True, time="8:30"),   # FT_A2 (next second, countdown)
        ]
        is_last_0, pts_0 = ft_sequence_info(0, moves, False)
        is_last_1, pts_1 = ft_sequence_info(1, moves, False)
        assert is_last_0 is False
        assert is_last_1 is True
        assert pts_0 == 2
        assert pts_1 == 2

    def test_different_ts_other_team_still_breaks_forward(self):
        """Other-team FT at DIFFERENT timestamp must still end the forward scan."""
        moves = [
            _feb_ft("A", made=True, time="8:31"),   # idx 0: FT_A1
            _feb_ft("B", made=True, time="8:00"),   # idx 1: FT_B at different ts
            _feb_ft("A", made=True, time="7:59"),   # idx 2: FT_A2 (different possession)
        ]
        is_last_0, pts_0 = ft_sequence_info(0, moves, False)
        assert is_last_0 is True, "FT_A1 must be last; FT_B at different ts ends the scan"
        assert pts_0 == 1
