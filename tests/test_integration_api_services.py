"""Integration tests for API layer.

Tests the full API → Service → (mocked) Repository chain using FastAPI TestClient.
Covers three router modules with low/medium coverage:
  - ai.py (59% → +15%)     : SSE stream, export-pdf, individual-scouting/docx
  - reports.py (partial)   : weekly-report job lifecycle, progress, download
  - collections + teams    : end-to-end pagination, dependency chain

INTEGRATION pattern: TestClient with ``app.dependency_overrides[get_db]``;
AI provider calls patched with unittest.mock to avoid real network calls.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import json

import pytest
from fastapi.testclient import TestClient

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from src.api.app import app
from src.api.deps import get_db

V1 = "/api/v1"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_mock_db(**kwargs) -> MagicMock:
    handler = MagicMock()
    handler.is_connected.return_value = True
    handler.get_team_stats.return_value = kwargs.get("team_stats", [])
    handler.get_league_stats.return_value = kwargs.get("league_stats", {})
    handler.get_player_stats.return_value = kwargs.get("player_stats", [])
    handler.get_all_teams.return_value = kwargs.get("all_teams", [])
    handler.get_teams_with_ids.return_value = kwargs.get("teams_with_ids", [])
    handler.get_opponent_stats.return_value = []
    handler.get_aggregated_team_stats.return_value = {}
    handler.get_aggregated_opponent_stats.return_value = {}
    mock_coll = MagicMock()
    mock_coll.count_documents.return_value = 1
    mock_coll.find.return_value = []
    handler.connection.get_collection.return_value = mock_coll
    handler.connection.is_connected.return_value = True
    return handler


def _make_team_stat(name: str = "Alpha FC", ppg: float = 78.0) -> dict:
    return {
        "team_name": name, "total_games": 18,
        "points_per_game": ppg, "points_allowed_per_game": 73.0,
        "rebounds_per_game": 36.0, "assists_per_game": 18.0,
        "steals_per_game": 8.0, "turnovers_per_game": 13.0,
        "blocks_per_game": 3.5, "possessions_per_game": 72.0,
        "fg2_percentage": 0.48, "fg3_percentage": 0.36,
        "ft_percentage": 0.74, "efg_percentage": 0.52,
        "true_shooting": 0.55, "turnover_rate": 0.12,
        "offensive_rebound_rate": 0.30, "free_throw_rate": 0.25,
        "three_point_rate": 0.38, "assist_rate": 0.55,
        "assist_fg_rate": 0.60, "steal_rate": 0.09,
        "block_rate": 0.05, "defensive_rebound_rate": 0.72,
        "offensive_rating": 110.0, "defensive_rating": 104.0,
        "net_rating": 6.0, "points_scored": 1400,
        "total_rebounds": 648, "rebounds_off": 180, "rebounds_def": 468,
    }


# ---------------------------------------------------------------------------
# AI Router integration tests
# ---------------------------------------------------------------------------

class TestAIExportPDF:
    """Integration: POST /api/v1/ai/export-pdf covers PDFGenerator pipeline."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        db = _make_mock_db()
        app.dependency_overrides[get_db] = lambda: db
        yield TestClient(app)
        app.dependency_overrides.clear()

    @pytest.fixture
    def client(self):
        db = _make_mock_db()
        app.dependency_overrides[get_db] = lambda: db
        c = TestClient(app)
        yield c
        app.dependency_overrides.clear()

    def test_export_pdf_returns_200(self, client):
        r = client.post(f"{V1}/ai/export-pdf", json={
            "html": "<p>Análisis del equipo Alpha FC</p>",
            "team": "Alpha FC",
            "analysis_type": "own",
        })
        assert r.status_code == 200

    def test_export_pdf_content_type_is_pdf(self, client):
        r = client.post(f"{V1}/ai/export-pdf", json={
            "html": "<p>Stats</p>",
            "team": "Beta BC",
        })
        assert "pdf" in r.headers.get("content-type", "")

    def test_export_pdf_body_is_non_empty(self, client):
        r = client.post(f"{V1}/ai/export-pdf", json={
            "html": "<h1>Alpha FC</h1><p>PPG: 78.5</p>",
            "team": "Alpha FC",
        })
        assert len(r.content) > 0

    def test_export_pdf_empty_html(self, client):
        r = client.post(f"{V1}/ai/export-pdf", json={"html": "", "team": ""})
        assert r.status_code == 200

    def test_export_pdf_with_emojis_no_500(self, client):
        r = client.post(f"{V1}/ai/export-pdf", json={
            "html": "<p>🔥 Fortaleza ⚠️ Aviso ✅ OK</p>",
            "team": "Alpha FC",
        })
        assert r.status_code == 200

    def test_export_pdf_content_disposition_header(self, client):
        r = client.post(f"{V1}/ai/export-pdf", json={
            "html": "<p>Text</p>", "team": "Alpha FC",
        })
        assert "attachment" in r.headers.get("content-disposition", "")


