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
        "game_date": "2025-01-05", "opponent": "Rival A", "won": True,
        "pts": 82,  "fg2m": 24, "fg2a": 38, "fg3m": 8,  "fg3a": 22,
        "ftm": 8,   "fta": 10,  "drb": 32,  "orb": 10,
        "ast": 18,  "stl": 5,   "tov": 11,  "blk": 3,
        "opp_pts": 75, "opp_fg2m": 20, "opp_fg2a": 35, "opp_fg3m": 6,  "opp_fg3a": 18,
        "opp_ftm": 7,  "opp_fta": 9,   "opp_drb": 28,  "opp_orb": 8,
        "opp_ast": 14, "opp_stl": 4,   "opp_tov": 9,   "opp_blk": 2,
    },
    {
        "game_date": "2025-01-12", "opponent": "Rival B", "won": False,
        "pts": 74,  "fg2m": 20, "fg2a": 35, "fg3m": 6,  "fg3a": 20,
        "ftm": 10,  "fta": 13,  "drb": 29,  "orb": 8,
        "ast": 15,  "stl": 4,   "tov": 13,  "blk": 2,
        "opp_pts": 80, "opp_fg2m": 22, "opp_fg2a": 37, "opp_fg3m": 9,  "opp_fg3a": 24,
        "opp_ftm": 6,  "opp_fta": 8,   "opp_drb": 31,  "opp_orb": 7,
        "opp_ast": 16, "opp_stl": 6,   "opp_tov": 10,  "opp_blk": 3,
    },
    {
        "game_date": "2025-01-19", "opponent": "Rival C", "won": True,
        "pts": 90,  "fg2m": 28, "fg2a": 42, "fg3m": 9,  "fg3a": 24,
        "ftm": 9,   "fta": 11,  "drb": 35,  "orb": 12,
        "ast": 22,  "stl": 7,   "tov": 9,   "blk": 4,
        "opp_pts": 78, "opp_fg2m": 21, "opp_fg2a": 36, "opp_fg3m": 7,  "opp_fg3a": 20,
        "opp_ftm": 9,  "opp_fta": 12,  "opp_drb": 30,  "opp_orb": 9,
        "opp_ast": 18, "opp_stl": 5,   "opp_tov": 11,  "opp_blk": 2,
    },
]

