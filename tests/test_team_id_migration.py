"""TDD regression tests: Team ID migration + OOM fix.

RED → GREEN cycle (all tests fail before implementation):
1. test_get_teams_with_ids_*        — repository.get_teams_with_ids() exists + returns {id, name} dicts
2. test_shots_filter_*              — shots._extract_shots_feb() uses HEADER.TEAM.id, not name
3. test_shots_zones_streaming_*     — _stream_zone_counts_feb exists + used by zones endpoint
4. test_weekly_report_no_full_load  — _extract_shots never calls coll.find({}) (OOM regression)
"""

import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# 1. repository.get_teams_with_ids
# ---------------------------------------------------------------------------

class TestGetTeamsWithIds:

    def _repo(self, aggregate_return):
        from src.database.repository import BasketballRepository
        conn = MagicMock()
        conn.is_connected.return_value = True
        mock_coll = MagicMock()
        mock_coll.aggregate.return_value = iter(aggregate_return)
        conn.get_collection.return_value = mock_coll
        return BasketballRepository(conn)

    def test_method_exists_on_repository(self):
        from src.database.repository import BasketballRepository
        assert hasattr(BasketballRepository, "get_teams_with_ids"), (
            "BasketballRepository.get_teams_with_ids() must exist"
        )

    def test_returns_list_of_dicts_with_id_and_name(self):
        repo = self._repo([{"id": "1", "name": "Team A"}, {"id": "2", "name": "Team B"}])
        result = repo.get_teams_with_ids("FEB_LF2_2025_A")
        assert isinstance(result, list)
        assert len(result) == 2
        assert "id" in result[0] and "name" in result[0]
        assert "id" in result[1] and "name" in result[1]

    def test_returns_empty_for_empty_collection(self):
        repo = self._repo([])
        result = repo.get_teams_with_ids("FEB_LF2_2025_A")
        assert result == []

    def test_deduplication_by_id_via_aggregation(self):
        # aggregation already deduplicates — one id → one entry (newest name wins)
        repo = self._repo([{"id": "100", "name": "Nuevo Sponsor Burgos"}])
        result = repo.get_teams_with_ids("FEB_LF2_2025_A")
        ids = [t["id"] for t in result]
        assert ids.count("100") == 1

    def test_returns_empty_when_disconnected(self):
        from src.database.repository import BasketballRepository
        conn = MagicMock()
        conn.is_connected.return_value = False
        repo = BasketballRepository(conn)
        result = repo.get_teams_with_ids("FEB_LF2_2025_A")
        assert result == []

    def test_method_exists_on_db_handler(self):
        """MongoDBHandler wrapper must expose get_teams_with_ids()."""
        from src.database import MongoDBHandler
        assert hasattr(MongoDBHandler, "get_teams_with_ids"), (
            "MongoDBHandler.get_teams_with_ids() must exist"
        )


# ---------------------------------------------------------------------------
# 2. team_utils.resolve_team_by_id
# ---------------------------------------------------------------------------

class TestResolveTeamById:

    def test_function_exists(self):
        from src.utils.team_utils import resolve_team_by_id
        assert callable(resolve_team_by_id)

    def test_feb_returns_id_and_name(self):
        from src.utils.team_utils import resolve_team_by_id
        mock_coll = MagicMock()
        mock_coll.find_one.return_value = {
            "HEADER": {"TEAM": [
                {"id": "42", "name": "San Pablo Burgos"},
                {"id": "99", "name": "Otro Equipo"},
            ]}
        }
        result = resolve_team_by_id(mock_coll, "42", is_fbcyl=False)
        assert result is not None
        assert result["id"] == "42"
        assert result["name"] == "San Pablo Burgos"

    def test_feb_returns_none_when_not_found(self):
        from src.utils.team_utils import resolve_team_by_id
        mock_coll = MagicMock()
        mock_coll.find_one.return_value = None
        result = resolve_team_by_id(mock_coll, "999", is_fbcyl=False)
        assert result is None

    def test_fbcyl_returns_id_and_name(self):
        from src.utils.team_utils import resolve_team_by_id
        mock_coll = MagicMock()
        mock_coll.find_one.return_value = {
            "stats": {"teams": [
                {"teamIdExtern": 2001, "name": "C.B. LOCAL"},
                {"teamIdExtern": 2002, "name": "C.B. VISITANTE"},
            ]}
        }
        result = resolve_team_by_id(mock_coll, "2001", is_fbcyl=True)
        assert result is not None
        assert result["id"] == "2001"
        assert result["name"] == "C.B. LOCAL"


# ---------------------------------------------------------------------------
# 3. shots._extract_shots_feb uses HEADER.TEAM.id (OOM fix)
# ---------------------------------------------------------------------------

