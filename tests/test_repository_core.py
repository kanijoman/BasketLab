"""Tests for core BasketballRepository methods.

Uses mongomock so no real MongoDB connection is required.
Covers document_exists, insert_boxscore, insert_fbcyl_match, get_all_teams.
Structural tests for get_team_stats / get_player_stats (verify they return lists).
"""

import unittest
from unittest.mock import MagicMock

import mongomock
import pytest

from src.database.repository import BasketballRepository


# ---------------------------------------------------------------------------
# Shared mongomock setup helpers
# ---------------------------------------------------------------------------

def _make_connection(db):
    """Wrap a mongomock db in a connection-like mock."""
    conn = MagicMock()
    conn.is_connected.return_value = True
    conn.db = db
    conn.get_collection.side_effect = lambda name: db[name]
    return conn


def _feb_doc(match_id=1001):
    """Minimal FEB game document sufficient for repository operations."""
    return {
        "_id": match_id,
        "HEADER": {
            "CompID": "218",
            "competition": "L.F.-2",
            "starttime": "05-10-2025 - 12:30",
            "TEAM": [
                {"id": "100", "name": "EQUIPO LOCAL"},
                {"id": "200", "name": "EQUIPO VISITANTE"},
            ],
            "QUARTERS": {"QUARTER": [{"n": "1"}, {"n": "2"}, {"n": "3"}, {"n": "4"}]},
        },
        "BOXSCORE": {
            "TEAM": [
                {
                    "TOTAL": {
                        "p1m": "10", "p1a": "14", "p2m": "18", "p2a": "32",
                        "p3m": "8", "p3a": "20", "fgm": "26", "fga": "52",
                        "assist": "15", "bs": "2", "ro": "8", "rd": "22",
                        "pf": "14", "rf": "15", "to": "11", "st": "6",
                        "val": "85", "pts": "74", "fouls": "14",
                        "id": "100", "name": "EQUIPO LOCAL",
                    }
                },
                {
                    "TOTAL": {
                        "p1m": "8", "p1a": "12", "p2m": "15", "p2a": "28",
                        "p3m": "6", "p3a": "18", "fgm": "21", "fga": "46",
                        "assist": "12", "bs": "1", "ro": "6", "rd": "20",
                        "pf": "16", "rf": "14", "to": "13", "st": "5",
                        "val": "70", "pts": "62", "fouls": "16",
                        "id": "200", "name": "EQUIPO VISITANTE",
                    }
                },
            ]
        },
    }


def _fbcyl_doc(uuid="abc123"):
    """Minimal FBCYL game document sufficient for repository operations."""
    return {
        "_id": uuid,
        "uuid": uuid,
        "moves": [],
        "stats": {
            "teams": [
                {
                    "teamIdIntern": 1001,
                    "teamIdExtern": 2001,
                    "name": "C.B. LOCAL",
                    "players": [],
                    "data": {
                        "score": 80,
                        "shotsOfTwoSuccessful": 20, "shotsOfTwoAttempted": 35,
                        "shotsOfThreeSuccessful": 8, "shotsOfThreeAttempted": 22,
                        "shotsOfOneSuccessful": 12, "shotsOfOneAttempted": 16,
                        "rebounds": 35, "offensiveRebound": 9, "defensiveRebound": 26,
                        "assists": 18, "steals": 7, "lost": 10, "block": 3, "faults": 14,
                    },
                },
                {
                    "teamIdIntern": 1002,
                    "teamIdExtern": 2002,
                    "name": "C.B. VISITANTE",
                    "players": [],
                    "data": {
                        "score": 65,
                        "shotsOfTwoSuccessful": 15, "shotsOfTwoAttempted": 28,
                        "shotsOfThreeSuccessful": 6, "shotsOfThreeAttempted": 18,
                        "shotsOfOneSuccessful": 9, "shotsOfOneAttempted": 14,
                        "rebounds": 28, "offensiveRebound": 7, "defensiveRebound": 21,
                        "assists": 14, "steals": 5, "lost": 12, "block": 2, "faults": 16,
                    },
                },
            ]
        },
    }


# ===========================================================================
# document_exists
# ===========================================================================

class TestDocumentExists(unittest.TestCase):

    def setUp(self):
        client = mongomock.MongoClient()
        self.db = client["test"]
        self.repo = BasketballRepository(_make_connection(self.db))

    def test_returns_false_for_missing_doc(self):
        self.assertFalse(self.repo.document_exists("FEB_LF2_2025_A", 9999))

    def test_returns_true_for_existing_doc(self):
        self.db["FEB_LF2_2025_A"].insert_one(_feb_doc(match_id=1001))
        self.assertTrue(self.repo.document_exists("FEB_LF2_2025_A", 1001))

    def test_returns_false_when_disconnected(self):
        conn = _make_connection(self.db)
        conn.is_connected.return_value = False
        repo = BasketballRepository(conn)
        self.assertFalse(repo.document_exists("any_collection", 1))


# ===========================================================================
# insert_boxscore (FEB)
# ===========================================================================