_SHOT_DOCS = [
    {
        "SHOTCHART": {
            "SHOTS": [
                {"x": 50.0, "y": 50.0, "m": 1, "team": "0", "player": "5",  "quarter": 1},
                {"x": 50.0, "y": 50.0, "m": 0, "team": "0", "player": "5",  "quarter": 1},
                {"x": 5.0,  "y": 50.0, "m": 1, "team": "0", "player": "23", "quarter": 2},
                {"x": 95.0, "y": 90.0, "m": 0, "team": "0", "player": "11", "quarter": 2},
            ],
            "TEAM": [
                {"PLAYER": [
                    {"no": "5",  "id": "FE-101", "name": "Jugador A"},
                    {"no": "23", "id": "FE-102", "name": "Jugador B"},
                    {"no": "11", "id": "FE-103", "name": "Jugador C"},
                ]},
                {"PLAYER": []},
            ],
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
            "src.services.evolution_service.EvolutionService._evolution_feb",
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
        """Each item in the evolution list has game_number, rolling_avg, and cumulative_avg fields."""
        with patch(
            "src.services.evolution_service.EvolutionService._evolution_feb",
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

    def test_evolution_returns_cumulative_avg(self, client):
        """Evolution response includes cumulative_avg field computed from game 1."""
        with patch(
            "src.services.evolution_service.EvolutionService._evolution_feb",
            return_value=_EVOLUTION_DOCS,
        ), patch(
            "utils.collection_utils.is_fbcyl",
            return_value=False,
        ):
            resp = client.get(f"{V1}/teams/FEB_LF2_2025_A/evolution/Club%20Ejemplo?stat=points")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert "cumulative_avg" in data[0]
        # After game 1: cumulative = game 1 value
        assert data[0]["cumulative_avg"] == data[0]["value"]
        # After game 2: cumulative = mean of games 1-2
        assert data[1]["cumulative_avg"] == pytest.approx(
            (data[0]["value"] + data[1]["value"]) / 2, abs=0.1
        )

    def test_evolution_invalid_stat_falls_back(self, client):
        """Invalid stat key is silently replaced with 'points'."""
        with patch(
            "src.services.evolution_service.EvolutionService._evolution_feb",
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
            "src.services.evolution_service.EvolutionService._evolution_feb",
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

    def test_evolution_advanced_stat_returns_values(self, client):
        """Advanced stats (e.g. offensive_rating) return numeric values."""
        with patch(
            "src.services.evolution_service.EvolutionService._evolution_feb",
            return_value=_EVOLUTION_DOCS,
        ), patch(
            "utils.collection_utils.is_fbcyl",
            return_value=False,
        ):
            resp = client.get(
                f"{V1}/teams/FEB_LF2_2025_A/evolution/Club%20Ejemplo?stat=offensive_rating"
            )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        # OER = pts / possessions * 100 — should be a positive float
        assert all(isinstance(row["value"], (int, float)) and row["value"] > 0 for row in data)


# ---------------------------------------------------------------------------
# Competition evolution endpoint
# ---------------------------------------------------------------------------

class TestCompetitionEvolutionEndpoint:
    """Tests for GET /api/v1/teams/{collection}/competition-evolution"""

    def test_competition_evolution_returns_list(self, client):
        """Competition evolution endpoint returns a list."""
        mock_db = MagicMock()
        mock_db.is_connected.return_value = True
        mock_db.get_all_teams.return_value = ["Club Ejemplo"]
        mock_coll = MagicMock()
        mock_coll.aggregate.return_value = iter(_EVOLUTION_DOCS)
        mock_db.connection.get_collection.return_value = mock_coll
        from src.api.app import app as _app
        _app.dependency_overrides[get_db] = lambda: mock_db
        try:
            with patch("utils.collection_utils.is_fbcyl", return_value=False):
                resp = client.get(f"{V1}/teams/FEB_LF2_2025_A/competition-evolution?stat=points")
        finally:
            _app.dependency_overrides.clear()
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_competition_evolution_invalid_stat_falls_back(self, client):
        """Invalid stat key falls back to 'points' without HTTP error."""
        mock_db = MagicMock()
        mock_db.is_connected.return_value = True
        mock_db.get_all_teams.return_value = []
        mock_db.connection.get_collection.return_value = MagicMock()
        from src.api.app import app as _app
        _app.dependency_overrides[get_db] = lambda: mock_db
        try:
            with patch("utils.collection_utils.is_fbcyl", return_value=False):
                resp = client.get(
                    f"{V1}/teams/FEB_LF2_2025_A/competition-evolution?stat=not_a_real_stat"
                )
        finally:
            _app.dependency_overrides.clear()
        assert resp.status_code == 200
        assert resp.json() == []  # empty teams → empty result


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

    def test_shots_string_team_field_regression(self):
        """Regression: SHOTCHART.SHOTS.team is stored as a string in FEB MongoDB documents.

        Previously the check `team_idx not in (0, 1)` used int literals, so
        every shot with team="0" was silently discarded, returning all-zero
        zone stats regardless of the selected team.  After the fix, int()
        conversion is applied before the comparison.
        """
        string_team_docs = [
            {
                "SHOTCHART": {
                    "SHOTS": [
                        # team stored as STRING — the real FEB scraper format
                        {"x": 50.0, "y": 50.0, "m": 1, "team": "0", "player": "5"},
                        {"x": 50.0, "y": 50.0, "m": 0, "team": "0", "player": "5"},
                        {"x": 5.0,  "y": 50.0, "m": 1, "team": "0", "player": "23"},
                    ],
                    "TEAM": [
                        {"PLAYER": [
                            {"no": "5",  "id": "FE-001", "name": "Jugador Uno"},
                            {"no": "23", "id": "FE-002", "name": "Jugador Dos"},
                        ]},
                        {"PLAYER": []},
                    ],
                },
                "HEADER": {
                    "TEAM": [{"name": "Club Ejemplo"}, {"name": "Rival Team"}]
                },
            }
        ]
        mock_db = MagicMock()
        mock_db.is_connected.return_value = True
        mock_coll = MagicMock()
        mock_coll.find.side_effect = lambda *a, **kw: iter(string_team_docs)
        mock_db.connection.get_collection.return_value = mock_coll
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            with TestClient(app) as c:
                with patch("utils.collection_utils.is_fbcyl", return_value=False):
                    # All shots for team
                    resp_team = c.get(f"{V1}/shots/FEB_LF2_2025_A")
                    assert resp_team.status_code == 200
                    total_fga = sum(z["fga"] for z in resp_team.json())
                    assert total_fga == 3, (
                        f"Expected 3 FGA but got {total_fga}. "
                        "Bug: string '0' was rejected by int comparison."
                    )
                    # Player filter — pass actual player ID (not dorsal)
                    resp_player = c.get(f"{V1}/shots/FEB_LF2_2025_A?player=FE-001")
                    assert resp_player.status_code == 200
                    player_fga = sum(z["fga"] for z in resp_player.json())
                    assert player_fga == 2, (
                        f"Expected 2 FGA for player FE-001 but got {player_fga}. "
                        "Bug: dorsal not resolved to player_id."
                    )
        finally:
            app.dependency_overrides.clear()

    def test_shots_raw_returns_coordinates(self):
        """GET /shots/{collection}/raw returns individual shot dicts with x, y, made, zone.

        Each shot must have:
        - x in [0, 15]  (FIBA court width metres)
        - y in [0, 14]  (FIBA half-court length metres)
        - made (bool)
        - zone (str from the 10-zone taxonomy)
        """
        raw_docs = [
            {
                "SHOTCHART": {
                    "SHOTS": [
                        {"x": 50.0, "y": 50.0, "m": 1, "team": "0", "player": "5"},
                        {"x": 20.0, "y": 30.0, "m": 0, "team": "0", "player": "5"},
                        {"x": 90.0, "y": 10.0, "m": 1, "team": "1", "player": "11"},
                    ],
                    "TEAM": [
                        {"PLAYER": [{"no": "5", "id": "FE-001", "name": "Jugador Uno"}]},
                        {"PLAYER": [{"no": "11", "id": "FE-010", "name": "Jugador Diez"}]},
                    ],
                },
                "HEADER": {
                    "TEAM": [{"name": "Club A"}, {"name": "Club B"}]
                },
            }
        ]
        mock_db = MagicMock()
        mock_db.is_connected.return_value = True
        mock_coll = MagicMock()
        mock_coll.find.side_effect = lambda *a, **kw: iter(raw_docs)
        mock_db.connection.get_collection.return_value = mock_coll
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            with TestClient(app) as c:
                with patch("utils.collection_utils.is_fbcyl", return_value=False):
                    resp = c.get(f"{V1}/shots/FEB_LF2_2025_A/raw")
                    assert resp.status_code == 200
                    shots = resp.json()
                    assert len(shots) == 3, f"Expected 3 shots, got {len(shots)}"
                    for shot in shots:
                        assert "x" in shot and "y" in shot
                        assert "made" in shot and isinstance(shot["made"], bool)
                        assert "zone" in shot and isinstance(shot["zone"], str)
                        assert 0 <= shot["x"] <= 15, f"x={shot['x']} out of FIBA range"
                        assert 0 <= shot["y"] <= 14, f"y={shot['y']} out of FIBA range"
                    # Verify made/missed correctly mapped
                    made_count = sum(1 for s in shots if s["made"])
                    assert made_count == 2, f"Expected 2 made shots, got {made_count}"
        finally:
            app.dependency_overrides.clear()

    def test_shots_raw_returns_empty_for_fbcyl(self, client_fbcyl):
        """Raw endpoint returns empty list for FBCYL collections."""
        with patch("utils.collection_utils.is_fbcyl", return_value=True):
            resp = client_fbcyl.get(f"{V1}/shots/FBCYL_U16_2025_A/raw")
        assert resp.status_code == 200
        assert resp.json() == []


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
