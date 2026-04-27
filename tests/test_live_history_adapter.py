"""Tests for LiveHistoryAdapter — FASE quality coverage.

Targets missing lines: 40-44, 79-86, 98-123, 131-160
(_derive_season, get_team_history, _load_fbcyl, _load_feb)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from services.live_history_adapter import LiveHistoryAdapter, _derive_season


# ---------------------------------------------------------------------------
# _derive_season (line 40-44)
# ---------------------------------------------------------------------------

class TestDeriveSeasonHelper:
    def test_standard_fbcyl_pattern(self):
        name = "FBCYL_Women_Temporada_20252026"
        assert _derive_season(name) == "2025-26"

    def test_four_digit_year(self):
        name = "FBCYL_SeniorA_Temporada_20242025"
        assert _derive_season(name) == "2024-25"

    def test_no_match_falls_back_to_raw(self):
        name = "FEB_LF2_2025_A"
        assert _derive_season(name) == "FEB_LF2_2025_A"

    def test_embedded_pattern_in_long_name(self):
        name = "FBCYL_Femenino_FBCYL_1_DIVISION_FEMENINA_Temporada_20252026"
        assert _derive_season(name) == "2025-26"


# ---------------------------------------------------------------------------
# get_team_history — connection guard (line 79-82)
# ---------------------------------------------------------------------------

class TestGetTeamHistoryConnectionGuard:
    def test_disconnected_returns_empty_list(self):
        conn = MagicMock()
        conn.is_connected.return_value = False
        adapter = LiveHistoryAdapter(conn)
        result = adapter.get_team_history("FBCYL_Temporada_20252026", "TeamA", is_fbcyl=True)
        assert result == []

    def test_disconnected_feb_returns_empty_list(self):
        conn = MagicMock()
        conn.is_connected.return_value = False
        adapter = LiveHistoryAdapter(conn)
        result = adapter.get_team_history("FEB_LF2_2025_A", "TeamA", is_fbcyl=False)
        assert result == []


# ---------------------------------------------------------------------------
# _load_fbcyl (lines 98-123)
# ---------------------------------------------------------------------------

class TestLoadFBCYL:
    def _adapter(self, docs):
        conn = MagicMock()
        conn.is_connected.return_value = True
        mock_col = MagicMock()
        mock_col.find.return_value = docs
        conn.get_collection.return_value = mock_col
        return LiveHistoryAdapter(conn)

    def test_empty_collection_returns_empty_list(self):
        adapter = self._adapter([])
        result = adapter.get_team_history(
            "FBCYL_Temporada_20252026", "TeamA", is_fbcyl=True)
        assert result == []

    def test_col_find_exception_returns_empty_list(self):
        conn = MagicMock()
        conn.is_connected.return_value = True
        mock_col = MagicMock()
        mock_col.find.side_effect = Exception("DB error")
        conn.get_collection.return_value = mock_col
        adapter = LiveHistoryAdapter(conn)
        result = adapter.get_team_history("FBCYL_Temporada_20252026", "TeamA", is_fbcyl=True)
        assert result == []

    def test_normalize_exception_skipped(self):
        """Docs that cannot be normalised are silently skipped."""
        adapter = self._adapter([{"bad": "doc"}])
        # normalize_fbcyl_match will raise or return empty — adapter must swallow it
        with patch(
            "services.live_history_adapter.normalize_fbcyl_match",
            side_effect=Exception("parse error"),
        ):
            result = adapter.get_team_history("FBCYL_Temporada_20252026", "TeamA", is_fbcyl=True)
        assert result == []

    def test_only_matching_team_records_returned(self):
        """normalize_fbcyl_match returns two records; only the matching team's is kept."""
        adapter = self._adapter([{"_id": "g1"}])
        record_team = {"team_name": "TeamA", "date": None}
        record_opp  = {"team_name": "TeamB", "date": None}
        with patch(
            "services.live_history_adapter.normalize_fbcyl_match",
            return_value=[record_team, record_opp],
        ):
            result = adapter.get_team_history("FBCYL_Temporada_20252026", "TeamA", is_fbcyl=True)
        assert result == [record_team]

    def test_no_matching_team_skips_doc(self):
        adapter = self._adapter([{"_id": "g1"}])
        with patch(
            "services.live_history_adapter.normalize_fbcyl_match",
            return_value=[{"team_name": "OtherTeam", "date": None}],
        ):
            result = adapter.get_team_history("FBCYL_Temporada_20252026", "TeamA", is_fbcyl=True)
        assert result == []


# ---------------------------------------------------------------------------
# _load_feb (lines 131-160)
# ---------------------------------------------------------------------------

class TestLoadFEB:
    def _adapter(self, docs):
        conn = MagicMock()
        conn.is_connected.return_value = True
        mock_col = MagicMock()
        mock_col.find.return_value = docs
        conn.get_collection.return_value = mock_col
        return LiveHistoryAdapter(conn)

    def test_empty_collection_returns_empty_list(self):
        adapter = self._adapter([])
        result = adapter.get_team_history("FEB_LF2_2025_A", "TeamA", is_fbcyl=False)
        assert result == []

    def test_col_find_exception_returns_empty_list(self):
        conn = MagicMock()
        conn.is_connected.return_value = True
        mock_col = MagicMock()
        mock_col.find.side_effect = Exception("DB error")
        conn.get_collection.return_value = mock_col
        adapter = LiveHistoryAdapter(conn)
        result = adapter.get_team_history("FEB_LF2_2025_A", "TeamA", is_fbcyl=False)
        assert result == []

    def test_normalize_exception_skipped(self):
        adapter = self._adapter([{"bad": "doc"}])
        with patch(
            "services.live_history_adapter.normalize_feb_match",
            side_effect=Exception("parse error"),
        ):
            result = adapter.get_team_history("FEB_LF2_Temporada_20252026", "TeamA", is_fbcyl=False)
        assert result == []

    def test_only_matching_team_returned(self):
        adapter = self._adapter([{"_id": "g1"}])
        record_team = {"team_name": "TeamA", "date": None}
        record_opp  = {"team_name": "TeamB", "date": None}
        with patch(
            "services.live_history_adapter.normalize_feb_match",
            return_value=[record_team, record_opp],
        ):
            result = adapter.get_team_history("FEB_LF2_Temporada_20252026", "TeamA", is_fbcyl=False)
        assert result == [record_team]

    def test_sorted_by_date(self):
        from datetime import datetime
        adapter = self._adapter([{"_id": "g1"}, {"_id": "g2"}])
        d1 = datetime(2025, 1, 10)
        d2 = datetime(2025, 1, 20)
        records = [{"team_name": "TeamA", "date": d2}, {"team_name": "TeamA", "date": d1}]
        call_count = {"n": 0}

        def fake_normalize(doc, **kwargs):
            r = records[call_count["n"]]
            call_count["n"] += 1
            return [r]

        with patch("services.live_history_adapter.normalize_feb_match", side_effect=fake_normalize):
            result = adapter.get_team_history("FEB_LF2_Temporada_20252026", "TeamA", is_fbcyl=False)
        assert result[0]["date"] == d1
        assert result[1]["date"] == d2
