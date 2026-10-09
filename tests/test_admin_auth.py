"""Admin API key protecting destructive / ingestion / training endpoints (issue #115).

Policy: set ``ADMIN_API_KEY`` and send it as ``X-Admin-Key``. Without the variable the
protected routes are open in development (local use) and closed (503) in production.
"""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db
from src.api.scraper_app import app as scraper_app

PROTECTED = [
    ("DELETE", "/api/v1/collections/FEB_X", None),
    ("POST", "/api/v1/scrape/start", {}),
    ("POST", "/api/v1/historical/ingest", {}),
    ("POST", "/api/v1/historical/ingest_competition", {}),
    ("POST", "/api/v1/analysis/elasticity/train", {}),
    ("POST", "/api/v1/analysis/elasticity/train/stream", {}),
]
BLOCKED = {401, 403, 503}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)


@pytest.fixture()
def client():
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
    def test_reads_do_not_need_the_key(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_API_KEY", "s3cret")
        monkeypatch.setenv("ENVIRONMENT", "production")
        r = client.get("/api/v1/collections")
        assert r.status_code not in BLOCKED

    def test_compute_only_posts_stay_public(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_API_KEY", "s3cret")
        r = client.post("/api/v1/reports/export-pdf", json={"html": "<p>x</p>", "team": "A"})
        assert r.status_code not in BLOCKED


class TestScraperService:
    """The separate scraper app mounts the same routers and must be protected too."""

    def test_scraper_app_requires_the_key(self, monkeypatch):
        monkeypatch.setenv("ADMIN_API_KEY", "s3cret")
        scraper_app.dependency_overrides[get_db] = lambda: MagicMock()
        try:
            c = TestClient(scraper_app)
            assert c.delete("/api/v1/collections/FEB_X").status_code == 401
            assert c.post("/api/v1/scrape/start", json={}).status_code == 401
            ok = c.delete("/api/v1/collections/FEB_X", headers={"X-Admin-Key": "s3cret"})
            assert ok.status_code not in BLOCKED
        finally:
            scraper_app.dependency_overrides.clear()


def test_key_is_read_at_request_time_not_import_time(client, monkeypatch):
    assert _call(client, "DELETE", "/api/v1/collections/FEB_X", None).status_code not in BLOCKED
    monkeypatch.setenv("ADMIN_API_KEY", "late")
    assert _call(client, "DELETE", "/api/v1/collections/FEB_X", None).status_code == 401


def test_cors_allows_the_admin_header():
    r = TestClient(app).options(
        "/api/v1/collections/FEB_X",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "DELETE",
                 "Access-Control-Request-Headers": "x-admin-key"},
    )
    assert r.status_code == 200
    assert "x-admin-key" in r.headers.get("access-control-allow-headers", "").lower() or \
        r.headers.get("access-control-allow-headers") == "x-admin-key"


# Write endpoints deliberately left public: compute-only (nothing persisted or destroyed).
PUBLIC_WRITE_ROUTES = {
    ("POST", "/api/v1/reports/export-pdf"),
    ("POST", "/api/v1/reports/{collection}/weekly-report"),
    ("POST", "/api/v1/analysis/montecarlo/{team_id}"),
    ("POST", "/api/v1/analysis/game-prediction/{team_id}"),
    # builds + encrypts a live preparation package: compute only, single-flight (src/api/routers/live_package.py)
    ("POST", "/api/v1/live/package"),
}


def _has_admin_guard(route) -> bool:
    from src.api.security import require_admin

    return any(d.call is require_admin for d in route.dependant.dependencies)


@pytest.mark.parametrize("application", [app, scraper_app], ids=["api", "scraper"])
def test_every_write_route_is_protected_or_explicitly_public(application):
    """New POST/PUT/PATCH/DELETE endpoints must take ``Depends(require_admin)`` or be added
    (consciously) to PUBLIC_WRITE_ROUTES above."""
    unclassified = []
    for route in application.routes:
        methods = (getattr(route, "methods", None) or set()) - {"GET", "HEAD", "OPTIONS"}
        if not methods or not hasattr(route, "dependant"):
            continue
        for m in methods:
            if (m, route.path) not in PUBLIC_WRITE_ROUTES and not _has_admin_guard(route):
                unclassified.append((m, route.path))
    assert unclassified == []
