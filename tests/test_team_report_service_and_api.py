"""Team report: HTML renderer, service (data gathering) and API endpoints (#121/#126)."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db
from src.report_engine import build_team_report
from src.report_engine.html_renderer import render_report_html
from src.services.team_report_service import TeamNotFoundError, TeamReportService

V1 = "/api/v1/reports"

QUARTILES = {
    "points_per_game": {"q1": 70, "q2": 78, "q3": 85},
    "turnovers_per_game": {"q1": 11, "q2": 13, "q3": 15},
}
TEAM = {"team_id": "7", "games_played": 20, "points_per_game": 90.0, "turnovers_per_game": 18.0}


class FakeStats:
    def __init__(self, rows=None, cv=None):
        self.rows = [TEAM] if rows is None else rows
        self.cv = {"own": {"Equipo <A>": {"turnovers_per_game": {"cv": 40, "n": 20}}}} if cv is None else cv

    def load_season_data(self, collection):
        return {"team_stats": self.rows, "opponent_stats": []}

    def get_quartiles(self, collection):
        return QUARTILES

    def get_consistency(self, collection):
        return self.cv

    def get_teams_with_ids(self, collection):
        return [{"id": "7", "name": "Equipo <A>"}, {"id": "8", "name": "B"}]


class TestRenderer:
    def _report(self, mode="own"):
        return build_team_report("Equipo <A>", TEAM, QUARTILES, {"turnovers_per_game": {"cv": 40, "n": 20}}, mode)

    def test_contains_sections_and_escapes_team_name(self):
        html = render_report_html(self._report())
        assert "Equipo &lt;A&gt;" in html and "<A>" not in html
        for heading in ("Puntos fuertes", "Debilidades", "diferencial", "Consistencia", "Recomendaciones", "entrenamiento"):
            assert heading in html

    def test_rival_mode_uses_scouting_wording(self):
        html = render_report_html(self._report("rival"))
        assert "Scouting" in html and "neutralizar" in html.lower()

    def test_empty_report_renders_without_error(self):
        html = render_report_html(build_team_report("X", {}, {}, None))
        assert "X" in html

    def test_html_is_accepted_by_the_pdf_generator(self):
        from src.services.pdf_generator import PDFGenerator

        pdf = PDFGenerator.generate_bytes_from_html(render_report_html(self._report()))
        assert pdf.startswith(b"%PDF")


class TestService:
    def test_builds_report_for_a_team_id(self):
        r = TeamReportService(MagicMock(), stats=FakeStats()).build("col", "7", "own")
        assert r["team"] == "Equipo <A>" and r["games_played"] == 20
        assert "points_per_game" in [f["key"] for f in r["strengths"]]
        assert r["consistency"][0]["key"] == "turnovers_per_game"

    def test_unknown_team_raises(self):
        with pytest.raises(TeamNotFoundError):
            TeamReportService(MagicMock(), stats=FakeStats()).build("col", "99", "own")

    def test_consistency_failure_does_not_break_the_report(self):
        r = TeamReportService(MagicMock(), stats=FakeStats(cv={})).build("col", "7", "rival")
        assert r["consistency"] == [] and r["mode"] == "rival"

    def test_fbcyl_style_rows_matched_by_underscore_id(self):
        rows = [{"_id": "7", **{k: v for k, v in TEAM.items() if k != "team_id"}}]
        r = TeamReportService(MagicMock(), stats=FakeStats(rows=rows)).build("col", "7", "own")
        assert r["games_played"] == 20


@pytest.fixture()
def client():
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.clear()


SVC = "src.api.routers.team_report.TeamReportService"


class TestEndpoints:
    def test_json_report(self, client):
        with patch(SVC) as svc:
            svc.return_value.build.return_value = build_team_report("A", TEAM, QUARTILES, None)
            r = client.get(f"{V1}/team-report/col?team_id=7&mode=rival")
        assert r.status_code == 200 and r.json()["team"] == "A"
        svc.return_value.build.assert_called_once_with("col", "7", "rival")

    def test_unknown_team_is_404(self, client):
        with patch(SVC) as svc:
            svc.return_value.build.side_effect = TeamNotFoundError("7")
            assert client.get(f"{V1}/team-report/col?team_id=7").status_code == 404

    def test_invalid_mode_is_422(self, client):
        assert client.get(f"{V1}/team-report/col?team_id=7&mode=other").status_code == 422

    def test_team_id_is_required(self, client):
        assert client.get(f"{V1}/team-report/col").status_code == 422

    def test_pdf_download(self, client):
        with patch(SVC) as svc:
            svc.return_value.build.return_value = build_team_report("Equipo A", TEAM, QUARTILES, None)
            r = client.get(f"{V1}/team-report/col/pdf?team_id=7")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")
        assert "Analisis_Equipo_A" in r.headers["content-disposition"]

    def test_pdf_filename_for_rival_is_scouting(self, client):
        with patch(SVC) as svc:
            svc.return_value.build.return_value = build_team_report("Equipo A", TEAM, QUARTILES, None, "rival")
            r = client.get(f"{V1}/team-report/col/pdf?team_id=7&mode=rival")
        assert "Scouting_Equipo_A" in r.headers["content-disposition"]