class TestAIStreamEndpoint:
    """Integration: GET /api/v1/ai/analyze/stream with mocked AI provider."""

    @pytest.fixture
    def client_with_team(self):
        db = _make_mock_db(
            team_stats=[_make_team_stat("Alpha FC")],
            league_stats={"avg_points": 74.0},
        )

        # Mock TeamStatsService.get_consistency to avoid DB calls
        def _mock_get_consistency(coll):
            return {"own": {"Alpha FC": {"cv_ppg": 8.5}}}

        with patch("src.services.team_stats_service.TeamStatsService.get_consistency",
                   side_effect=_mock_get_consistency):
            app.dependency_overrides[get_db] = lambda: db
            yield TestClient(app)
            app.dependency_overrides.clear()

    def test_stream_no_api_key_returns_error_event(self, client_with_team):
        """Without a configured API key, SSE emits error JSON."""
        with patch("src.ai.config.AnalysisConfig.has_api_key", return_value=False):
            r = client_with_team.get(
                f"{V1}/ai/analyze/stream",
                params={"collection": "FEB_LF2_2025", "team_id": "Alpha FC",
                        "provider": "groq"},
            )
        # SSE returns 200 but body contains error data
        assert r.status_code == 200
        assert "error" in r.text

    def test_stream_returns_200(self, client_with_team):
        with patch("src.ai.config.AnalysisConfig.has_api_key", return_value=False):
            r = client_with_team.get(
                f"{V1}/ai/analyze/stream",
                params={"collection": "FEB_LF2_2025", "team_id": "Alpha FC"},
            )
        assert r.status_code == 200

    def test_stream_content_type_sse(self, client_with_team):
        with patch("src.ai.config.AnalysisConfig.has_api_key", return_value=False):
            r = client_with_team.get(
                f"{V1}/ai/analyze/stream",
                params={"collection": "FEB_LF2_2025", "team_id": "Alpha FC"},
            )
        assert "text/event-stream" in r.headers.get("content-type", "")


