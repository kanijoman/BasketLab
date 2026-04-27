"""Tests for the reports router — weekly-report job lifecycle.

Covers:
- POST /{collection}/weekly-report → returns {job_id}, status 200
- GET /weekly-report-progress/{job_id} → returns progress dict
- GET /weekly-report-progress/unknown → 404
- GET /weekly-report-download/{job_id} when running → 409
- GET /weekly-report-download/{job_id} when done → ZIP bytes
- GET /weekly-report-download/unknown → 404
- Background task sets status=done and stores zip_bytes
- Background task sets status=error on exception
"""

import io
import zipfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db
from src.api.routers.reports import REPORT_JOBS


V1 = "/api/v1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_report_jobs():
    """Wipe the in-process job store before and after every test."""
    REPORT_JOBS.clear()
    yield
    REPORT_JOBS.clear()


@pytest.fixture
def client():
    mock_db = MagicMock()
    mock_db.is_connected.return_value = True
    app.dependency_overrides[get_db] = lambda: mock_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /{collection}/weekly-report
# ---------------------------------------------------------------------------

class TestWeeklyReportStart:
    def test_returns_job_id(self, client):
        with patch("src.api.routers.reports._run_weekly_report"):
            res = client.post(
                f"{V1}/reports/FEB_LF2_2025_A/weekly-report",
                json={"team_a": "Team A", "team_b": "Team B"},
            )
        assert res.status_code == 200
        data = res.json()
        assert "job_id" in data
        assert isinstance(data["job_id"], str)

    def test_job_created_in_store(self, client):
        with patch("src.api.routers.reports._run_weekly_report"):
            res = client.post(
                f"{V1}/reports/FEB_LF2_2025_A/weekly-report",
                json={"team_a": "Team A", "team_b": "Team B"},
            )
        job_id = res.json()["job_id"]
        assert job_id in REPORT_JOBS

    def test_initial_job_status_is_running(self, client):
        with patch("src.api.routers.reports._run_weekly_report"):
            res = client.post(
                f"{V1}/reports/FEB_LF2_2025_A/weekly-report",
                json={"team_a": "Team A", "team_b": "Team B"},
            )
        job_id = res.json()["job_id"]
        assert REPORT_JOBS[job_id]["status"] == "running"

    def test_missing_team_a_returns_422(self, client):
        res = client.post(
            f"{V1}/reports/FEB_LF2_2025_A/weekly-report",
            json={"team_b": "Team B"},
        )
        assert res.status_code == 422

    def test_missing_team_b_returns_422(self, client):
        res = client.post(
            f"{V1}/reports/FEB_LF2_2025_A/weekly-report",
            json={"team_a": "Team A"},
        )
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# GET /weekly-report-progress/{job_id}
# ---------------------------------------------------------------------------

class TestWeeklyReportProgress:
    def test_returns_progress_for_known_job(self, client):
        REPORT_JOBS["abc"] = {"status": "running", "step": 2, "total": 5,
                               "message": "Procesando…", "error": None}
        res = client.get(f"{V1}/reports/weekly-report-progress/abc")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "running"
        assert data["step"] == 2
        assert data["total"] == 5

    def test_unknown_job_returns_404(self, client):
        res = client.get(f"{V1}/reports/weekly-report-progress/no-such-job")
        assert res.status_code == 404

    def test_done_status_returned(self, client):
        REPORT_JOBS["done-job"] = {"status": "done", "step": 5, "total": 5,
                                    "message": "Completado", "error": None,
                                    "zip_bytes": b"PK"}
        res = client.get(f"{V1}/reports/weekly-report-progress/done-job")
        assert res.json()["status"] == "done"

    def test_error_status_returned(self, client):
        REPORT_JOBS["err-job"] = {"status": "error", "step": 1, "total": 5,
                                   "message": "Error: boom", "error": "boom"}
        res = client.get(f"{V1}/reports/weekly-report-progress/err-job")
        data = res.json()
        assert data["status"] == "error"
        assert data["error"] == "boom"


# ---------------------------------------------------------------------------
# GET /weekly-report-download/{job_id}
# ---------------------------------------------------------------------------

class TestWeeklyReportDownload:
    def _make_zip(self) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("test.png", b"\x89PNG")
        return buf.getvalue()

    def test_download_returns_zip_when_done(self, client):
        z = self._make_zip()
        REPORT_JOBS["ready"] = {"status": "done", "step": 5, "total": 5,
                                 "message": "Completado", "error": None,
                                 "zip_bytes": z}
        res = client.get(f"{V1}/reports/weekly-report-download/ready")
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/zip"
        assert zipfile.is_zipfile(io.BytesIO(res.content))

    def test_download_removes_job_from_store(self, client):
        REPORT_JOBS["toclean"] = {"status": "done", "step": 5, "total": 5,
                                   "message": "ok", "error": None,
                                   "zip_bytes": self._make_zip()}
        client.get(f"{V1}/reports/weekly-report-download/toclean")
        assert "toclean" not in REPORT_JOBS

    def test_download_running_job_returns_409(self, client):
        REPORT_JOBS["busy"] = {"status": "running", "step": 1, "total": 5,
                                "message": "…", "error": None, "zip_bytes": None}
        res = client.get(f"{V1}/reports/weekly-report-download/busy")
        assert res.status_code == 409

    def test_download_unknown_job_returns_404(self, client):
        res = client.get(f"{V1}/reports/weekly-report-download/ghost")
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# _run_weekly_report background function
# ---------------------------------------------------------------------------

class TestRunWeeklyReport:
    def test_sets_done_on_success(self):
        from src.api.routers.reports import _run_weekly_report
        fake_zip = b"PK\x03\x04"
        db = MagicMock()
        REPORT_JOBS["j1"] = {"status": "running", "step": 0, "total": 5,
                              "message": "…", "zip_bytes": None, "error": None}
        with patch(
            "src.services.weekly_report_service.WeeklyReportService.generate_report_zip",
            return_value=fake_zip,
        ):
            _run_weekly_report("j1", "FEB_LF2_2025_A", "A", "B", db)
        assert REPORT_JOBS["j1"]["status"] == "done"
        assert REPORT_JOBS["j1"]["zip_bytes"] == fake_zip

    def test_sets_error_on_exception(self):
        from src.api.routers.reports import _run_weekly_report
        db = MagicMock()
        REPORT_JOBS["j2"] = {"status": "running", "step": 0, "total": 5,
                              "message": "…", "zip_bytes": None, "error": None}
        with patch(
            "src.services.weekly_report_service.WeeklyReportService.generate_report_zip",
            side_effect=RuntimeError("boom"),
        ):
            _run_weekly_report("j2", "FEB_LF2_2025_A", "A", "B", db)
        assert REPORT_JOBS["j2"]["status"] == "error"
        assert "boom" in REPORT_JOBS["j2"]["error"]

    def test_callback_updates_job_step(self):
        from src.api.routers.reports import _run_weekly_report
        db = MagicMock()
        REPORT_JOBS["j3"] = {"status": "running", "step": 0, "total": 5,
                              "message": "…", "zip_bytes": None, "error": None}

        recorded = []

        def fake_generate(self_svc, collection, ta, tb, progress_callback=None):
            for i in range(1, 6):
                progress_callback(i, 5, f"Step {i}")
                recorded.append(REPORT_JOBS["j3"]["step"])
            return b"PK"

        with patch(
            "src.services.weekly_report_service.WeeklyReportService.generate_report_zip",
            fake_generate,
        ):
            _run_weekly_report("j3", "FEB_LF2_2025_A", "A", "B", db)

        assert recorded == [1, 2, 3, 4, 5]
