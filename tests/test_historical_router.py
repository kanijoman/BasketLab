"""Tests for the historical router — the query endpoints (the ingestion jobs were retired, issue #724).

Covers:
- GET /historical/summary → 200 list
- GET /historical/seasons → 200 list
- GET /historical/teams → 200 list
- GET /historical/teams?season=2024-25 → 200 list (filtered)
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db


V1 = "/api/v1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    mock_db = MagicMock()
    mock_db.is_connected.return_value = True
    app.dependency_overrides[get_db] = lambda: mock_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /historical/summary
# ---------------------------------------------------------------------------

class TestHistoricalSummary:
    def test_returns_200(self, client):
        with patch("src.database.historical_repository.HistoricalRepository") as MockRepo:
            MockRepo.return_value.get_summary.return_value = []
            resp = client.get(f"{V1}/historical/summary")
        assert resp.status_code == 200

    def test_returns_list(self, client):
        sample = [{"league": "FEB", "competition": "LF2", "season": "2024-25",
                   "group": "A", "match_count": 20}]
        with patch("src.database.historical_repository.HistoricalRepository") as MockRepo:
            MockRepo.return_value.get_summary.return_value = sample
            resp = client.get(f"{V1}/historical/summary")
        assert isinstance(resp.json(), list)
        assert len(resp.json()) == 1

    def test_returns_expected_fields(self, client):
        sample = [{"league": "FEB", "competition": "LF2", "season": "2024-25",
                   "group": "A", "match_count": 20}]
        with patch("src.database.historical_repository.HistoricalRepository") as MockRepo:
            MockRepo.return_value.get_summary.return_value = sample
            resp = client.get(f"{V1}/historical/summary")
        item = resp.json()[0]
        assert item["league"] == "FEB"
        assert item["match_count"] == 20


# ---------------------------------------------------------------------------
# GET /historical/seasons
# ---------------------------------------------------------------------------

class TestHistoricalSeasons:
    def test_returns_200(self, client):
        with patch("src.database.historical_repository.HistoricalRepository") as MockRepo:
            MockRepo.return_value.list_seasons.return_value = ["2024-25", "2023-24"]
            resp = client.get(f"{V1}/historical/seasons")
        assert resp.status_code == 200

    def test_returns_list_of_strings(self, client):
        with patch("src.database.historical_repository.HistoricalRepository") as MockRepo:
            MockRepo.return_value.list_seasons.return_value = ["2024-25"]
            resp = client.get(f"{V1}/historical/seasons")
        body = resp.json()
        assert isinstance(body, list)
        assert body[0] == "2024-25"

    def test_empty_db_returns_empty_list(self, client):
        with patch("src.database.historical_repository.HistoricalRepository") as MockRepo:
            MockRepo.return_value.list_seasons.return_value = []
            resp = client.get(f"{V1}/historical/seasons")
        assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /historical/teams
# ---------------------------------------------------------------------------

class TestHistoricalTeams:
    def test_returns_200(self, client):
        with patch("src.database.historical_repository.HistoricalRepository") as MockRepo:
            MockRepo.return_value.list_teams.return_value = []
            resp = client.get(f"{V1}/historical/teams")
        assert resp.status_code == 200

    def test_returns_list_of_dicts(self, client):
        sample = [{"team_id": "t1", "team_name": "Alpha FC"}]
        with patch("src.database.historical_repository.HistoricalRepository") as MockRepo:
            MockRepo.return_value.list_teams.return_value = sample
            resp = client.get(f"{V1}/historical/teams")
        assert resp.json()[0]["team_name"] == "Alpha FC"

    def test_season_filter_passed_to_repo(self, client):
        with patch("src.database.historical_repository.HistoricalRepository") as MockRepo:
            MockRepo.return_value.list_teams.return_value = []
            resp = client.get(f"{V1}/historical/teams?season=2024-25")
        assert resp.status_code == 200
        MockRepo.return_value.list_teams.assert_called_once_with("2024-25")

    def test_no_season_passes_none_to_repo(self, client):
        with patch("src.database.historical_repository.HistoricalRepository") as MockRepo:
            MockRepo.return_value.list_teams.return_value = []
            resp = client.get(f"{V1}/historical/teams")
        MockRepo.return_value.list_teams.assert_called_once_with(None)