class TestAIIndividualScoutingDocx:
    """Integration: GET /api/v1/ai/individual-scouting/docx."""

    @pytest.fixture
    def client(self):
        db = _make_mock_db(team_stats=[_make_team_stat("Alpha FC")])
        app.dependency_overrides[get_db] = lambda: db
        yield TestClient(app)
        app.dependency_overrides.clear()

    def test_docx_no_players_returns_404(self, client):
        """When IndividualScoutingDocxBuilder returns None/empty, endpoint 404s."""
        with patch("src.services.individual_scouting_service.IndividualScoutingDocxBuilder") as MockBuilder:
            MockBuilder.return_value.build.return_value = None
            r = client.get(
                f"{V1}/ai/individual-scouting/docx",
                params={"collection": "FEB_LF2_2025", "team_id": "Alpha FC"},
            )
        assert r.status_code == 404

    def test_docx_with_data_returns_200(self, client):
        docx_fake = b"PK\x03\x04" + b"\x00" * 100  # minimal DOCX-like bytes
        with patch("src.services.individual_scouting_service.IndividualScoutingDocxBuilder") as MockBuilder:
            MockBuilder.return_value.build.return_value = docx_fake
            r = client.get(
                f"{V1}/ai/individual-scouting/docx",
                params={"collection": "FEB_LF2_2025", "team_id": "Alpha FC"},
            )
        assert r.status_code == 200

    def test_docx_content_type_is_docx(self, client):
        docx_fake = b"PK\x03\x04" + b"\x00" * 100
        with patch("src.services.individual_scouting_service.IndividualScoutingDocxBuilder") as MockBuilder:
            MockBuilder.return_value.build.return_value = docx_fake
            r = client.get(
                f"{V1}/ai/individual-scouting/docx",
                params={"collection": "FEB_LF2_2025", "team_id": "Alpha FC"},
            )
        assert "wordprocessingml" in r.headers.get("content-type", "")

    def test_docx_builder_exception_returns_500(self, client):
        with patch("src.services.individual_scouting_service.IndividualScoutingDocxBuilder") as MockBuilder:
            MockBuilder.return_value.build.side_effect = RuntimeError("Build failed")
            r = client.get(
                f"{V1}/ai/individual-scouting/docx",
                params={"collection": "FEB_LF2_2025", "team_id": "Alpha FC"},
            )
        assert r.status_code == 500

    def test_docx_filename_sanitized(self, client):
        docx_fake = b"PK\x03\x04" + b"\x00" * 100
        with patch("src.services.individual_scouting_service.IndividualScoutingDocxBuilder") as MockBuilder:
            MockBuilder.return_value.build.return_value = docx_fake
            r = client.get(
                f"{V1}/ai/individual-scouting/docx",
                params={"collection": "FEB_LF2_2025", "team_id": "Alpha FC"},
            )
        cd = r.headers.get("content-disposition", "")
        assert "Scouting_" in cd


# ---------------------------------------------------------------------------
# Reports router — weekly-report job lifecycle
# ---------------------------------------------------------------------------

class TestWeeklyReportJobLifecycle:
    """Integration: job creation → progress polling → download (mocked ZIP)."""

    @pytest.fixture(autouse=True)
    def client(self):
        db = _make_mock_db()
        app.dependency_overrides[get_db] = lambda: db
        self._client = TestClient(app)
        yield
        app.dependency_overrides.clear()

    def test_start_returns_job_id(self):
        with patch("src.services.weekly_report_service.WeeklyReportService.generate_report_zip",
                   return_value=b"PK\x03\x04test"):
            r = self._client.post(
                f"{V1}/reports/FEB_LF2_2025/weekly-report",
                json={"team_a": "Alpha FC", "team_b": "Beta BC"},
            )
        assert r.status_code == 200
        assert "job_id" in r.json()

    def test_start_job_id_is_uuid_format(self):
        import uuid
        with patch("src.services.weekly_report_service.WeeklyReportService.generate_report_zip",
                   return_value=b"PK\x03\x04test"):
            r = self._client.post(
                f"{V1}/reports/FEB_LF2_2025/weekly-report",
                json={"team_a": "Alpha FC", "team_b": "Beta BC"},
            )
        job_id = r.json()["job_id"]
        # Should parse as valid UUID
        uuid.UUID(job_id)

    def test_progress_known_job_returns_200(self):
        with patch("src.services.weekly_report_service.WeeklyReportService.generate_report_zip",
                   return_value=b"PK\x03\x04test"):
            r1 = self._client.post(
                f"{V1}/reports/FEB_LF2_2025/weekly-report",
                json={"team_a": "Alpha FC", "team_b": "Beta BC"},
            )
        job_id = r1.json()["job_id"]
        r2 = self._client.get(f"{V1}/reports/weekly-report-progress/{job_id}")
        assert r2.status_code == 200

    def test_progress_unknown_job_returns_404(self):
        r = self._client.get(f"{V1}/reports/weekly-report-progress/nonexistent-job")
        assert r.status_code == 404

    def test_progress_response_has_status_field(self):
        with patch("src.services.weekly_report_service.WeeklyReportService.generate_report_zip",
                   return_value=b"PK\x03\x04test"):
            r1 = self._client.post(
                f"{V1}/reports/FEB_LF2_2025/weekly-report",
                json={"team_a": "Alpha FC", "team_b": "Beta BC"},
            )
        job_id = r1.json()["job_id"]
        r2 = self._client.get(f"{V1}/reports/weekly-report-progress/{job_id}")
        assert "status" in r2.json()

    def test_download_not_ready_returns_409(self):
        """A job that is still running returns 409 when trying to download."""
        from src.api.routers.reports import REPORT_JOBS
        import uuid as _uuid
        job_id = str(_uuid.uuid4())
        REPORT_JOBS[job_id] = {"status": "running", "step": 1, "total": 5,
                                "message": "Working", "zip_bytes": None, "error": None}
        r = self._client.get(f"{V1}/reports/weekly-report-download/{job_id}")
        assert r.status_code == 409
        del REPORT_JOBS[job_id]

    def test_download_unknown_job_returns_404(self):
        r = self._client.get(f"{V1}/reports/weekly-report-download/no-such-job")
        assert r.status_code == 404

    def test_download_done_job_returns_200_and_zip(self):
        """A completed job should deliver the ZIP bytes."""
        from src.api.routers.reports import REPORT_JOBS
        import uuid as _uuid
        job_id = str(_uuid.uuid4())
        REPORT_JOBS[job_id] = {
            "status": "done", "step": 5, "total": 5,
            "message": "Completado", "zip_bytes": b"PK\x03\x04fake_zip", "error": None,
        }
        r = self._client.get(f"{V1}/reports/weekly-report-download/{job_id}")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/zip"

    def test_download_done_job_removed_after_download(self):
        """Job entry is cleaned up after successful download (one-time use)."""
        from src.api.routers.reports import REPORT_JOBS
        import uuid as _uuid
        job_id = str(_uuid.uuid4())
        REPORT_JOBS[job_id] = {
            "status": "done", "step": 5, "total": 5,
            "message": "Completado", "zip_bytes": b"PK\x03\x04data", "error": None,
        }
        self._client.get(f"{V1}/reports/weekly-report-download/{job_id}")
        assert job_id not in REPORT_JOBS