class TestShotsFilterByTeamId:

    def _coll(self, docs=None):
        coll = MagicMock()
        coll.find.return_value = iter(docs or [])
        return coll

    def test_team_id_included_in_mongo_query(self):
        from src.api.routers.shots import _extract_shots_feb
        coll = self._coll()
        _extract_shots_feb(coll, team_id="42", player_filter=None)
        query = coll.find.call_args[0][0]
        assert "HEADER.TEAM.id" in query, "HEADER.TEAM.id must be in MongoDB query"
        assert query["HEADER.TEAM.id"] == "42"

    def test_team_name_never_used_as_mongo_filter(self):
        """Regression: HEADER.TEAM.name must NOT appear in the MongoDB query."""
        from src.api.routers.shots import _extract_shots_feb
        coll = self._coll()
        _extract_shots_feb(coll, team_id="42", player_filter=None)
        query = coll.find.call_args[0][0]
        assert "HEADER.TEAM.name" not in query, (
            "HEADER.TEAM.name must not be used as MongoDB filter — OOM regression"
        )

    def test_no_team_id_excludes_team_filter_from_query(self):
        from src.api.routers.shots import _extract_shots_feb
        coll = self._coll()
        _extract_shots_feb(coll, team_id=None, player_filter=None)
        query = coll.find.call_args[0][0]
        assert "HEADER.TEAM.id" not in query
        assert "HEADER.TEAM.name" not in query

    def test_old_team_filter_param_removed(self):
        """Signature must use team_id, not team_filter."""
        import inspect
        from src.api.routers.shots import _extract_shots_feb
        params = inspect.signature(_extract_shots_feb).parameters
        assert "team_id" in params, "_extract_shots_feb must have team_id param"
        assert "team_filter" not in params, "Old team_filter param must be removed"


# ---------------------------------------------------------------------------
# 4. shots._stream_zone_counts_feb exists (O(1) memory for zones endpoint)
# ---------------------------------------------------------------------------

class TestStreamingZoneCounts:

    def test_function_exists(self):
        from src.api.routers import shots
        assert hasattr(shots, "_stream_zone_counts_feb"), (
            "_stream_zone_counts_feb must exist for memory-efficient zones endpoint"
        )

    def test_returns_zone_accum_dict_structure(self):
        from src.api.routers.shots import _stream_zone_counts_feb
        coll = MagicMock()
        coll.find.return_value = iter([])
        result = _stream_zone_counts_feb(coll, team_id="1", player_filter=None)
        assert isinstance(result, dict)
        assert "restricted_area" in result
        assert "paint" in result
        assert "corner_left" in result
        for zone, counts in result.items():
            assert "fga" in counts
            assert "fgm" in counts

    def test_zones_endpoint_uses_streaming_not_all_shots_list(self):
        """GET /shots/{col} must call _stream_zone_counts_feb, not _extract_shots_feb."""
        from src.api.routers import shots as shots_module
        from src.api.app import app
        from src.api.deps import get_db
        from fastapi.testclient import TestClient

        mock_db = MagicMock()
        mock_coll = MagicMock()
        mock_coll.find.return_value = iter([])
        mock_db.connection.get_collection.return_value = mock_coll

        empty_accum = {z: {"fga": 0, "fgm": 0} for z in shots_module._ZONE_META}

        with patch.object(shots_module, "_extract_shots_feb") as mock_extract, \
             patch.object(shots_module, "_stream_zone_counts_feb",
                          return_value=empty_accum) as mock_stream:
            app.dependency_overrides[get_db] = lambda: mock_db
            try:
                client = TestClient(app)
                r = client.get("/api/v1/shots/FEB_LF2_2025?team_id=42")
                assert r.status_code == 200
            finally:
                app.dependency_overrides.clear()

        mock_stream.assert_called_once()
        mock_extract.assert_not_called()


# ---------------------------------------------------------------------------
# 5. weekly_report._extract_shots must NOT call coll.find({}) (OOM regression)
# ---------------------------------------------------------------------------

class TestWeeklyReportNoFullCollectionLoad:

    def _db(self, docs=None):
        db = MagicMock()
        mock_coll = MagicMock()
        mock_coll.find.return_value = iter(docs or [])
        mock_coll.find_one.return_value = None
        db.connection.get_collection.return_value = mock_coll
        return db, mock_coll

    def test_feb_never_calls_find_without_filter(self):
        """OOM regression: find({}) must not be called for FEB shots."""
        from src.services.weekly_report_service import _extract_shots
        db, mock_coll = self._db()
        _extract_shots(db, "FEB_LF2_2025_A", "42")
        for c in mock_coll.find.call_args_list:
            query = c[0][0] if c[0] else {}
            assert query != {}, (
                "coll.find({}) called with no filter — OOM regression (FEB)"
            )

    def test_fbcyl_never_calls_find_without_filter(self):
        """OOM regression: find({}) must not be called for FBCYL shots."""
        from src.services.weekly_report_service import _extract_shots
        db, mock_coll = self._db()
        _extract_shots(db, "FBCYL_SE_2025_A", "2001")
        for c in mock_coll.find.call_args_list:
            query = c[0][0] if c[0] else {}
            assert query != {}, (
                "coll.find({}) called with no filter — OOM regression (FBCYL)"
            )
