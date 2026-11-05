"""``GET /api/v1/health`` tells which commit is serving, when the environment says it (``GIT_COMMIT``)."""
from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


def test_reports_the_commit_the_environment_gives(monkeypatch):
    monkeypatch.setenv("GIT_COMMIT", "abc123def")
    body = client.get("/api/v1/health").json()
    assert body == {"status": "ok", "commit": "abc123def"}


def test_commit_is_null_when_the_environment_gives_none(monkeypatch):
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    assert client.get("/api/v1/health").json() == {"status": "ok", "commit": None}


def test_needs_no_database(monkeypatch):
    from src.api import deps

    def boom():
        raise RuntimeError("no db")

    monkeypatch.setattr(deps, "_create_handler", boom)
    assert client.get("/api/v1/health").status_code == 200