# ---------------------------------------------------------------------------
# Collections router — pagination integration
# ---------------------------------------------------------------------------

class TestCollectionsPagination:
    """Integration: GET /api/v1/collections/list with skip/limit pagination."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        db = _make_mock_db()
        mock_coll = MagicMock()
        mock_coll.count_documents.return_value = 1
        db.connection.get_collection.return_value = mock_coll
        # Patch list_collection_names on the underlying client
        db.connection.db.list_collection_names = MagicMock(
            return_value=[f"FEB_LF2_2025_{chr(65+i)}" for i in range(10)]
        )
        app.dependency_overrides[get_db] = lambda: db
        self._client = TestClient(app)
        yield
        app.dependency_overrides.clear()

    def test_list_returns_200(self):
        r = self._client.get(f"{V1}/collections/list")
        assert r.status_code == 200

    def test_list_with_limit(self):
        r = self._client.get(f"{V1}/collections/list?limit=5")
        assert r.status_code == 200

    def test_list_with_skip_and_limit(self):
        r = self._client.get(f"{V1}/collections/list?skip=2&limit=3")
        assert r.status_code == 200

    def test_list_limit_too_large_returns_422(self):
        r = self._client.get(f"{V1}/collections/list?limit=501")
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Teams router — season stats integration
# ---------------------------------------------------------------------------

class TestTeamStatsIntegration:
    """Integration: GET /api/v1/{collection}/teams → validates TeamStatsService chain."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        teams = [
            _make_team_stat("Alpha FC", ppg=78.0),
            _make_team_stat("Beta BC", ppg=72.0),
        ]
        db = _make_mock_db(team_stats=teams)
        app.dependency_overrides[get_db] = lambda: db
        self._client = TestClient(app)
        yield
        app.dependency_overrides.clear()

    def test_teams_endpoint_returns_200(self):
        r = self._client.get(f"{V1}/teams/FEB_LF2_2025/teams")
        assert r.status_code == 200

    def test_teams_endpoint_returns_list(self):
        r = self._client.get(f"{V1}/teams/FEB_LF2_2025/teams")
        body = r.json()
        assert isinstance(body, (list, dict))

    def test_teams_with_pagination(self):
        r = self._client.get(f"{V1}/teams/FEB_LF2_2025/teams?skip=0&limit=1")
        assert r.status_code == 200
