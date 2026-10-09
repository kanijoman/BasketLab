"""Match list endpoint, match info inside the package and collection metadata (issue #119)."""
import json
import time
from unittest.mock import MagicMock, patch

import pytest
from db_helpers import new_mock_db
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db
from src.live_core.package import PreparationPackage
from src.live_prep.package_crypto import decrypt_package

OWN, RIVAL = "982047", "981204"
V1 = "/api/v1/live"
ROUTER_SVC = "src.api.routers.live_package.MatchScheduleService"
MATCH = {
    "code": "2524999", "kind": "scheduled", "round": 3, "score": None, "start": "2027-04-17T19:00", "status": "scheduled",
    "home": {"id": OWN, "name": "ACEITES ABRIL ADBA SANFER"}, "away": {"id": RIVAL, "name": "MANRESA CBF A"},
    "is_home": True, "opponent": {"id": RIVAL, "name": "MANRESA CBF A"}, "starts_in_min": 9000,
}


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


class TestMatchesEndpoint:
    def test_returns_the_service_result(self, client):
        with patch(ROUTER_SVC) as svc:
            svc.return_value.upcoming.return_value = {"matches": [MATCH], "calendar_url": "u", "warning": None}
            r = client.get(f"{V1}/matches/FEB_TEST_2025_A?team_id={OWN}&limit=3")
        assert r.status_code == 200 and r.json()["matches"][0]["code"] == "2524999"
        svc.return_value.upcoming.assert_called_once_with("FEB_TEST_2025_A", OWN, limit=3)

    def test_team_id_is_required_and_limit_is_bounded(self, client):
        assert client.get(f"{V1}/matches/FEB_TEST_2025_A").status_code == 422
        assert client.get(f"{V1}/matches/FEB_TEST_2025_A?team_id=1&limit=0").status_code == 422
        assert client.get(f"{V1}/matches/FEB_TEST_2025_A?team_id=1&limit=99").status_code == 422

    def test_calendar_problems_are_a_warning_with_200(self, client):
        with patch(ROUTER_SVC) as svc:
            svc.return_value.upcoming.return_value = {"matches": [], "calendar_url": None, "warning": "sin calendario"}
            r = client.get(f"{V1}/matches/FEB_TEST_2025_A?team_id={OWN}")
        assert r.status_code == 200 and r.json()["warning"] == "sin calendario"


def _wait(client, job):
    end = time.time() + 60
    while time.time() < end:
        p = client.get(f"{V1}/package/progress/{job}").json()
        if p["status"] != "running":
            return p
        time.sleep(0.05)
    raise AssertionError("timeout")


class TestMatchInThePackage:
    BODY = {"collection": "FEB_TEST_2025_A", "team_id": OWN, "rival_id": RIVAL, "passphrase": "clave-segura-1"}

    def _package(self, client, body):
        job = client.post(f"{V1}/package", json=body).json()["job_id"]
        assert _wait(client, job)["status"] == "done"
        env = json.loads(client.get(f"{V1}/package/download/{job}").content)
        return PreparationPackage.loads(decrypt_package(env, body["passphrase"]))

    def test_the_chosen_match_is_stored_in_competition_meta(self, client):
        with patch(ROUTER_SVC) as svc:
            svc.return_value.upcoming.return_value = {"matches": [MATCH], "calendar_url": "u", "warning": None}
            pkg = self._package(client, {**self.BODY, "match_code": "2524999"})
        assert pkg.competition_meta["match"] == {
            "code": "2524999", "start": "2027-04-17T19:00", "round": 3,
            "home": {"id": OWN, "name": "ACEITES ABRIL ADBA SANFER"}, "away": {"id": RIVAL, "name": "MANRESA CBF A"}}

    def test_unknown_match_code_keeps_only_the_code(self, client):
        with patch(ROUTER_SVC) as svc:
            svc.return_value.upcoming.return_value = {"matches": [], "calendar_url": "u", "warning": None}
            pkg = self._package(client, {**self.BODY, "match_code": "777"})
        assert pkg.competition_meta["match"] == {"code": "777"}

    def test_calendar_errors_do_not_block_the_package(self, client):
        with patch(ROUTER_SVC) as svc:
            svc.return_value.upcoming.side_effect = RuntimeError("feb down")
            pkg = self._package(client, {**self.BODY, "match_code": "777"})
        assert pkg.competition_meta["match"] == {"code": "777"}

    def test_without_match_code_the_package_has_no_match(self, client):
        assert "match" not in self._package(client, self.BODY).competition_meta

    def test_match_code_must_be_digits(self, client):
        assert client.post(f"{V1}/package", json={**self.BODY, "match_code": "abc"}).status_code == 422


class TestCollectionMetaAtScrapeTime:
    def test_save_feb_meta_upserts_the_competition_url_and_selection(self):
        from src.services.collection_meta import save_feb_meta

        metas = new_mock_db()["COLLECTION_META"]
        db = MagicMock()
        db.repository.connection.get_collection.return_value = metas
        params = MagicMock(competition_url="https://baloncestoenvivo.feb.es/calendario/lf2/9/2025", season_value="5",
                           group_value="1", year="2025", competition_label="LF2", season_label="LF2 2025", group_label="A")
        save_feb_meta(db, "LF2_2025_A", params)
        save_feb_meta(db, "LF2_2025_A", params)  # idempotent: replaces, never duplicates
        docs = list(metas.find({}))
        assert len(docs) == 1 and docs[0]["_id"] == "LF2_2025_A"
        assert docs[0]["competition_url"].endswith("/lf2/9/2025") and docs[0]["group_value"] == "1"
        assert docs[0]["league"] == "FEB" and "saved_at" in docs[0]

    def test_the_feb_scrape_job_saves_the_metadata(self):
        from src.api.routers import scrape

        scraper = MagicMock()
        scraper.get_page_content.return_value = (None, MagicMock())
        scraper.get_matches.return_value = []
        db = MagicMock()
        params = scrape.FEBScrapeParams(competition_url="https://x/calendario/lf2/9/2025", season_value="5", group_value="1",
                                        year="2025", competition_label="LF2", season_label="LF2 2025", group_label="A")
        scrape.SCRAPE_JOBS["job1"] = {"status": "queued", "errors": [], "done": 0, "skipped": 0, "total": 0}
        with patch("src.scraper.FEBWebScraper", return_value=scraper), patch("src.database.MongoDBHandler", return_value=db), \
                patch("src.services.collection_meta.save_feb_meta") as save:
            scrape._run_feb_scrape("job1", params)
        save.assert_called_once()
        assert save.call_args[0][2] is params
