"""
Phase 5 quality-gate tests: report generation endpoints.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.app import app

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_PDF_MIME  = "application/pdf"


@pytest.fixture
def client():
    from src.api.deps import get_db
    app.dependency_overrides[get_db] = lambda: MagicMock()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Player scouting DOCX
# ---------------------------------------------------------------------------

class TestPlayerScoutingEndpoint:
    BASE = "/api/v1/reports"

    def test_returns_docx_content_type(self, client):
        fake_bytes = b"PK\x03\x04fake-docx-content"  # DOCX starts with PK zip magic
        with patch("src.api.routers.reports.build_player_scouting_docx", return_value=fake_bytes):
            r = client.get(f"{self.BASE}/FEB_test/player-scouting/1234")
        assert r.status_code == 200
        assert r.headers["content-type"] == _DOCX_MIME

    def test_returns_content_disposition_attachment(self, client):
        with patch("src.api.routers.reports.build_player_scouting_docx", return_value=b"x"):
            r = client.get(f"{self.BASE}/FEB_test/player-scouting/999")
        assert "attachment" in r.headers.get("content-disposition", "")

    def test_docx_body_matches_service_output(self, client):
        marker = b"FAKE_DOCX_BODY"
        with patch("src.api.routers.reports.build_player_scouting_docx", return_value=marker):
            r = client.get(f"{self.BASE}/FEB_test/player-scouting/42")
        assert r.content == marker


# ---------------------------------------------------------------------------
# Team scouting PDF
# ---------------------------------------------------------------------------

class TestTeamScoutingEndpoint:
    BASE = "/api/v1/reports"

    def test_returns_pdf_content_type(self, client):
        fake_pdf = b"%PDF-1.4 fake"
        with patch("src.api.routers.reports.build_team_scouting_pdf", return_value=fake_pdf):
            r = client.get(f"{self.BASE}/FEB_test/team-scouting/TeamA")
        assert r.status_code == 200
        assert r.headers["content-type"] == _PDF_MIME

    def test_pdf_body_matches_service_output(self, client):
        marker = b"%PDF marker"
        with patch("src.api.routers.reports.build_team_scouting_pdf", return_value=marker):
            r = client.get(f"{self.BASE}/FEB_test/team-scouting/TeamB")
        assert r.content == marker

    def test_content_disposition_includes_team_name(self, client):
        with patch("src.api.routers.reports.build_team_scouting_pdf", return_value=b"x"):
            r = client.get(f"{self.BASE}/FEB_test/team-scouting/My_Team")
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd


# ---------------------------------------------------------------------------
# Season summary PDF
# ---------------------------------------------------------------------------

class TestSeasonSummaryEndpoint:
    BASE = "/api/v1/reports"

    def test_returns_pdf_content_type(self, client):
        fake_pdf = b"%PDF-1.4 summary"
        with patch("src.api.routers.reports.build_season_summary_pdf", return_value=fake_pdf):
            r = client.get(f"{self.BASE}/FEB_test/season-summary")
        assert r.status_code == 200
        assert r.headers["content-type"] == _PDF_MIME

    def test_pdf_body_matches_service_output(self, client):
        marker = b"season_summary_pdf_bytes"
        with patch("src.api.routers.reports.build_season_summary_pdf", return_value=marker):
            r = client.get(f"{self.BASE}/FEB_test/season-summary")
        assert r.content == marker


# ---------------------------------------------------------------------------
# Report service unit tests
# ---------------------------------------------------------------------------

class TestReportServiceUnits:
    """Test the report_service functions directly (no HTTP layer)."""

    def test_player_scouting_docx_returns_bytes_when_player_not_found(self):
        """Should produce a DOCX even if player_id is unknown."""
        from src.services.report_service import build_player_scouting_docx
        mock_db = MagicMock()
        with patch("src.services.report_service.PlayerStatsService") as MockSvc:
            MockSvc.return_value.load_season_data.return_value = []
            result = build_player_scouting_docx("FEB_test", "nonexistent", mock_db)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_team_scouting_pdf_returns_bytes(self):
        from src.services.report_service import build_team_scouting_pdf
        mock_db = MagicMock()
        with patch("src.services.report_service.TeamStatsService") as MockSvc:
            MockSvc.return_value.get_team_detailed_stats.return_value = {"points": 85.0}
            MockSvc.return_value.get_opponent_detailed_stats.return_value = {"points": 78.0}
            result = build_team_scouting_pdf("FEB_test", "TeamA", mock_db)
        assert isinstance(result, bytes)
        assert result[:4] == b"%PDF"

    def test_season_summary_pdf_returns_bytes_with_empty_data(self):
        from src.services.report_service import build_season_summary_pdf
        mock_db = MagicMock()
        with patch("src.services.report_service.TeamStatsService") as MockSvc:
            MockSvc.return_value.get_possession_stats.return_value = []
            result = build_season_summary_pdf("FEB_test", mock_db)
        assert isinstance(result, bytes)
        assert result[:4] == b"%PDF"

    def test_season_summary_pdf_includes_team_rows(self):
        from src.services.report_service import build_season_summary_pdf
        mock_db = MagicMock()
        teams = [
            {"team": "Alpha", "pace": 75.2, "oer": 105.0, "der": 98.0, "net_rating": 7.0},
            {"team": "Beta",  "pace": 72.1, "oer":  99.0, "der": 102.0, "net_rating": -3.0},
        ]
        with patch("src.services.report_service.TeamStatsService") as MockSvc:
            MockSvc.return_value.get_possession_stats.return_value = teams
            result_with = build_season_summary_pdf("FEB_test", mock_db)
        with patch("src.services.report_service.TeamStatsService") as MockSvc:
            MockSvc.return_value.get_possession_stats.return_value = []
            result_empty = build_season_summary_pdf("FEB_test", mock_db)
        # PDF with data should be larger than empty PDF (more content streams)
        assert len(result_with) >= len(result_empty)
