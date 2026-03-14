"""Tests for the FastAPI application layer.

These tests exercise the HTTP routes using FastAPI's built-in test client
and mock the database dependency so no real MongoDB connection is needed.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# App import + dependency override
# ---------------------------------------------------------------------------

from src.api.app import app
from src.api.deps import get_db

# All routes live under /api/v1/ after the versioning migration.
V1 = "/api/v1"


def _mock_db(
    team_stats=None,
    opponent_stats=None,
    player_stats=None,
    all_teams=None,
    connected=True,
):
    handler = MagicMock()
    handler.is_connected.return_value = connected
    handler.get_team_stats.return_value = team_stats or []
    handler.get_opponent_stats.return_value = opponent_stats or []
    handler.get_player_stats.return_value = player_stats or []
    handler.get_all_teams.return_value = all_teams or []
    handler.get_aggregated_team_stats.return_value = {}
    handler.get_aggregated_opponent_stats.return_value = {}
    handler.get_league_stats.return_value = {}
    handler.get_player_in_out_stats.return_value = {"in": {}, "out": {}}
    handler.get_two_players_together_stats.return_value = {}
    handler.get_lineup_analysis.return_value = []
    mock_collection = MagicMock()
    mock_collection.count_documents.return_value = 1
    handler.connection.get_collection.return_value = mock_collection
    return handler


@pytest.fixture
def client():
    """Test client with a mocked database connection."""
    mock = _mock_db(all_teams=["TeamA", "TeamB"])
    app.dependency_overrides[get_db] = lambda: mock
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def disconnected_client():
    """Test client with a disconnected database."""
    from fastapi import HTTPException as _HTTPException

    def _disconnected_get_db():
        mock = _mock_db(connected=False)
        if not mock.is_connected():
            raise _HTTPException(status_code=503, detail="Database not connected.")
        return mock  # pragma: no cover

    app.dependency_overrides[get_db] = _disconnected_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_root_returns_ok(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_root_returns_app_name(self, client):
        r = client.get("/")
        assert "MetricsForAll" in r.json()["app"]


# ---------------------------------------------------------------------------
# Collections router
# ---------------------------------------------------------------------------

class TestCollectionsRouter:
    def test_list_teams_returns_200(self, client):
        r = client.get(f"{V1}/collections/?collection=FEB_LF2_2025_A")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_teams_contains_expected_teams(self, client):
        r = client.get(f"{V1}/collections/?collection=FEB_LF2_2025_A")
        assert "TeamA" in r.json()

    def test_list_teams_returns_404_when_empty(self):
        mock = _mock_db(all_teams=[], connected=True)
        # Make count_documents return 0 to trigger 404 (collection not found)
        mock.connection.get_collection.return_value.count_documents.return_value = 0
        app.dependency_overrides[get_db] = lambda: mock
        c = TestClient(app)
        try:
            r = c.get(f"{V1}/collections/?collection=NONEXISTENT")
            assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_detect_format_fbcyl(self, client):
        r = client.get(f"{V1}/collections/format?collection=FBCYL_SE_2025_A")
        assert r.status_code == 200
        assert r.json()["is_fbcyl"] is True

    def test_detect_format_feb(self, client):
        r = client.get(f"{V1}/collections/format?collection=FEB_LF2_2025_A")
        assert r.json()["is_fbcyl"] is False

    def test_resolve_name_returns_collection_name(self, client):
        r = client.get(f"{V1}/collections/resolve?competition=FEB&season=LF2_2025&group=A")
        assert r.status_code == 200
        assert "collection_name" in r.json()
        assert "FEB" in r.json()["collection_name"]


# ---------------------------------------------------------------------------
# Teams router
# ---------------------------------------------------------------------------

class TestTeamsRouter:
    def test_get_team_stats_returns_200(self, client):
        r = client.get(f"{V1}/teams/FEB_LF2_2025_A")
        assert r.status_code == 200
        data = r.json()
        assert "team_stats" in data
        assert "opponent_stats" in data

    def test_get_team_stats_with_venue_filter(self, client):
        r = client.get(f"{V1}/teams/FEB_LF2_2025_A?venue=home")
        assert r.status_code == 200

    def test_get_team_stats_with_result_filter(self, client):
        r = client.get(f"{V1}/teams/FEB_LF2_2025_A?result=won")
        assert r.status_code == 200

    def test_quartiles_returns_200(self, client):
        with patch("src.services.team_stats_service.TeamStatsAggregator") as MockAgg:
            MockAgg.return_value.calculate_league_quartiles.return_value = {}
            r = client.get(f"{V1}/teams/FEB_LF2_2025_A/quartiles")
        assert r.status_code == 200

    def test_list_teams_endpoint_returns_list(self, client):
        r = client.get(f"{V1}/teams/FEB_LF2_2025_A/teams")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# Players router
# ---------------------------------------------------------------------------

class TestPlayersRouter:
    def test_get_player_stats_returns_200(self, client):
        r = client.get(f"{V1}/players/FEB_LF2_2025_A")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_inout_analysis_returns_200(self, client):
        r = client.get(f"{V1}/players/FEB_LF2_2025_A/inout/12345")
        assert r.status_code == 200

    def test_together_analysis_returns_200(self, client):
        r = client.get(f"{V1}/players/FEB_LF2_2025_A/together/12/34")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Lineups router
# ---------------------------------------------------------------------------

class TestLineupsRouter:
    def test_lineup_analysis_returns_200(self, client):
        r = client.get(f"{V1}/lineups/FEB_LF2_2025_A/123?team_name=Alpha")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_lineup_size_validation(self, client):
        # size=1 is below minimum (2), should fail with 422
        r = client.get(f"{V1}/lineups/FEB_LF2_2025_A/123?team_name=Alpha&size=1")
        assert r.status_code == 422

    def test_lineup_size_too_large(self, client):
        # size=6 is above maximum (5), should fail with 422
        r = client.get(f"{V1}/lineups/FEB_LF2_2025_A/123?team_name=Alpha&size=6")
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Database disconnected
# ---------------------------------------------------------------------------

class TestDbDisconnected:
    def test_teams_returns_503_when_disconnected(self, disconnected_client):
        r = disconnected_client.get(f"{V1}/teams/FEB_LF2_2025_A")
        assert r.status_code == 503

    def test_players_returns_503_when_disconnected(self, disconnected_client):
        r = disconnected_client.get(f"{V1}/players/FEB_LF2_2025_A")
        assert r.status_code == 503

    def test_lineups_returns_503_when_disconnected(self, disconnected_client):
        r = disconnected_client.get(f"{V1}/lineups/FEB_LF2_2025_A/123?team_name=T")
        assert r.status_code == 503
