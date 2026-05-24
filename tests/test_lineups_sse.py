"""Tests for the lineup SSE streaming endpoint.

Covers:
- GET /{collection}/{team_id}/stream returns 200 with text/event-stream
- SSE stream sends at least one 'data:' line
- Final event carries done=true and a result list
- Invalid stat param returns 400
- Progress events are emitted when the callback fires
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db

V1 = "/api/v1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_db():
    db = MagicMock()
    return db


@pytest.fixture()
def client(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_sse(raw: str) -> list:
    """Parse raw SSE text into list of parsed JSON objects."""
    events = []
    for line in raw.splitlines():
        if line.startswith("data: "):
            payload = line[len("data: "):]
            try:
                events.append(json.loads(payload))
            except json.JSONDecodeError:
                pass
    return events


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLineupStreamEndpoint:
    """SSE streaming endpoint for lineup analysis."""

    def test_stream_returns_200_event_stream(self, client):
        """/stream endpoint must return HTTP 200 with text/event-stream."""
        with patch("src.api.routers.lineups.LineupService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.get_lineup_analysis.return_value = []
            mock_svc_cls.return_value = mock_svc

            resp = client.get(
                f"{V1}/lineups/TEST_COL/T1/stream",
                params={"team_name": "Test Team", "size": 5, "stat": "net_rating"},
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_stream_contains_done_event(self, client):
        """Final SSE event must include done=true and a result array."""
        with patch("src.api.routers.lineups.LineupService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.get_lineup_analysis.return_value = [{"players": ["A", "B"], "net_rating": 5.0}]
            mock_svc_cls.return_value = mock_svc

            resp = client.get(
                f"{V1}/lineups/TEST_COL/T1/stream",
                params={"team_name": "Test Team"},
            )

        events = _parse_sse(resp.text)
        done_events = [e for e in events if e.get("done") is True]
        assert done_events, "At least one done=true event must be emitted"
        assert "result" in done_events[-1], "done event must contain 'result' key"

    def test_stream_result_matches_service_return(self, client):
        """result in done event must be the lineup list returned by the service."""
        expected = [{"players": ["X", "Y", "Z"], "net_rating": 3.5}]
        with patch("src.api.routers.lineups.LineupService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.get_lineup_analysis.return_value = expected
            mock_svc_cls.return_value = mock_svc

            resp = client.get(
                f"{V1}/lineups/TEST_COL/T1/stream",
                params={"team_name": "Test Team"},
            )

        events = _parse_sse(resp.text)
        done = next(e for e in events if e.get("done"))
        assert done["result"] == expected

    def test_stream_invalid_stat_returns_400(self, client):
        """Invalid stat should return 400 before starting any stream."""
        resp = client.get(
            f"{V1}/lineups/TEST_COL/T1/stream",
            params={"team_name": "Test Team", "stat": "INVALID_STAT"},
        )
        assert resp.status_code == 400

    def test_stream_emits_progress_events(self, client):
        """Progress events with 'progress' key must be emitted during processing."""
        def _analysis_with_progress(col, tid, tname, **kwargs):
            cb = kwargs.get("progress_callback")
            if cb:
                cb(1, 10)
                cb(5, 10)
                cb(10, 10)
            return []

        with patch("src.api.routers.lineups.LineupService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.get_lineup_analysis.side_effect = _analysis_with_progress
            mock_svc_cls.return_value = mock_svc

            resp = client.get(
                f"{V1}/lineups/TEST_COL/T1/stream",
                params={"team_name": "Test Team"},
            )

        events = _parse_sse(resp.text)
        progress_events = [e for e in events if "progress" in e]
        assert progress_events, "At least one progress event must be emitted"
        # Progress values should be in 0–100 range
        for ev in progress_events:
            assert 0 <= ev["progress"] <= 100

    def test_stream_error_propagated_in_done_event(self, client):
        """Service errors must surface as done=true with error key (not 500)."""
        with patch("src.api.routers.lineups.LineupService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.get_lineup_analysis.side_effect = RuntimeError("simulated DB error")
            mock_svc_cls.return_value = mock_svc

            resp = client.get(
                f"{V1}/lineups/TEST_COL/T1/stream",
                params={"team_name": "Test Team"},
            )

        assert resp.status_code == 200  # SSE always starts 200
        events = _parse_sse(resp.text)
        done = next((e for e in events if e.get("done")), None)
        assert done is not None
        assert "error" in done, "Error must appear in done event, not as HTTP 500"
