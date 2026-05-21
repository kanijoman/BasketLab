"""Regression tests for get_games_for_team and get_games_with_playbyplay.

These tests document the current behaviour and must pass both before and after
moving the methods to GamesRepositoryMixin (repository_games.py).
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from database.repository import BasketballRepository


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _make_connection(docs=None, aggregate_result=None, connected=True):
    conn = MagicMock()
    conn.is_connected.return_value = connected
    col = MagicMock()
    col.find.return_value = list(docs or [])
    col.aggregate.return_value = iter(aggregate_result or [])
    conn.get_collection.return_value = col
    conn.ensure_indexes = MagicMock()
    return conn


def _repo(docs=None, aggregate_result=None, connected=True):
    return BasketballRepository(_make_connection(docs, aggregate_result, connected))


# ---------------------------------------------------------------------------
# get_games_for_team — FEB
# ---------------------------------------------------------------------------

class TestGetGamesForTeamFEB:
    _COL = "FEB_LF2_2025_A"
    _TID = "team_001"

    def test_disconnected_returns_empty(self):
        assert _repo(connected=False).get_games_for_team(self._COL, self._TID) == []

    def test_find_uses_header_team_id_filter(self):
        repo = _repo(docs=[])
        repo.get_games_for_team(self._COL, self._TID)
        col = repo.connection.get_collection.return_value
        match_filter = col.find.call_args[0][0]
        assert match_filter.get("HEADER.TEAM.id") == self._TID

    def test_playbyplay_filter_added_when_requested(self):
        repo = _repo(docs=[])
        repo.get_games_for_team(self._COL, self._TID, only_with_playbyplay=True)
        col = repo.connection.get_collection.return_value
        match_filter = col.find.call_args[0][0]
        assert "PLAYBYPLAY.LINES" in match_filter

    def test_no_playbyplay_filter_by_default(self):
        repo = _repo(docs=[])
        repo.get_games_for_team(self._COL, self._TID)
        col = repo.connection.get_collection.return_value
        match_filter = col.find.call_args[0][0]
        assert "PLAYBYPLAY.LINES" not in match_filter

    def test_returns_list_of_docs(self):
        docs = [{"_id": 1}, {"_id": 2}]
        result = _repo(docs=docs).get_games_for_team(self._COL, self._TID)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# get_games_for_team — FBCYL
# ---------------------------------------------------------------------------

class TestGetGamesForTeamFBCYL:
    _COL = "FBCYL_2025_A"
    _TID = "123"

    def test_fbcyl_uses_or_filter(self):
        repo = _repo(docs=[])
        repo.get_games_for_team(self._COL, self._TID)
        col = repo.connection.get_collection.return_value
        match_filter = col.find.call_args[0][0]
        assert "$or" in match_filter

    def test_fbcyl_or_filter_includes_teamidextern(self):
        repo = _repo(docs=[])
        repo.get_games_for_team(self._COL, self._TID)
        col = repo.connection.get_collection.return_value
        match_filter = col.find.call_args[0][0]
        keys = [list(c.keys())[0] for c in match_filter["$or"]]
        assert any("teamIdExtern" in k for k in keys)

    def test_fbcyl_playbyplay_filter_uses_moves(self):
        repo = _repo(docs=[])
        repo.get_games_for_team(self._COL, self._TID, only_with_playbyplay=True)
        col = repo.connection.get_collection.return_value
        match_filter = col.find.call_args[0][0]
        assert "moves" in match_filter

    def test_fbcyl_no_playbyplay_filter_by_default(self):
        repo = _repo(docs=[])
        repo.get_games_for_team(self._COL, self._TID)
        col = repo.connection.get_collection.return_value
        match_filter = col.find.call_args[0][0]
        assert "moves" not in match_filter


# ---------------------------------------------------------------------------
# get_games_with_playbyplay — FEB
# ---------------------------------------------------------------------------

class TestGetGamesWithPlaybyplayFEB:
    _COL = "FEB_LF2_2025_A"

    def test_disconnected_returns_empty(self):
        assert _repo(connected=False).get_games_with_playbyplay(self._COL) == []

    def test_no_date_filter_uses_find_with_playbyplay_lines(self):
        repo = _repo(docs=[{"_id": 1, "PLAYBYPLAY": {"LINES": []}}])
        repo.get_games_with_playbyplay(self._COL)
        col = repo.connection.get_collection.return_value
        assert col.find.called
        match_filter = col.find.call_args[0][0]
        assert "PLAYBYPLAY.LINES" in match_filter

    def test_with_date_filter_uses_aggregate(self):
        repo = _repo(aggregate_result=[{"_id": 1}])
        date_f = {"$gte": datetime(2025, 1, 1)}
        repo.get_games_with_playbyplay(self._COL, date_filter=date_f)
        col = repo.connection.get_collection.return_value
        assert col.aggregate.called


# ---------------------------------------------------------------------------
# get_games_with_playbyplay — FBCYL
# ---------------------------------------------------------------------------

class TestGetGamesWithPlaybyplayFBCYL:
    _COL = "FBCYL_2025_A"

    def test_fbcyl_no_date_filter_uses_find_with_moves(self):
        repo = _repo(docs=[{"_id": "abc", "moves": []}])
        repo.get_games_with_playbyplay(self._COL)
        col = repo.connection.get_collection.return_value
        assert col.find.called
        match_filter = col.find.call_args[0][0]
        assert "moves" in match_filter

    def test_fbcyl_with_date_filter_uses_aggregate(self):
        repo = _repo(aggregate_result=[{"_id": "abc"}])
        date_f = {"$gte": datetime(2025, 1, 1)}
        repo.get_games_with_playbyplay(self._COL, date_filter=date_f)
        col = repo.connection.get_collection.return_value
        assert col.aggregate.called


# ---------------------------------------------------------------------------
# get_last_match
# ---------------------------------------------------------------------------

class TestGetLastMatch:
    _COL = "FEB_LF2_2025_A"

    def test_disconnected_returns_empty_dict(self):
        assert _repo(connected=False).get_last_match(self._COL, "TeamA") == {}

    def test_feb_uses_aggregate(self):
        repo = _repo(aggregate_result=[{"_id": 1}])
        result = repo.get_last_match(self._COL, "TeamA")
        col = repo.connection.get_collection.return_value
        assert col.aggregate.called
        assert result == {"_id": 1}

    def test_no_match_returns_empty_dict(self):
        repo = _repo(aggregate_result=[])
        result = repo.get_last_match(self._COL, "TeamA")
        assert result == {}

    def test_fbcyl_uses_aggregate(self):
        repo = _repo(aggregate_result=[{"_id": "abc"}])
        result = repo.get_last_match("FBCYL_2025_A", "TeamA")
        col = repo.connection.get_collection.return_value
        assert col.aggregate.called
        assert result == {"_id": "abc"}
