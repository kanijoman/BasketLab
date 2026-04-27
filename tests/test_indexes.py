"""Tests for IndexManager — MongoDB index creation and management.

Covers:
- ensure_indexes() FEB collection: creates expected indexes
- ensure_indexes() FBCYL collection: creates expected indexes
- ensure_indexes() when not connected: returns False
- list_indexes() when connected: returns list
- list_indexes() when not connected: returns []
- drop_index() behavior
"""

import pytest
from unittest.mock import MagicMock

import mongomock

from src.database.indexes import IndexManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_connection(connected: bool = True, collection_name: str = "FEB_LF2_2025_A"):
    """Return a mock connection wrapping a mongomock collection."""
    client = mongomock.MongoClient()
    db = client["test_db"]
    coll = db[collection_name]

    conn = MagicMock()
    conn.is_connected.return_value = connected
    conn.get_collection.side_effect = lambda name: db[name]
    return conn, coll


# ---------------------------------------------------------------------------
# ensure_indexes
# ---------------------------------------------------------------------------

class TestEnsureIndexes:
    def test_feb_collection_returns_true(self):
        conn, _ = _make_connection(collection_name="FEB_LF2_2025_A")
        mgr = IndexManager(conn)
        assert mgr.ensure_indexes("FEB_LF2_2025_A") is True

    def test_fbcyl_collection_returns_true(self):
        conn, _ = _make_connection(collection_name="FBCYL_SE_2025")
        mgr = IndexManager(conn)
        assert mgr.ensure_indexes("FBCYL_SE_2025") is True

    def test_returns_false_when_not_connected(self):
        conn, _ = _make_connection(connected=False)
        mgr = IndexManager(conn)
        assert mgr.ensure_indexes("FEB_LF2_2025_A") is False

    def test_feb_indexes_are_created(self):
        conn, coll = _make_connection(collection_name="FEB_LF2_2025_A")
        mgr = IndexManager(conn)
        mgr.ensure_indexes("FEB_LF2_2025_A")
        index_names = {idx["name"] for idx in coll.list_indexes()}
        # Default _id index is always present; at least one custom index should be too
        assert len(index_names) >= 2

    def test_fbcyl_indexes_are_created(self):
        conn, coll = _make_connection(collection_name="FBCYL_SE_2025")
        mgr = IndexManager(conn)
        mgr.ensure_indexes("FBCYL_SE_2025")
        index_names = {idx["name"] for idx in coll.list_indexes()}
        assert len(index_names) >= 2

    def test_exception_during_creation_returns_false(self):
        conn = MagicMock()
        conn.is_connected.return_value = True
        conn.get_collection.side_effect = RuntimeError("DB error")
        mgr = IndexManager(conn)
        result = mgr.ensure_indexes("FEB_LF2_2025_A")
        assert result is False


# ---------------------------------------------------------------------------
# list_indexes
# ---------------------------------------------------------------------------

class TestListIndexes:
    def test_returns_list_when_connected(self):
        conn, _ = _make_connection(collection_name="FEB_LF2_2025_A")
        mgr = IndexManager(conn)
        mgr.ensure_indexes("FEB_LF2_2025_A")   # create indexes first
        indexes = mgr.list_indexes("FEB_LF2_2025_A")
        assert isinstance(indexes, list)
        assert len(indexes) >= 1

    def test_returns_empty_list_when_not_connected(self):
        conn = MagicMock()
        conn.is_connected.return_value = False
        mgr = IndexManager(conn)
        assert mgr.list_indexes("FEB_LF2_2025_A") == []

    def test_returns_empty_list_on_exception(self):
        conn = MagicMock()
        conn.is_connected.return_value = True
        conn.get_collection.side_effect = RuntimeError("DB error")
        mgr = IndexManager(conn)
        assert mgr.list_indexes("FEB_LF2_2025_A") == []


# ---------------------------------------------------------------------------
# drop_index
# ---------------------------------------------------------------------------

class TestDropIndex:
    def test_drop_existing_index_returns_true(self):
        conn, coll = _make_connection(collection_name="FEB_LF2_2025_A")
        mgr = IndexManager(conn)
        mgr.ensure_indexes("FEB_LF2_2025_A")
        # Drop one of the created indexes (playbyplay_lines_1)
        result = mgr.drop_index("FEB_LF2_2025_A", "playbyplay_lines_1")
        assert result is True

    def test_drop_nonexistent_index_returns_false(self):
        conn, _ = _make_connection(collection_name="FEB_LF2_2025_A")
        mgr = IndexManager(conn)
        result = mgr.drop_index("FEB_LF2_2025_A", "does_not_exist")
        assert result is False

    def test_drop_returns_false_when_not_connected(self):
        conn = MagicMock()
        conn.is_connected.return_value = False
        mgr = IndexManager(conn)
        assert mgr.drop_index("FEB_LF2_2025_A", "player_id_1") is False
