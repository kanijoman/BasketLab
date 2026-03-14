"""Regression tests for the /api/v1/ versioning migration (Phase 2).

These tests guard against:
1. The v1 prefix being removed — old /api/ paths must 404.
2. Team-stat response shape matching the TypeScript TeamStat interface.
3. Player-stat response shape matching the TypeScript PlayerStat interface.
4. Efficiency rating fields using the correct names (offensive_rating /
   defensive_rating / net_rating) instead of legacy oer/der.

All tests use the FastAPI TestClient with mocked DB so no MongoDB is needed.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db

V1 = "/api/v1"

# ---------------------------------------------------------------------------
# Minimal fake data matching the aggregation pipeline output shape
# ---------------------------------------------------------------------------

TEAM_ROW = {
    "_id": "team_001",
    "team_name": "Basket Club A",
    "total_games": 18,
    "games_home": 9,
    "games_away": 9,
    "points_per_game": 82.4,
    "points_against_per_game": 78.1,
    "possessions_per_game": 72.3,
    "rebounds_per_game": 34.2,
    "assists_per_game": 18.6,
    "steals_per_game": 7.1,
    "turnovers_per_game": 12.3,
    "blocks_per_game": 3.2,
    # shooting
    "fg2_percentage": 52.3,
    "fg3_percentage": 34.1,
    "ft_percentage": 74.8,
    # four factors
    "efg_percentage": 53.7,
    "turnover_rate": 14.2,
    "offensive_rebound_rate": 28.6,
    "free_throw_rate": 21.4,
    # advanced shooting
    "three_point_rate": 37.8,
    "true_shooting": 57.9,
    # playmaking
    "assist_fg_rate": 54.2,
    "assist_rate": 25.8,
    "steal_rate": 9.8,
    "block_rate": 4.4,
    # rebounding
    "defensive_rebound_rate": 71.2,
    # efficiency — correct names from advanced_stats.py
    "offensive_rating": 108.5,
    "defensive_rating": 103.2,
    "net_rating": 5.3,
}

PLAYER_ROW = {
    "player_id": "p001",
    "player_name": "Ana García",
    "team_name": "Basket Club A",
    "team_id": "team_001",
    "games_played": 18,
    "total_minutes": 540,
    "minutes_per_game": 30.0,
    "total_pts": 324,
    "total_p2m": 80,
    "total_p2a": 155,
    "total_p3m": 24,
    "total_p3a": 70,
    "total_p1m": 36,
    "total_p1a": 40,
    "total_assist": 72,
    "total_ro": 18,
    "total_rd": 54,
    "total_rt": 72,
    "total_st": 36,
    "total_to": 27,
    "total_bs": 9,
    "total_pf": 45,
    "total_val": 378,
    "total_pllss": 54,
    "points_per_game": 18.0,
    "rebounds_per_game": 4.0,
    "assists_per_game": 4.0,
    "steals_per_game": 2.0,
    "blocks_per_game": 0.5,
    "turnovers_per_game": 1.5,
    "valoracion_per_game": 21.0,
    "pllss_per_game": 3.0,
    "fg1_percentage": 90.0,
    "fg2_percentage": 51.6,
    "fg3_percentage": 34.3,
}


def _mock_db_with_data():
    handler = MagicMock()
    handler.is_connected.return_value = True
    handler.get_team_stats.return_value = [TEAM_ROW]
    handler.get_opponent_stats.return_value = [TEAM_ROW]
    handler.get_player_stats.return_value = [PLAYER_ROW]
    handler.get_all_teams.return_value = ["Basket Club A"]
    mock_coll = MagicMock()
    mock_coll.count_documents.return_value = 18
    handler.connection.get_collection.return_value = mock_coll
    return handler


@pytest.fixture
def client():
    db = _mock_db_with_data()
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 1: /api/v1/ prefix is mandatory — old prefix must return 404
# ---------------------------------------------------------------------------

class TestV1PrefixRequired:
    """Guard that the old /api/ prefix was removed and /api/v1/ is the only path."""

    def test_old_teams_prefix_returns_404(self, client):
        """Regression: /api/teams/ must not exist after v1 migration."""
        r = client.get("/api/teams/FEB_LF2_2025_A")
        assert r.status_code == 404, (
            f"Old prefix /api/teams/ should 404 after v1 migration, got {r.status_code}"
        )

    def test_old_players_prefix_returns_404(self, client):
        """Regression: /api/players/ must not exist after v1 migration."""
        r = client.get("/api/players/FEB_LF2_2025_A")
        assert r.status_code == 404

    def test_old_lineups_prefix_returns_404(self, client):
        """Regression: /api/lineups/ must not exist after v1 migration."""
        r = client.get("/api/lineups/FEB_LF2_2025_A/123?team_name=T")
        assert r.status_code == 404

    def test_old_collections_prefix_returns_404(self, client):
        """Regression: /api/collections/ must not exist after v1 migration."""
        r = client.get("/api/collections/?collection=FEB_LF2_2025_A")
        assert r.status_code == 404

    def test_v1_teams_returns_200(self, client):
        r = client.get(f"{V1}/teams/FEB_LF2_2025_A")
        assert r.status_code == 200

    def test_v1_players_returns_200(self, client):
        r = client.get(f"{V1}/players/FEB_LF2_2025_A")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Test 2: Team response shape — fields match TypeScript TeamStat interface
# ---------------------------------------------------------------------------

class TestTeamStatShape:
    """Verify the response payload contains the exact field names expected by
    the TypeScript TeamStat interface defined in frontend/src/api/client.ts."""

    def _get_first_team(self, client):
        r = client.get(f"{V1}/teams/FEB_LF2_2025_A")
        assert r.status_code == 200
        return r.json()["team_stats"][0]

    def test_response_contains_team_stats_and_opponent_stats_keys(self, client):
        r = client.get(f"{V1}/teams/FEB_LF2_2025_A")
        body = r.json()
        assert "team_stats" in body
        assert "opponent_stats" in body

    def test_team_name_field_present(self, client):
        row = self._get_first_team(client)
        assert "team_name" in row

    def test_basic_per_game_fields_present(self, client):
        row = self._get_first_team(client)
        for field in [
            "points_per_game", "points_against_per_game", "possessions_per_game",
            "rebounds_per_game", "assists_per_game", "steals_per_game",
            "turnovers_per_game", "blocks_per_game",
        ]:
            assert field in row, f"Missing required field: {field}"

    def test_shooting_percentage_fields_use_correct_names(self, client):
        """Regression: fields are fg2_percentage / fg3_percentage / ft_percentage
        (not field_goals_2_pct or free_throw_pct as typed in the old interface)."""
        row = self._get_first_team(client)
        assert "fg2_percentage" in row, "fg2_percentage missing — old name was field_goals_2_pct"
        assert "fg3_percentage" in row
        assert "ft_percentage"  in row

    def test_efficiency_rating_fields_use_correct_names(self, client):
        """Regression: advanced_stats.py outputs offensive_rating/defensive_rating/net_rating,
        NOT oer/der. The frontend and CollectionHub deriveHighlights() now use
        offensive_rating, so this field must be present."""
        row = self._get_first_team(client)
        assert "offensive_rating" in row, (
            "offensive_rating missing — CollectionHub.deriveHighlights() depends on this field"
        )
        assert "defensive_rating" in row
        assert "net_rating"       in row

    def test_four_factors_fields_present(self, client):
        row = self._get_first_team(client)
        for field in ["efg_percentage", "turnover_rate", "offensive_rebound_rate", "free_throw_rate"]:
            assert field in row, f"Four-factor field missing: {field}"

    def test_no_legacy_oer_der_fields_in_response(self, client):
        """Regression: legacy field names oer/der were removed from the TypeScript
        interface. The backend never emitted them, so they must not appear."""
        row = self._get_first_team(client)
        assert "oer" not in row, "Legacy field 'oer' must not be in response (use offensive_rating)"
        assert "der" not in row, "Legacy field 'der' must not be in response (use defensive_rating)"


# ---------------------------------------------------------------------------
# Test 3: Player response shape — fields match TypeScript PlayerStat interface
# ---------------------------------------------------------------------------

class TestPlayerStatShape:
    """Verify the response payload contains the field names expected by the
    TypeScript PlayerStat interface."""

    def _get_first_player(self, client):
        r = client.get(f"{V1}/players/FEB_LF2_2025_A")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) > 0
        return rows[0]

    def test_player_identity_fields_present(self, client):
        row = self._get_first_player(client)
        assert "player_name" in row
        assert "player_id"   in row
        assert "team_name"   in row

    def test_per_game_fields_present(self, client):
        row = self._get_first_player(client)
        for field in [
            "games_played", "minutes_per_game", "points_per_game",
            "rebounds_per_game", "assists_per_game",
        ]:
            assert field in row, f"Missing player per-game field: {field}"

    def test_shooting_percentage_field_names(self, client):
        """Regression: player shooting fields are fg1_percentage / fg2_percentage /
        fg3_percentage (NOT field_goals_2_pct as in the old interface)."""
        row = self._get_first_player(client)
        assert "fg2_percentage" in row, "fg2_percentage missing from player row"
        assert "fg3_percentage" in row
        # fg1 = free throw percentage
        assert "fg1_percentage" in row

    def test_valoracion_field_present(self, client):
        """valoracion_per_game is a FEB-specific stat that must survive the migration."""
        row = self._get_first_player(client)
        assert "valoracion_per_game" in row

    def test_pllss_field_present(self, client):
        """pllss_per_game (+/-) must be present."""
        row = self._get_first_player(client)
        assert "pllss_per_game" in row

    def test_total_fields_present(self, client):
        """Totals are used in the player SlideDrawer profile panel."""
        row = self._get_first_player(client)
        for field in ["total_pts", "total_minutes", "total_val"]:
            assert field in row, f"Total field missing for drawer: {field}"


# ---------------------------------------------------------------------------
# Test 4: Team quartiles shape
# ---------------------------------------------------------------------------

class TestTeamQuartilesShape:
    def test_quartiles_returns_dict(self, client):
        with patch("src.services.team_stats_service.TeamStatsAggregator") as MockAgg:
            MockAgg.return_value.calculate_league_quartiles.return_value = {
                "offensive_rating": {"q1": 96.0, "q2": 100.5, "q3": 106.2, "min": 88.0, "max": 115.0, "count": 18},
                "points_per_game":  {"q1": 70.0, "q2": 76.5,  "q3": 82.0,  "min": 60.0, "max": 94.0,  "count": 18},
            }
            r = client.get(f"{V1}/teams/FEB_LF2_2025_A/quartiles")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)

    def test_quartiles_includes_offensive_rating(self, client):
        """Regression: quartile map must contain offensive_rating so the frontend
        DataTable can colour-code the OER column."""
        with patch("src.services.team_stats_service.TeamStatsAggregator") as MockAgg:
            MockAgg.return_value.calculate_league_quartiles.return_value = {
                "offensive_rating": {"q1": 96.0, "q2": 100.5, "q3": 106.2},
            }
            r = client.get(f"{V1}/teams/FEB_LF2_2025_A/quartiles")
        data = r.json()
        assert "offensive_rating" in data, (
            "offensive_rating must be in quartiles for DataTable quartile colouring"
        )
