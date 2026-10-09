"""Live preparation package: generation service + API (issue #133, part a).

POST /api/v1/live/package starts a background job; progress is polled and the encrypted
file is downloaded once. Compute-only (nothing persisted), hence public but single-flight.
"""
import json
import time
from unittest.mock import MagicMock

import pytest
from db_helpers import new_mock_db
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db
from src.live_core.package import PreparationPackage
from src.live_prep.package_crypto import decrypt_package

OWN, RIVAL = "982047", "981204"
V1 = "/api/v1/live"
BODY = {"collection": "FEB_TEST_2025_A", "team_id": OWN, "rival_id": RIVAL, "passphrase": "clave-segura-1"}


@pytest.fixture()
def handler(feb_game_doc):
    coll = new_mock_db()["FEB_TEST_2025_A"]
    coll.insert_one({**feb_game_doc, "_id": "g1", "_season": "2025-2026"})
    h = MagicMock()
    h.repository.connection.get_collection.return_value = coll
    h.get_teams_with_ids.return_value = [
        {"id": OWN, "name": "ACEITES ABRIL ADBA SANFER"}, {"id": RIVAL, "name": "MANRESA CBF A"}]
    return h


@pytest.fixture()
def client(handler):
    from src.api.routers import live_package

    live_package.JOBS.clear()
    app.dependency_overrides[get_db] = lambda: handler
    yield TestClient(app)
    app.dependency_overrides.clear()
    live_package.JOBS.clear()


def _wait_done(client, job_id, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        p = client.get(f"{V1}/package/progress/{job_id}").json()
        if p["status"] != "running":
            return p
        time.sleep(0.05)
    raise AssertionError("job did not finish")


class TestGeneration:
    def test_full_flow_returns_an_encrypted_package_that_decrypts(self, client):
        r = client.post(f"{V1}/package", json=BODY)
        assert r.status_code == 202
        job = r.json()["job_id"]
        progress = _wait_done(client, job)
        assert progress["status"] == "done" and progress["team"] == "ACEITES ABRIL ADBA SANFER"
        dl = client.get(f"{V1}/package/download/{job}")
        assert dl.status_code == 200
        assert "attachment" in dl.headers["content-disposition"] and ".bpkg" in dl.headers["content-disposition"]
        pkg = PreparationPackage.loads(decrypt_package(json.loads(dl.content), BODY["passphrase"]))
        assert pkg.team["id"] == OWN and pkg.rival["id"] == RIVAL and pkg.season == "2025-2026"

    def test_the_passphrase_is_never_returned_or_stored(self, client):
        from src.api.routers import live_package

        job = client.post(f"{V1}/package", json=BODY).json()["job_id"]
        progress = _wait_done(client, job)
        assert BODY["passphrase"] not in json.dumps(progress)
        assert BODY["passphrase"] not in repr(live_package.JOBS[job])

    def test_download_is_one_shot(self, client):
        job = client.post(f"{V1}/package", json=BODY).json()["job_id"]
        _wait_done(client, job)
        assert client.get(f"{V1}/package/download/{job}").status_code == 200
        assert client.get(f"{V1}/package/download/{job}").status_code == 404

    def test_progress_reports_games_processed(self, client):
        job = client.post(f"{V1}/package", json=BODY).json()["job_id"]
        p = _wait_done(client, job)
        assert p["total"] == 1 and p["current"] == 1


class TestValidation:
    @pytest.mark.parametrize("change, status", [
        ({"passphrase": "corta"}, 422),
        ({"rival_id": OWN}, 422),
        ({"team_id": ""}, 422),
        ({"collection": ""}, 422),
    ])
    def test_invalid_input_is_rejected(self, client, change, status):
        assert client.post(f"{V1}/package", json={**BODY, **change}).status_code == status

    def test_fbcyl_collections_are_not_supported_yet(self, client):
        r = client.post(f"{V1}/package", json={**BODY, "collection": "FBCYL_1A_2026"})
        assert r.status_code == 422 and "FEB" in r.json()["detail"]

    def test_unknown_team_is_a_404(self, client):
        r = client.post(f"{V1}/package", json={**BODY, "team_id": "999"})
        assert r.status_code == 404

    def test_unknown_job_is_a_404(self, client):
        assert client.get(f"{V1}/package/progress/nope").status_code == 404
        assert client.get(f"{V1}/package/download/nope").status_code == 404

    def test_download_before_completion_is_a_409(self, client):
        from src.api.routers import live_package

        live_package.JOBS["j"] = {"status": "running", "created_at": time.time()}
        assert client.get(f"{V1}/package/download/j").status_code == 409


class TestLimits:
    def test_only_one_generation_at_a_time(self, client):
        from src.api.routers import live_package

        live_package.JOBS["busy"] = {"status": "running", "created_at": time.time()}
        r = client.post(f"{V1}/package", json=BODY)
        assert r.status_code == 429

    def test_stale_jobs_are_purged_and_do_not_block_new_ones(self, client):
        from src.api.routers import live_package

        live_package.JOBS["old"] = {"status": "running", "created_at": time.time() - live_package.JOB_TTL_S - 5}
        assert client.post(f"{V1}/package", json=BODY).status_code == 202
        assert "old" not in live_package.JOBS

    def test_failed_generation_is_reported_not_raised(self, client, handler):
        handler.repository.connection.get_collection.side_effect = RuntimeError("db down")
        job = client.post(f"{V1}/package", json=BODY).json()["job_id"]
        p = _wait_done(client, job)
        assert p["status"] == "error" and "db down" in p["error"]
        assert client.get(f"{V1}/package/download/{job}").status_code == 409
