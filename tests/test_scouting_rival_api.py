"""Rival scouting report API (issue #299): a background job per request, progress, the JSON report and the PDF.

Compute only (nothing is persisted), so it needs no admin key, but only ONE job may run at a time and finished jobs expire.
The service is replaced here by a fake: it has its own tests; these are about the HTTP contract and the job life cycle.
"""
import time
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db
from src.live_prep.scouting_report import build_scouting_report
from src.services.team_report_service import TeamNotFoundError
from tests.test_scouting_report import collected

V1 = "/api/v1/scouting-rival"
COLLECTION = "FEB_TEST_2025_A"
BODY = {"collection": COLLECTION, "team_id": "T1", "own_team_id": "T2"}
CALLS = []


class FakeService:
    fail = None

    def __init__(self, db):
        pass

    def build(self, collection, team_id, own_team_id=None, progress=None):
        CALLS.append((collection, team_id, own_team_id))
        if FakeService.fail:
            raise FakeService.fail
        if progress:
            progress(3, 3)
        report = build_scouting_report(collected())
        report.update(collection=collection, own_team={"id": own_team_id, "name": "NUESTRO EQUIPO"} if own_team_id else None)
        return report


@pytest.fixture()
def client(monkeypatch):
    from src.api.routers import scouting_rival

    handler = MagicMock()
    handler.get_teams_with_ids.return_value = [{"id": "T1", "name": "EQUIPO DEL INFORME"}, {"id": "T2", "name": "NUESTRO EQUIPO"}]
    monkeypatch.setattr(scouting_rival, "SERVICE", FakeService)
    FakeService.fail = None
    CALLS.clear()
    scouting_rival.JOBS.clear()
    app.dependency_overrides[get_db] = lambda: handler
    yield TestClient(app)
    app.dependency_overrides.clear()
    scouting_rival.JOBS.clear()


def wait_done(client, job_id, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        p = client.get(f"{V1}/progress/{job_id}").json()
        if p["status"] != "running":
            return p
        time.sleep(0.05)
    raise AssertionError("job did not finish")


class TestJob:
    def test_full_flow_progress_report_and_pdf(self, client):
        r = client.post(V1, json=BODY)
        assert r.status_code == 202
        job = r.json()["job_id"]
        progress = wait_done(client, job)
        assert progress["status"] == "done" and progress["team"] == "EQUIPO DEL INFORME" and progress["own_team"] == "NUESTRO EQUIPO"
        assert (progress["current"], progress["total"]) == (3, 3)
        assert CALLS == [(COLLECTION, "T1", "T2")]
        report = client.get(f"{V1}/report/{job}").json()
        assert report["team"]["name"] == "EQUIPO DEL INFORME" and report["keys"]
        pdf = client.get(f"{V1}/pdf/{job}")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and pdf.headers["content-type"] == "application/pdf"
        assert 'filename="Scouting_EQUIPO_DEL_INFORME.pdf"' in pdf.headers["content-disposition"]

    def test_the_pdf_can_be_downloaded_again_until_it_expires(self, client):
        job = client.post(V1, json=BODY).json()["job_id"]
        wait_done(client, job)
        assert client.get(f"{V1}/pdf/{job}").status_code == 200
        assert client.get(f"{V1}/pdf/{job}").status_code == 200

    def test_our_team_is_optional(self, client):
        job = client.post(V1, json={"collection": COLLECTION, "team_id": "T1"}).json()["job_id"]
        assert wait_done(client, job)["status"] == "done"
        assert CALLS == [(COLLECTION, "T1", None)]

    def test_a_failure_is_reported_through_the_progress_and_blocks_the_downloads(self, client):
        FakeService.fail = RuntimeError("el motor falló")
        job = client.post(V1, json=BODY).json()["job_id"]
        progress = wait_done(client, job)
        assert progress["status"] == "error" and "el motor falló" in progress["error"]
        for path in ("report", "pdf"):
            assert client.get(f"{V1}/{path}/{job}").status_code == 409

    def test_a_team_without_games_is_a_readable_error(self, client):
        FakeService.fail = ValueError("El equipo T1 no tiene partidos con jugada a jugada en la colección")
        job = client.post(V1, json=BODY).json()["job_id"]
        assert "no tiene partidos" in wait_done(client, job)["error"]

    def test_unknown_or_expired_jobs(self, client):
        for path in ("progress", "report", "pdf"):
            assert client.get(f"{V1}/{path}/nope").status_code == 404

    def test_jobs_expire(self, client):
        from src.api.routers import scouting_rival

        job = client.post(V1, json=BODY).json()["job_id"]
        wait_done(client, job)
        scouting_rival.JOBS[job]["created_at"] -= scouting_rival.JOB_TTL_S + 1
        assert client.get(f"{V1}/progress/{job}").status_code == 404


class TestValidation:
    def test_unknown_team_is_404_and_same_team_is_422(self, client):
        assert client.post(V1, json={**BODY, "team_id": "ZZZ"}).status_code == 404
        assert client.post(V1, json={**BODY, "own_team_id": "ZZZ"}).status_code == 404
        assert client.post(V1, json={**BODY, "own_team_id": "T1"}).status_code == 422

    def test_fbcyl_is_not_supported_yet(self, client):
        assert client.post(V1, json={**BODY, "collection": "FBCYL_1A_FASE_GRUPO_A_2025"}).status_code == 422

    def test_a_body_without_team_is_422(self, client):
        assert client.post(V1, json={"collection": COLLECTION}).status_code == 422

    def test_only_one_job_at_a_time(self, client):
        from src.api.routers import scouting_rival

        scouting_rival.JOBS["busy"] = {"status": "running", "created_at": time.time()}
        assert client.post(V1, json=BODY).status_code == 429

    def test_the_service_error_for_an_unknown_team_is_a_404_in_the_job(self, client):
        FakeService.fail = TeamNotFoundError("T1")
        job = client.post(V1, json=BODY).json()["job_id"]
        assert wait_done(client, job)["status"] == "error"
