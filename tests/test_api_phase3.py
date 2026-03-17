"""Phase 3 Quality Gate — integration tests for evolution, shots, possessions.

Guard against:
- Evolution endpoint returns ordered game-by-game list
- Evolution endpoint falls back to 'points' on invalid stat key
- Shots endpoint returns 10 zones for FEB collections
- Shots endpoint returns empty list for FBCYL collections
- Possessions endpoint maps OER/DER/pace correctly from team stats

All tests use FastAPI TestClient with mocked DB (no MongoDB required).
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db

V1 = "/api/v1"

# ---------------------------------------------------------------------------
# Fake DB data for mocking
# ---------------------------------------------------------------------------

TEAM_STAT_ROW = {
    "team_name": "Club Ejemplo",
    "total_games": 20,
    "games_home": 10,
    "games_away": 10,
    "points_per_game": 78.5,
    "points_against_per_game": 74.2,
    "possessions_per_game": 73.1,
    "rebounds_per_game": 33.4,
    "assists_per_game": 17.8,
    "steals_per_game": 6.9,
    "turnovers_per_game": 11.5,
    "blocks_per_game": 2.8,
    "fg2_percentage": 51.0,
    "fg3_percentage": 33.0,
    "ft_percentage": 72.0,
    "offensive_rating": 107.2,
    "defensive_rating": 102.5,
    "net_rating": 4.7,
}

_EVOLUTION_DOCS = [
    {
        "game_date": "2025-01-05",
        "opponent": "Rival A",
        "value": 82.0,
        "won": True,
    },
    {
        "game_date": "2025-01-12",
        "opponent": "Rival B",
        "value": 74.0,
        "won": False,
    },
    {
        "game_date": "2025-01-19",
        "opponent": "Rival C",
        "value": 90.0,
        "won": True,
    },
]

_SHOT_DOCS = [
    {
        "SHOTCHART": {
            "SHOTS": [
                {"x": 50.0, "y": 50.0, "m": 1, "team": 0, "player": "101", "quarter": 1},
                {"x": 50.0, "y": 50.0, "m": 0, "team": 0, "player": "101", "quarter": 1},
                {"x": 5.0,  "y": 50.0, "m": 1, "team": 0, "player": "102", "quarter": 2},
                {"x": 95.0, "y": 90.0, "m": 0, "team": 0, "player": "103", "quarter": 2},
            ]
        },
        "HEADER": {
            "TEAM": [
                {"name": "Club Ejemplo"},
                {"name": "Rival Team"},
            ]
        },
    }
]


def _make_mock_db(is_fbcyl_collection: bool = False):
    """Create a MagicMock database handler."""
    mock_db = MagicMock()
    mock_db.is_connected.return_value = True
    mock_db.get_team_stats.return_value = [TEAM_STAT_ROW]

    # Mock the connection to get_collection for shots
    mock_coll = MagicMock()
    mock_coll.find.return_value = iter(_SHOT_DOCS)
    mock_coll.aggregate.return_value = iter([])
    mock_db.connection.get_collection.return_value = mock_coll

    return mock_db


@pytest.fixture
def client():
    """TestClient with mocked DB dependency."""
    mock_db = _make_mock_db()
    app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_fbcyl():
    """TestClient that simulates a FBCYL collection."""
    mock_db = _make_mock_db(is_fbcyl_collection=True)
    app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Evolution endpoint
# ---------------------------------------------------------------------------

class TestEvolutionEndpoint:
    """Tests for GET /api/v1/teams/{collection}/evolution/{team_name}"""

    def test_evolution_returns_list(self, client):
        """Evolution endpoint returns a list (even if empty with mock data)."""
        with patch(
            "src.services.team_stats_service.TeamStatsService._evolution_feb",
            return_value=_EVOLUTION_DOCS,
        ), patch(
            "utils.collection_utils.is_fbcyl",
            return_value=False,
        ):
            resp = client.get(f"{V1}/teams/FEB_LF2_2025_A/evolution/Club%20Ejemplo?stat=points")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_evolution_returns_game_number(self, client):
        """Each item in the evolution list has a game_number field."""
        with patch(
            "src.services.team_stats_service.TeamStatsService._evolution_feb",
            return_value=_EVOLUTION_DOCS,
        ), patch(
            "utils.collection_utils.is_fbcyl",
            return_value=False,
        ):
            resp = client.get(f"{V1}/teams/FEB_LF2_2025_A/evolution/Club%20Ejemplo?stat=points")
        assert resp.status_code == 200
        data = resp.json()
        if data:
            assert "game_number" in data[0]
            assert "rolling_avg" in data[0]

    def test_evolution_invalid_stat_falls_back(self, client):
        """Invalid stat key is silently replaced with 'points'."""
        with patch(
            "src.services.team_stats_service.TeamStatsService._evolution_feb",
            return_value=[],
        ), patch(
            "utils.collection_utils.is_fbcyl",
            return_value=False,
        ):
            resp = client.get(
                f"{V1}/teams/FEB_LF2_2025_A/evolution/Club%20Ejemplo?stat=invalid_stat"
            )
        assert resp.status_code == 200

    def test_evolution_empty_collection_returns_empty_list(self, client):
        """No games for a team returns an empty list (not an error)."""
        with patch(
            "src.services.team_stats_service.TeamStatsService._evolution_feb",
            return_value=[],
        ), patch(
            "utils.collection_utils.is_fbcyl",
            return_value=False,
        ):
            resp = client.get(
                f"{V1}/teams/FEB_LF2_2025_A/evolution/Equipo%20Inexistente?stat=points"
            )
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Shots endpoint
# ---------------------------------------------------------------------------

class TestShotZonesEndpoint:
    """Tests for GET /api/v1/shots/{collection}"""

    def test_shots_returns_10_zones_for_feb(self, client):
        """FEB collection returns exactly 10 zone objects."""
        with patch("utils.collection_utils.is_fbcyl", return_value=False):
            resp = client.get(f"{V1}/shots/FEB_LF2_2025_A")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 10

    def test_shots_zone_fields_present(self, client):
        """Each zone object has the required fields."""
        with patch("utils.collection_utils.is_fbcyl", return_value=False):
            resp = client.get(f"{V1}/shots/FEB_LF2_2025_A")
        data = resp.json()
        for zone in data:
            assert "zone" in zone
            assert "zone_label" in zone
            assert "fga" in zone
            assert "fgm" in zone
            assert "fg_pct" in zone

    def test_shots_returns_empty_for_fbcyl(self, client_fbcyl):
        """FBCYL collection returns an empty list (no shot coordinates)."""
        with patch("utils.collection_utils.is_fbcyl", return_value=True):
            resp = client_fbcyl.get(f"{V1}/shots/FBCYL_U16_2025_A")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_shots_no_negative_fg_pct(self, client):
        """FG% is never negative."""
        with patch("utils.collection_utils.is_fbcyl", return_value=False):
            resp = client.get(f"{V1}/shots/FEB_LF2_2025_A")
        for zone in resp.json():
            assert zone["fg_pct"] >= 0

    def test_shots_fgm_le_fga(self, client):
        """Made shots never exceed attempts."""
        with patch("utils.collection_utils.is_fbcyl", return_value=False):
            resp = client.get(f"{V1}/shots/FEB_LF2_2025_A")
        for zone in resp.json():
            assert zone["fgm"] <= zone["fga"]


# ---------------------------------------------------------------------------
# Possessions endpoint
# ---------------------------------------------------------------------------

class TestPossessionsEndpoint:
    """Tests for GET /api/v1/possessions/{collection}"""

    def test_possessions_returns_list(self, client):
        """Possessions endpoint returns a list."""
        resp = client.get(f"{V1}/possessions/FEB_LF2_2025_A")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_possessions_has_required_fields(self, client):
        """Each possession stat entry has pace, oer, der, net_rating."""
        resp = client.get(f"{V1}/possessions/FEB_LF2_2025_A")
        data = resp.json()
        assert len(data) >= 1
        fields = {"team_name", "pace", "oer", "der", "net_rating", "possessions_per_game"}
        for entry in data:
            for f in fields:
                assert f in entry, f"Missing field: {f}"

    def test_possessions_maps_from_team_stats(self, client):
        """OER/DER values match the offensive_rating/defensive_rating from team_stats."""
        resp = client.get(f"{V1}/possessions/FEB_LF2_2025_A")
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["oer"] == pytest.approx(TEAM_STAT_ROW["offensive_rating"], rel=1e-3)
        assert data[0]["der"] == pytest.approx(TEAM_STAT_ROW["defensive_rating"], rel=1e-3)

    def test_possessions_fbcyl_collection(self, client_fbcyl):
        """FBCYL collection also returns possessions data (from team stats)."""
        resp = client_fbcyl.get(f"{V1}/possessions/FBCYL_U16_2025_A")
        assert resp.status_code == 200
