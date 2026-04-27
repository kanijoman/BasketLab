"""Tests for the historical router — ingestion jobs and query endpoints.

Covers:
- POST /historical/ingest with FEB → 200 + job_id
- POST /historical/ingest with FBCYL → 200 + job_id
- POST /historical/ingest with invalid league → 400
- POST /historical/ingest with FEB but missing feb_seasons → 422
- POST /historical/ingest with FBCYL but missing fbcyl_seasons → 422
- GET /historical/progress/{job_id} → returns job state dict
- GET /historical/progress/unknown → 404
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
from src.api.routers.historical import HISTORICAL_JOBS


V1 = "/api/v1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_historical_jobs():
    """Isolate the in-process job store between tests."""
    HISTORICAL_JOBS.clear()
    yield
    HISTORICAL_JOBS.clear()


@pytest.fixture
def client():
    mock_db = MagicMock()
    mock_db.is_connected.return_value = True
    app.dependency_overrides[get_db] = lambda: mock_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ── request payloads ──────────────────────────────────────────────────────────

_FEB_PAYLOAD = {
    "league": "FEB",
    "feb_seasons": [
        {
            "competition_url": "https://baloncestoenvivo.feb.es/competition/1",
            "season_value": "2025",
            "group_value": "A",
            "year": "2025",
            "competition_label": "LF2",
            "season_label": "LF2 2025",
            "group_label": "A",
            "normalized_season": "2024-25",
        }
    ],
}

_FBCYL_PAYLOAD = {
    "league": "FBCYL",
    "fbcyl_seasons": [
        {
            "competition_id": "12",
            "season": "2025",
            "gender": "M",
            "territory": "0",
            "category": "Senior",
            "competition_label": "SeniorA",
            "normalized_season": "2024-25",
        }
    ],
}


# ---------------------------------------------------------------------------
# POST /historical/ingest
# ---------------------------------------------------------------------------

class TestStartHistoricalIngest:
    def test_feb_returns_job_id(self, client):
        resp = client.post(f"{V1}/historical/ingest", json=_FEB_PAYLOAD)
        assert resp.status_code == 200
        body = resp.json()
        assert "job_id" in body
        assert isinstance(body["job_id"], str)

    def test_fbcyl_returns_job_id(self, client):
        resp = client.post(f"{V1}/historical/ingest", json=_FBCYL_PAYLOAD)
        assert resp.status_code == 200
        assert "job_id" in resp.json()

    def test_invalid_league_returns_400(self, client):
        payload = {"league": "ACB", "feb_seasons": []}
        resp = client.post(f"{V1}/historical/ingest", json=payload)
        assert resp.status_code == 400

    def test_feb_missing_feb_seasons_returns_422(self, client):
        payload = {"league": "FEB", "feb_seasons": None}
        resp = client.post(f"{V1}/historical/ingest", json=payload)
        assert resp.status_code == 422

    def test_fbcyl_missing_fbcyl_seasons_returns_422(self, client):
        payload = {"league": "FBCYL", "fbcyl_seasons": None}
        resp = client.post(f"{V1}/historical/ingest", json=payload)
        assert resp.status_code == 422

    def test_feb_job_is_stored(self, client):
        resp = client.post(f"{V1}/historical/ingest", json=_FEB_PAYLOAD)
        job_id = resp.json()["job_id"]
        # TestClient runs background tasks synchronously, status may already be final
        assert job_id in HISTORICAL_JOBS

    def test_job_has_required_fields(self, client):
        resp = client.post(f"{V1}/historical/ingest", json=_FEB_PAYLOAD)
        job_id = resp.json()["job_id"]
        job = HISTORICAL_JOBS[job_id]
        for key in ("status", "total", "done", "errors"):
            assert key in job

    def test_two_successive_jobs_have_different_ids(self, client):
        id1 = client.post(f"{V1}/historical/ingest", json=_FEB_PAYLOAD).json()["job_id"]
        id2 = client.post(f"{V1}/historical/ingest", json=_FEB_PAYLOAD).json()["job_id"]
        assert id1 != id2


# ---------------------------------------------------------------------------
# GET /historical/progress/{job_id}
# ---------------------------------------------------------------------------

class TestIngestProgress:
    def _seed_job(self, status="running"):
        job_id = "test-job-abc-123"
        HISTORICAL_JOBS[job_id] = {
            "status": status,
            "total": 5,
            "done": 2,
            "errors": [],
            "current_season": "2024-25",
            "current_match": None,
        }
        return job_id

    def test_known_job_returns_200(self, client):
        job_id = self._seed_job()
        resp = client.get(f"{V1}/historical/progress/{job_id}")
        assert resp.status_code == 200

    def test_returns_status_field(self, client):
        job_id = self._seed_job("running")
        resp = client.get(f"{V1}/historical/progress/{job_id}")
        assert resp.json()["status"] == "running"

    def test_returns_done_count(self, client):
        job_id = self._seed_job()
        resp = client.get(f"{V1}/historical/progress/{job_id}")
        assert resp.json()["done"] == 2

    def test_unknown_job_returns_404(self, client):
        resp = client.get(f"{V1}/historical/progress/does-not-exist")
        assert resp.status_code == 404

    def test_done_job_fields_present(self, client):
        job_id = self._seed_job("done")
        resp = client.get(f"{V1}/historical/progress/{job_id}")
        body = resp.json()
        assert body["status"] == "done"
        assert "errors" in body


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
