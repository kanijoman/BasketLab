"""Tests for the rotaciones router (REST + SSE), RotationService mocked."""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db

V1 = "/api/v1/rotaciones"
SVC = "src.api.routers.rotaciones.RotationService"


@pytest.fixture()
def client():
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.clear()


def _events(raw: str) -> list:
    return [json.loads(l[6:]) for l in raw.splitlines() if l.startswith("data: ")]


class TestRotationRest:
    def test_returns_service_result_and_forwards_params(self, client):
        with patch(SVC) as svc:
            svc.return_value.get_rotation_analysis.return_value = {"players": []}
            r = client.get(f"{V1}/col/7?team_name=Foo&min_games=2&min_total_min=30")
        assert r.status_code == 200
        assert r.json() == {"players": []}
        svc.return_value.get_rotation_analysis.assert_called_once_with(
            "col", "7", "Foo", min_games=2, min_total_min=30.0,
        )

    def test_team_name_is_required(self, client):
        assert client.get(f"{V1}/col/7").status_code == 422

    def test_negative_min_games_rejected(self, client):
        assert client.get(f"{V1}/col/7?team_name=Foo&min_games=-1").status_code == 422


class TestRotationStream:
    def test_streams_progress_then_result(self, client):
        def fake(collection, team_id, team_name, progress_callback=None, **kw):
            progress_callback(1, 2)
            progress_callback(2, 2)
            return {"players": [1]}

        with patch(SVC) as svc:
            svc.return_value.get_rotation_analysis.side_effect = fake
            r = client.get(f"{V1}/col/7/stream?team_name=Foo")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        events = _events(r.text)
        assert [e["progress"] for e in events if "progress" in e] == [50, 100]
        assert events[-1] == {"done": True, "result": {"players": [1]}}

    def test_service_error_becomes_done_error_event(self, client):
        with patch(SVC) as svc:
            svc.return_value.get_rotation_analysis.side_effect = RuntimeError("boom")
            r = client.get(f"{V1}/col/7/stream?team_name=Foo")
        assert r.status_code == 200
        assert _events(r.text)[-1] == {"done": True, "error": "boom"}
