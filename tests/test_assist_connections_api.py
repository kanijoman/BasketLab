"""``GET /api/v1/assist-connections/{collection}/{team_id}`` (issue #773): the service's answer, read-only and public (no admin key)."""
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db
from tests.db_helpers import new_mock_db
from tests.test_assist_connection_service import FEB, Handler, feb_game


@pytest.fixture()
def client():
    db = new_mock_db()
    db[FEB].insert_one(feb_game())
    app.dependency_overrides[get_db] = lambda: Handler(db)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_it_answers_the_connections_of_the_team(client):
    body = client.get(f"/api/v1/assist-connections/{FEB}/10").json()
    assert body["assisted_baskets"] == 1 and body["format"] == "feb" and "focus" not in body


def test_the_player_filter_adds_the_focus(client):
    body = client.get(f"/api/v1/assist-connections/{FEB}/10", params={"player_id": "p2"}).json()
    assert body["focus"]["as_receiver"]["player_id"] == "p2"


def test_an_unknown_team_gives_an_empty_answer_not_an_error(client):
    response = client.get(f"/api/v1/assist-connections/{FEB}/999")
    assert response.status_code == 200 and response.json()["receivers"] == []