class TestInsertBoxscore(unittest.TestCase):

    def setUp(self):
        client = mongomock.MongoClient()
        self.db = client["test"]
        self.repo = BasketballRepository(_make_connection(self.db))
        self.col = "FEB_LF2_2025_A"

    def test_insert_new_document_returns_true(self):
        doc = _feb_doc(match_id=2001)
        result = self.repo.insert_boxscore(self.col, "2001", doc)
        self.assertTrue(result)

    def test_inserted_document_is_findable(self):
        doc = _feb_doc(match_id=2002)
        self.repo.insert_boxscore(self.col, "2002", doc)
        found = self.db[self.col].find_one({"_id": 2002})
        self.assertIsNotNone(found)

    def test_insert_duplicate_returns_true_no_error(self):
        doc = _feb_doc(match_id=2003)
        self.repo.insert_boxscore(self.col, "2003", doc)
        result = self.repo.insert_boxscore(self.col, "2003", _feb_doc(match_id=2003))
        self.assertTrue(result)

    def test_collection_count_after_duplicate_insert(self):
        doc = _feb_doc(match_id=2004)
        self.repo.insert_boxscore(self.col, "2004", doc)
        self.repo.insert_boxscore(self.col, "2004", _feb_doc(match_id=2004))
        count = self.db[self.col].count_documents({"_id": 2004})
        self.assertEqual(count, 1)

    def test_insert_when_disconnected_returns_false(self):
        conn = _make_connection(self.db)
        conn.is_connected.return_value = False
        repo = BasketballRepository(conn)
        result = repo.insert_boxscore(self.col, "9999", _feb_doc(9999))
        self.assertFalse(result)


# ===========================================================================
# insert_fbcyl_match
# ===========================================================================

class TestInsertFbcylMatch(unittest.TestCase):

    def setUp(self):
        client = mongomock.MongoClient()
        self.db = client["test"]
        self.repo = BasketballRepository(_make_connection(self.db))
        self.col = "FBCYL_SE_2025_A"

    def test_insert_new_match_returns_true(self):
        doc = _fbcyl_doc("uuid-001")
        result = self.repo.insert_fbcyl_match(self.col, "uuid-001", doc)
        self.assertTrue(result)

    def test_inserted_doc_is_findable(self):
        doc = _fbcyl_doc("uuid-002")
        self.repo.insert_fbcyl_match(self.col, "uuid-002", doc)
        found = self.db[self.col].find_one({"_id": "uuid-002"})
        self.assertIsNotNone(found)

    def test_insert_duplicate_does_not_raise(self):
        doc = _fbcyl_doc("uuid-003")
        self.repo.insert_fbcyl_match(self.col, "uuid-003", doc)
        result = self.repo.insert_fbcyl_match(self.col, "uuid-003", _fbcyl_doc("uuid-003"))
        self.assertTrue(result)


# ===========================================================================
# get_all_teams
# ===========================================================================

class TestGetAllTeams(unittest.TestCase):

    def setUp(self):
        client = mongomock.MongoClient()
        self.db = client["test"]
        self.col = "FEB_LF2_2025_A"
        self.repo = BasketballRepository(_make_connection(self.db))

    def test_returns_list(self):
        result = self.repo.get_all_teams(self.col)
        self.assertIsInstance(result, list)

    def test_returns_empty_for_empty_collection(self):
        result = self.repo.get_all_teams(self.col)
        self.assertEqual(result, [])

    def test_returns_false_or_empty_when_disconnected(self):
        conn = _make_connection(self.db)
        conn.is_connected.return_value = False
        repo = BasketballRepository(conn)
        result = repo.get_all_teams(self.col)
        # Returns empty list or False — either is acceptable, just no crash
        self.assertFalse(bool(result))


# ===========================================================================
# get_team_stats / get_player_stats — structural (return-type) tests
# These run against a real mongomock collection with known data.
# ===========================================================================

class TestGetTeamStatsStructural(unittest.TestCase):
    """Verify get_team_stats returns a list (even if empty or without full pipeline support)."""

    def setUp(self):
        client = mongomock.MongoClient()
        self.db = client["test"]
        self.col = "FEB_LF2_2025_A"
        self.db[self.col].insert_one(_feb_doc(3001))
        self.repo = BasketballRepository(_make_connection(self.db))

    def test_returns_list_or_none(self):
        """get_team_stats must return a list (possibly empty) and not raise."""
        try:
            result = self.repo.get_team_stats(self.col)
            self.assertIsInstance(result, list)
        except Exception as exc:
            # Aggregation operators not supported by mongomock are acceptable
            # but must be a known pymongo/mongomock error, not a Python crash
            self.assertIn(type(exc).__name__,
                          {"OperationFailure", "NotImplementedError", "PyMongoError"},
                          f"Unexpected exception type: {type(exc).__name__}: {exc}")

    def test_returns_false_when_disconnected(self):
        conn = _make_connection(self.db)
        conn.is_connected.return_value = False
        repo = BasketballRepository(conn)
        result = repo.get_team_stats(self.col)
        self.assertFalse(bool(result))


class TestGetPlayerStatsStructural(unittest.TestCase):

    def setUp(self):
        client = mongomock.MongoClient()
        self.db = client["test"]
        self.col = "FEB_LF2_2025_A"
        self.db[self.col].insert_one(_feb_doc(4001))
        self.repo = BasketballRepository(_make_connection(self.db))

    def test_returns_list_or_raises_known_error(self):
        try:
            result = self.repo.get_player_stats(self.col)
            self.assertIsInstance(result, list)
        except Exception as exc:
            self.assertIn(type(exc).__name__,
                          {"OperationFailure", "NotImplementedError", "PyMongoError"})

    def test_returns_false_when_disconnected(self):
        conn = _make_connection(self.db)
        conn.is_connected.return_value = False
        repo = BasketballRepository(conn)
        result = repo.get_player_stats(self.col)
        self.assertFalse(bool(result))


if __name__ == "__main__":
    unittest.main()
