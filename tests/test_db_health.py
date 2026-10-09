"""Database failures must be visible, not a bare HTTP 500 (found on production 2026-10-09).

Production returned ``500 Internal Server Error`` on every database endpoint while ``/`` worked:
the handler could not be built (``MONGODB_CONNECTION_STRING`` missing or the credentials rejected)
and the exception escaped. Now: 503 with an actionable message, a public ``/health/db`` and a
connection class that survives any PyMongo error.
"""
from unittest.mock import MagicMock, patch

import pymongo.errors as pme
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.db_health import classify_db_error

MISSING = RuntimeError("MONGODB_CONNECTION_STRING env var is required in production. Set it ...")


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestClassify:
    @pytest.mark.parametrize("exc, kind", [
        (MISSING, "missing_config"),
        (pme.OperationFailure("bad auth : Authentication failed.", code=18), "auth_failed"),
        (pme.OperationFailure("not authorized on BASKETBALL", code=13), "not_authorized"),
        (pme.ServerSelectionTimeoutError("no servers"), "unreachable"),
        (pme.ConfigurationError("bad uri"), "invalid_config"),
        (ValueError("???"), "error"),
    ])
    def test_kinds(self, exc, kind):
        assert classify_db_error(exc) == kind

    def test_messages_never_leak_credentials_or_hosts(self):
        text = classify_db_error(pme.OperationFailure("mongodb+srv://user:S3CRET@cluster0.abc.mongodb.net failed", code=18))
        assert "S3CRET" not in text and "cluster0" not in text


class TestGetDb:
    def test_missing_configuration_is_a_503_with_an_actionable_message_regression(self, client):
        from src.api import deps

        with patch.object(deps, "_create_handler", side_effect=MISSING):
            r = client.get("/api/v1/collections/list")
        assert r.status_code == 503
        assert "MONGODB_CONNECTION_STRING" in r.json()["detail"]

    def test_rejected_credentials_are_a_503_not_a_500(self, client):
        from src.api import deps

        with patch.object(deps, "_create_handler", side_effect=pme.OperationFailure("bad auth", code=18)):
            r = client.get("/api/v1/collections/list")
        assert r.status_code == 503 and "autenticación" in r.json()["detail"].lower()

    def test_a_working_handler_is_unaffected(self, client):
        from src.api import deps

        handler = MagicMock()
        handler.is_connected.return_value = True
        handler.connection.get_database.return_value.list_collection_names.return_value = []
        with patch.object(deps, "_create_handler", return_value=handler):
            assert client.get("/api/v1/collections/list").status_code == 200


class TestConnection:
    def test_an_authentication_failure_does_not_crash_the_constructor_regression(self):
        from src.database.connection import MongoDBConnection

        with patch("pymongo.MongoClient") as mc:
            mc.return_value.server_info.side_effect = pme.OperationFailure("bad auth", code=18)
            conn = MongoDBConnection("mongodb://x")
        assert conn.is_connected() is False and conn.last_error_kind == "auth_failed"

    def test_an_unreachable_server_is_still_handled(self):
        from src.database.connection import MongoDBConnection

        with patch("pymongo.MongoClient") as mc:
            mc.return_value.server_info.side_effect = pme.ServerSelectionTimeoutError("down")
            conn = MongoDBConnection("mongodb://x")
        assert conn.is_connected() is False and conn.last_error_kind == "unreachable"


class TestHealthEndpoint:
    def test_connected(self, client):
        from src.api import deps

        handler = MagicMock()
        handler.is_connected.return_value = True
        handler.connection.get_database.return_value.list_collection_names.return_value = ["A", "B", "HISTORICAL"]
        with patch.object(deps, "_create_handler", return_value=handler):
            r = client.get("/api/v1/health/db")
        assert r.status_code == 200 and r.json()["connected"] is True and r.json()["collections"] == 3
        assert r.json()["latency_ms"] >= 0

    def test_missing_configuration_is_reported_with_its_kind(self, client):
        from src.api import deps

        with patch.object(deps, "_create_handler", side_effect=MISSING):
            r = client.get("/api/v1/health/db")
        assert r.status_code == 503
        body = r.json()
        assert body["connected"] is False and body["error"] == "missing_config" and "MONGODB_CONNECTION_STRING" in body["hint"]

    def test_disconnected_handler_reports_the_kind_the_connection_recorded(self, client):
        from src.api import deps

        handler = MagicMock()
        handler.is_connected.return_value = False
        handler.connection.last_error_kind = "auth_failed"
        with patch.object(deps, "_create_handler", return_value=handler):
            r = client.get("/api/v1/health/db")
        assert r.status_code == 503 and r.json()["error"] == "auth_failed"

    def test_the_endpoint_is_public_and_leaks_nothing(self, client):
        from src.api import deps

        with patch.object(deps, "_create_handler", side_effect=pme.OperationFailure("mongodb+srv://u:PW@host/db", code=18)):
            r = client.get("/api/v1/health/db")
        assert "PW" not in r.text and "host" not in r.text
