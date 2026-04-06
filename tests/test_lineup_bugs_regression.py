"""Regression tests for lineup analysis bug fixes.

Bug 1 (Error 500): MongoDBHandler.get_lineup_analysis() did not accept the
    ``include_game_log`` keyword argument, causing a TypeError / HTTP 500 on
    every lineup analysis request after ``include_game_log`` was added to the
    router and service layers but not to the handler wrapper.

Bug 2 (no data with 23 games): The frontend passed ``team_name`` as the URL
    path segment ``{team_id}``.  Repository methods filter games by numeric
    team ID (``HEADER.TEAM.id`` for FEB, ``stats.teams.teamIdIntern`` for
    FBCYL), so passing a name string matched zero documents and the endpoint
    returned an empty list.  The API-level fix is to validate that the handler
    correctly receives and forwards ``team_id`` (not ``team_name``), and the
    ``team_id`` field is now exposed in the team-stats response so the frontend
    can look it up.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db

V1 = "/api/v1"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LINEUP_ROW = {
    "player_names": ["Ana", "Bea"],
    "player_ids": ["1", "2"],
    "minutes": 25.0,
    "games_played": 7,
    "avg_minutes_per_game": 3.6,
    "points_for": 60,
    "points_against": 50,
    "plus_minus": 10,
    "possessions": 48.0,
    "ortg": 125.0,
    "drtg": 104.2,
    "net_rating": 20.8,
    "efg_pct": 55.0,
    "tov_pct": 12.0,
    "orb_pct": 30.0,
    "ftr": 0.22,
    "fgm": 22,
    "fga": 40,
    "fg3m": 6,
    "fg3a": 14,
    "ftm": 8,
    "fta": 10,
    "orb": 8,
    "drb": 16,
    "trb": 24,
    "ast": 12,
    "stl": 6,
    "blk": 2,
    "tov": 5,
    "pf": 9,
}

LINEUP_ROW_WITH_LOG = dict(LINEUP_ROW, game_log=[
    {"date": "2025-10-01", "net_rating": 18.0, "ortg": 120.0, "drtg": 102.0,
     "plus_minus": 8, "points_for": 28, "points_against": 20,
     "efg_pct": 54.0, "tov_pct": 11.0, "orb_pct": 28.0,
     "ftr": 0.20, "ast": 5, "trb": 10, "minutes": 12.0},
    {"date": "2025-10-08", "net_rating": 22.0, "ortg": 128.0, "drtg": 106.0,
     "plus_minus": 12, "points_for": 32, "points_against": 20,
     "efg_pct": 56.0, "tov_pct": 13.0, "orb_pct": 32.0,
     "ftr": 0.24, "ast": 7, "trb": 14, "minutes": 13.0},
])


def _mock_db(lineups=None, lineups_with_log=None):
    """Return a MagicMock db handler pre-configured for lineup tests."""
    handler = MagicMock()
    handler.is_connected.return_value = True
    handler.get_lineup_analysis.return_value = lineups or [LINEUP_ROW]
    # team stats: include team_id so frontend can resolve it
    handler.get_team_stats.return_value = [
        {"team_name": "Club A", "team_id": 42, "_id": {"team_id": 42, "team_name": "Club A"}}
    ]
    handler.get_opponent_stats.return_value = []
    return handler


# ---------------------------------------------------------------------------
# Bug 1 regression — include_game_log keyword must not raise TypeError (500)
# ---------------------------------------------------------------------------

class TestIncludeGameLogRegression:
    """Bug: MongoDBHandler wrapper missing include_game_log → HTTP 500."""

    def test_handler_accepts_include_game_log_kwarg(self):
        """Handler must accept include_game_log without TypeError.

        Before the fix, calling::

            handler.get_lineup_analysis(..., include_game_log=True)

        raised ``TypeError: unexpected keyword argument 'include_game_log'``
        because the MongoDBHandler wrapper did not declare that parameter.
        """
        from src.database import MongoDBHandler

        handler = MagicMock(spec=MongoDBHandler)
        # The real method signature must accept include_game_log
        import inspect
        sig = inspect.signature(MongoDBHandler.get_lineup_analysis)
        assert "include_game_log" in sig.parameters, (
            "MongoDBHandler.get_lineup_analysis must expose 'include_game_log' parameter"
        )

    def test_handler_forwards_include_game_log_to_repository(self):
        """Handler must forward include_game_log=True to the repository mixin."""
        from src.database import MongoDBHandler

        mock_repo = MagicMock()
        mock_repo.get_lineup_analysis.return_value = [LINEUP_ROW_WITH_LOG]

        handler = MagicMock(spec=MongoDBHandler)
        handler.repository = mock_repo

        # Simulate what the real handler delegates
        real_handler = MongoDBHandler.__new__(MongoDBHandler)
        real_handler.repository = mock_repo

        real_handler.get_lineup_analysis(
            "FEB_LF2_2025_A", "42", "Club A",
            combination_size=5,
            include_game_log=True,
        )

        # Repository must have been called with include_game_log=True
        assert mock_repo.get_lineup_analysis.called
        _, kwargs = mock_repo.get_lineup_analysis.call_args
        args = mock_repo.get_lineup_analysis.call_args[0]
        # include_game_log is the 7th positional arg (index 6) or a kwarg
        passed_as_kwarg = kwargs.get("include_game_log")
        passed_as_positional = args[6] if len(args) > 6 else None
        assert passed_as_kwarg is True or passed_as_positional is True, (
            "include_game_log=True was not forwarded to the repository"
        )

    def test_api_endpoint_returns_200_with_include_game_log(self):
        """GET /{collection}/{team_id}?include_game_log=true must return 200.

        Before the fix this returned 500 due to the TypeError in the handler.
        """
        db = _mock_db(lineups=[LINEUP_ROW_WITH_LOG])
        db.get_lineup_analysis.return_value = [LINEUP_ROW_WITH_LOG]
        app.dependency_overrides[get_db] = lambda: db

        try:
            client = TestClient(app)
            resp = client.get(
                f"{V1}/lineups/FEB_LF2_2025_A/42"
                "?team_name=Club+A&size=5&include_game_log=true"
            )
            assert resp.status_code == 200, (
                f"Expected 200 but got {resp.status_code}: {resp.text}"
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_service_normalises_player_names_to_players(self):
        """Service must rename player_names → players for the frontend.

        The repository stores the resolved names in 'player_names' but the
        frontend LineupRow interface (and all renderRow calls) uses 'players'.
        Without the normalisation the Combinación cell would be empty/crash.
        """
        db = _mock_db()
        # Repository returns player_names, not players
        row_with_player_names = dict(LINEUP_ROW)
        row_with_player_names.pop("players", None)
        row_with_player_names["player_names"] = ["Ana García", "Bea López"]
        db.get_lineup_analysis.return_value = [row_with_player_names]
        app.dependency_overrides[get_db] = lambda: db

        try:
            client = TestClient(app)
            resp = client.get(f"{V1}/lineups/FEB_LF2_2025_A/42?team_name=Club+A")
            assert resp.status_code == 200
            row = resp.json()[0]
            assert "players" in row, "Response must include 'players' field"
            assert row["players"] == ["Ana García", "Bea López"]
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_api_endpoint_game_log_absent_when_not_requested(self):
        """game_log must not appear in response by default (include_game_log=false)."""
        db = _mock_db(lineups=[LINEUP_ROW])
        app.dependency_overrides[get_db] = lambda: db

        try:
            client = TestClient(app)
            resp = client.get(
                f"{V1}/lineups/FEB_LF2_2025_A/42?team_name=Club+A"
            )
            assert resp.status_code == 200
            row = resp.json()[0]
            assert "game_log" not in row or row["game_log"] is None, (
                "game_log should not be present when include_game_log=false"
            )
        finally:
            app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Bug 2 regression — team_id (numeric) vs team_name in API call
# ---------------------------------------------------------------------------

class TestTeamIdVsTeamNameRegression:
    """Bug: frontend sent team_name as URL team_id → zero games matched → empty results."""

    def test_team_stats_response_includes_team_id_field(self):
        """TeamStat response must expose team_id so the frontend can resolve it.

        The frontend previously had no ``team_id`` in the TypeScript
        ``TeamStat`` type and the teams API did not guarantee it in the
        response.  Without it the frontend could only pass ``team_name`` to the
        lineup endpoint, which matched no documents in MongoDB.
        """
        db = _mock_db()
        app.dependency_overrides[get_db] = lambda: db

        try:
            client = TestClient(app)
            resp = client.get(f"{V1}/teams/FEB_LF2_2025_A")
            assert resp.status_code == 200
            team_stats = resp.json().get("team_stats", [])
            assert team_stats, "team_stats must not be empty"
            assert "team_id" in team_stats[0], (
                "team_stats entries must include 'team_id' so the frontend "
                "can pass the correct numeric ID to the lineups endpoint"
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_lineup_endpoint_called_with_numeric_team_id(self):
        """Lineup endpoint must receive team_id, not team_name, in the URL path.

        Before the fix the frontend sent::

            GET /lineups/{collection}/Club+A?team_name=Club+A

        which caused ``get_games_for_team("Club A")`` to match zero documents
        because the repo filters on numeric ``HEADER.TEAM.id`` (FEB) or
        ``stats.teams.teamIdIntern`` (FBCYL).

        After the fix the frontend sends::

            GET /lineups/{collection}/42?team_name=Club+A

        This test simulates both calls and asserts the handler receives the
        correct value in the ``team_id`` positional argument.
        """
        # --- Broken call: passing team_name as team_id path segment ---
        db_bad = _mock_db(lineups=[])
        db_bad.get_lineup_analysis.return_value = []
        app.dependency_overrides[get_db] = lambda: db_bad

        try:
            client = TestClient(app)
            resp_bad = client.get(
                f"{V1}/lineups/FEB_LF2_2025_A/Club%20A?team_name=Club+A&size=5"
            )
            assert resp_bad.status_code == 200
            # Capture what team_id the handler received
            call_args_bad = db_bad.get_lineup_analysis.call_args
            team_id_bad = call_args_bad[0][1] if call_args_bad[0] else call_args_bad[1].get("team_id")
        finally:
            app.dependency_overrides.pop(get_db, None)

        # --- Correct call: passing numeric id as team_id path segment ---
        db_good = _mock_db(lineups=[LINEUP_ROW])
        app.dependency_overrides[get_db] = lambda: db_good

        try:
            client = TestClient(app)
            resp_good = client.get(
                f"{V1}/lineups/FEB_LF2_2025_A/42?team_name=Club+A&size=5"
            )
            assert resp_good.status_code == 200
            call_args_good = db_good.get_lineup_analysis.call_args
            team_id_good = call_args_good[0][1] if call_args_good[0] else call_args_good[1].get("team_id")
        finally:
            app.dependency_overrides.pop(get_db, None)

        # The broken call received the team name; the correct call received "42"
        assert team_id_bad == "Club A", (
            f"Sanity check: broken call should pass team_name, got {team_id_bad!r}"
        )
        assert team_id_good == "42", (
            f"Correct call must pass numeric id '42', got {team_id_good!r}"
        )

    def test_stat_param_invalid_returns_400(self):
        """Passing an unknown stat must return 400, not 500."""
        db = _mock_db()
        app.dependency_overrides[get_db] = lambda: db

        try:
            client = TestClient(app)
            resp = client.get(
                f"{V1}/lineups/FEB_LF2_2025_A/42?team_name=Club+A&stat=invalid_stat"
            )
            assert resp.status_code == 400, (
                f"Invalid stat should return 400, got {resp.status_code}"
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
