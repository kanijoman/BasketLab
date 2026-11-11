"""Admin API key, the guard of a write endpoint (issue #115). No endpoint uses it today: the destructive and ingestion ones were retired (#724) and the training ones with the old predictive
analysis (#853). It stays as the PATTERN for the next write endpoint, so it is tested on a small app that has one.

Policy: set ``ADMIN_API_KEY`` and send it as ``X-Admin-Key``. Without the variable the
protected routes are open in development (local use) and closed (503) in production.
"""
from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api_routes import api_operations, takes_the_admin_key
from src.api.app import app
from src.api.deps import get_db
from src.api.security import require_admin

PROTECTED = [("POST", "/api/v1/write", {}), ("POST", "/api/v1/write/stream", {})]
GUARDED = FastAPI()


@GUARDED.post("/api/v1/write", dependencies=[Depends(require_admin)])
@GUARDED.post("/api/v1/write/stream", dependencies=[Depends(require_admin)])
def _write():
    return {"done": True}


BLOCKED = {401, 403, 503}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)


@pytest.fixture()
def client():
    """The small app with two guarded endpoints (the real one has none)."""
    return TestClient(GUARDED)


@pytest.fixture()
def api():
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _call(client, method, path, body, headers=None):
    return client.request(method, path, json=body, headers=headers or {})


@pytest.mark.parametrize("method, path, body", PROTECTED)
class TestKeyConfigured:
    def test_missing_key_is_rejected(self, client, monkeypatch, method, path, body):
        monkeypatch.setenv("ADMIN_API_KEY", "s3cret")
        assert _call(client, method, path, body).status_code == 401

    def test_wrong_key_is_rejected(self, client, monkeypatch, method, path, body):
        monkeypatch.setenv("ADMIN_API_KEY", "s3cret")
        r = _call(client, method, path, body, {"X-Admin-Key": "nope"})
        assert r.status_code == 401

    def test_correct_key_passes_the_gate(self, client, monkeypatch, method, path, body):
        monkeypatch.setenv("ADMIN_API_KEY", "s3cret")
        r = _call(client, method, path, body, {"X-Admin-Key": "s3cret"})
        assert r.status_code not in BLOCKED


@pytest.mark.parametrize("method, path, body", PROTECTED)
class TestKeyNotConfigured:
    def test_open_in_development(self, client, method, path, body):
        assert _call(client, method, path, body).status_code not in BLOCKED

    def test_closed_in_production(self, client, monkeypatch, method, path, body):
        monkeypatch.setenv("ENVIRONMENT", "production")
        r = _call(client, method, path, body)
        assert r.status_code == 503
        assert "ADMIN_API_KEY" in r.json()["detail"]


class TestPublicRoutesStayPublic:
    def test_reads_do_not_need_the_key(self, api, monkeypatch):
        monkeypatch.setenv("ADMIN_API_KEY", "s3cret")
        monkeypatch.setenv("ENVIRONMENT", "production")
        r = api.get("/api/v1/collections")
        assert r.status_code not in BLOCKED

    def test_compute_only_posts_stay_public(self, api, monkeypatch):
        monkeypatch.setenv("ADMIN_API_KEY", "s3cret")
        r = api.post("/api/v1/scouting-rival", json={})          # an empty body: 422 from the validation, not 401/503 from the key
        assert r.status_code not in BLOCKED


# Write endpoints deliberately left public: compute-only (nothing persisted or destroyed).
PUBLIC_WRITE_ROUTES = {
    ("POST", "/api/v1/reports/{collection}/weekly-report"),
    # the rival scouting report of any team: compute only, single-flight (src/api/routers/scouting_rival.py)
    ("POST", "/api/v1/scouting-rival"),
}


def test_every_write_route_is_protected_or_explicitly_public():
    """New POST/PUT/PATCH/DELETE endpoints must take ``Depends(require_admin)`` or be added
    (consciously) to PUBLIC_WRITE_ROUTES above.

    Read from the OpenAPI schema: a loop over ``app.routes`` finds nothing in the FastAPI of the CI (included routers are nested there) and the check passed without checking."""
    assert all(takes_the_admin_key(op) for op in api_operations(GUARDED).values())                    # the detector does see a guarded operation
    operations = api_operations(app)
    unclassified = [
        (method, path) for (method, path), operation in operations.items()
        if method in {"POST", "PUT", "PATCH", "DELETE"} and (method, path) not in PUBLIC_WRITE_ROUTES and not takes_the_admin_key(operation)
    ]
    assert unclassified == []
