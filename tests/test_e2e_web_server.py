"""The API server used by the web smoke e2e (issue #111) must keep working: real app on mongomock."""
import importlib.util
import sys
from pathlib import Path

import mongomock
import pytest
from fastapi.testclient import TestClient

SERVER = Path(__file__).parent / "e2e_web" / "serve_api.py"


@pytest.fixture()
def client(monkeypatch):
    import pymongo

    from src.api import deps
    from src.api.app import app

    monkeypatch.setattr(pymongo, "MongoClient", mongomock.MongoClient)
    deps._create_handler.cache_clear()
    spec = importlib.util.spec_from_file_location("serve_api", SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.seed(deps._create_handler().connection.client)
    yield TestClient(app), module.COLLECTION
    deps._create_handler.cache_clear()
    sys.modules.pop("serve_api", None)


def test_seeded_competition_is_listed_and_the_internal_collection_is_not(client):
    http, name = client
    names = [c["name"] for c in http.get("/api/v1/collections/list").json()]
    assert names == [name]


def test_pages_of_the_smoke_have_data(client):
    http, name = client
    assert http.get("/api/v1/health/db").json()["connected"] is True
    assert http.get(f"/api/v1/teams/{name}").json()["team_stats"]
    assert len(http.get(f"/api/v1/possessions/{name}").json()) >= 2
