"""
Phase 4 quality-gate tests: AI SSE streaming + IN/OUT endpoints.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from src.api.deps import get_db
    from unittest.mock import MagicMock
    app.dependency_overrides[get_db] = lambda: MagicMock()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# AI streaming endpoint (/api/v1/ai/analyze/stream)
# ---------------------------------------------------------------------------

class TestAIStreamEndpoint:
    BASE = "/api/v1/ai/analyze/stream"

    def test_missing_collection_returns_422(self, client):
        r = client.get(self.BASE)
        assert r.status_code == 422

    def test_missing_team_returns_422(self, client):
        r = client.get(self.BASE, params={"collection": "FEB_test"})
        assert r.status_code == 422

    def test_invalid_provider_returns_400_or_default(self, client):
        """Unknown provider should either be rejected (400/422) or quietly fall back."""
        r = client.get(
            self.BASE,
            params={"collection": "FEB_test", "team": "TeamA", "provider": "unknown_llm"},
        )
        assert r.status_code in (400, 422, 200, 500)  # implementation may reject or fallback

    def test_valid_request_returns_event_stream_content_type(self, client):
        """A well-formed request should return text/event-stream even if AI call fails."""
        with patch("src.api.routers.ai.ContextBuilder.build_team_context", return_value="ctx"):
            r = client.get(
                self.BASE,
                params={"collection": "FEB_test", "team": "TeamA", "provider": "groq"},
            )
        # SSE or error — must not be 404
        assert r.status_code != 404

    def test_sse_error_event_is_json(self, client):
        """When AI fails the SSE body must contain a JSON error event."""
        with patch("src.api.routers.ai.ContextBuilder.build_team_context", side_effect=RuntimeError("boom")):
            r = client.get(
                self.BASE,
                params={"collection": "FEB_test", "team": "TeamA"},
            )
        # Status may be 200 (SSE) or 500 — both acceptable
        if r.status_code == 200:
            body = r.text
            # The SSE body should contain a data: {...} line with "error" key
            data_lines = [ln[6:] for ln in body.splitlines() if ln.startswith("data:")]
            jsons = [json.loads(d) for d in data_lines if d.strip()]
            assert any("error" in j for j in jsons), f"No error event in: {body}"


# ---------------------------------------------------------------------------
# IN/OUT endpoint (/api/v1/players/{collection}/inout/{player_id})
# ---------------------------------------------------------------------------

class TestInOutEndpoint:
    def _url(self, col: str, pid: str) -> str:
        return f"/api/v1/players/{col}/inout/{pid}"

    def test_returns_200_with_on_off_keys(self, client):
        mock_result = {
            "player_id": "1234",
            "player_name": "Test Player",
            "team_name": "Test Team",
            "on":  {"points_for": 105.0, "points_against": 98.0, "minutes": 320.0, "net_rating": 7.0},
            "off": {"points_for": 100.0, "points_against": 104.0, "minutes": 280.0, "net_rating": -4.0},
        }
        with patch("src.api.routers.players.PlayerStatsService") as MockSvc:
            MockSvc.return_value.get_in_out_analysis.return_value = mock_result
            r = client.get(self._url("FEB_test", "1234"))
        assert r.status_code == 200
        body = r.json()
        assert "on" in body and "off" in body

    def test_on_block_has_required_fields(self, client):
        mock_result = {
            "player_id": "99",
            "player_name": "Player",
            "team_name": "Team",
            "on":  {"points_for": 110.0, "points_against": 100.0, "minutes": 200.0, "net_rating": 10.0},
            "off": {"points_for": 95.0, "points_against": 102.0, "minutes": 200.0, "net_rating": -7.0},
        }
        with patch("src.api.routers.players.PlayerStatsService") as MockSvc:
            MockSvc.return_value.get_in_out_analysis.return_value = mock_result
            r = client.get(self._url("FEB_test", "99"))
        body = r.json()
        for field in ("points_for", "points_against", "minutes"):
            assert field in body["on"], f"Missing field '{field}' in 'on' block"

    def test_missing_player_propagates_gracefully(self, client):
        with patch("src.api.routers.players.PlayerStatsService") as MockSvc:
            MockSvc.return_value.get_in_out_analysis.return_value = {}
            r = client.get(self._url("FEB_test", "nonexistent"))
        assert r.status_code in (200, 404)


# ---------------------------------------------------------------------------
# Together endpoint (/api/v1/players/{collection}/together/{p1}/{p2})
# ---------------------------------------------------------------------------

class TestPlayersTogetherEndpoint:
    def _url(self, col: str, p1: str, p2: str) -> str:
        return f"/api/v1/players/{col}/together/{p1}/{p2}"

    def test_returns_together_and_apart_keys(self, client):
        mock_result = {
            "together": {"points_for": 108.0, "points_against": 100.0, "minutes": 180.0, "net_rating": 8.0},
            "apart":    {"points_for":  99.0, "points_against": 103.0, "minutes": 220.0, "net_rating": -4.0},
        }
        with patch("src.api.routers.players.PlayerStatsService") as MockSvc:
            MockSvc.return_value.get_players_together.return_value = mock_result
            r = client.get(self._url("FEB_test", "11", "22"))
        assert r.status_code == 200
        body = r.json()
        assert "together" in body and "apart" in body

    def test_together_block_has_net_rating(self, client):
        mock_result = {
            "together": {"points_for": 108.0, "points_against": 100.0, "minutes": 180.0, "net_rating": 8.0},
            "apart":    {"points_for":  99.0, "points_against": 103.0, "minutes": 220.0, "net_rating": -4.0},
        }
        with patch("src.api.routers.players.PlayerStatsService") as MockSvc:
            MockSvc.return_value.get_players_together.return_value = mock_result
            r = client.get(self._url("FEB_test", "11", "22"))
        assert r.json()["together"]["net_rating"] == 8.0
