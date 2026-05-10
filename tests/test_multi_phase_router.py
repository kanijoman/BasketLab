"""Tests for multi-phase router — TDD red phase.

HTTP contract for:
  GET /api/v1/multi/team-stats?collections=C1,C2[&is_fbcyl=false]
  GET /api/v1/multi/player-stats?collections=C1,C2
  GET /api/v1/multi/team-stats/breakdown?collections=C1,C2
  GET /api/v1/multi/player-stats/breakdown?collections=C1,C2
  GET /api/v1/multi/sibling-collections?collection=FEB_LF2_2025_A
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from src.api.app import app
from src.api.deps import get_db

V1 = "/api/v1"


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _team_row(name: str, games: int = 10) -> Dict:
    return {
        "_id": name, "team_name": name, "games_played": games,
        "points_scored": 750.0, "points_per_game": 75.0,
        "fg2_made": 200, "fg2_attempts": 400,
        "fg3_made": 50,  "fg3_attempts": 150,
        "ft_made": 80,   "ft_attempts": 100,
        "rebounds_off": 80, "rebounds_def": 220, "total_rebounds": 300,
        "assists": 150, "steals": 50, "turnovers": 100,
        "blocks": 30, "personal_fouls": 160,
    }


def _player_row(name: str, team: str = "T1") -> Dict:
    return {
        "_id": name, "player_name": name, "team_name": team,
        "games_played": 8, "points_per_game": 12.0, "total_points": 96,
        "assists_per_game": 3.0, "rebounds_per_game": 4.0,
    }


def _mock_db(team_data: Dict[str, List], player_data: Dict[str, List] | None = None) -> MagicMock:
    db = MagicMock()
    db.is_connected.return_value = True

    def _get_team(coll, *a, **kw):
        return team_data.get(coll, [])

    def _get_player(coll, *a, **kw):
        return (player_data or {}).get(coll, [])

    db.get_team_stats.side_effect = _get_team
    db.get_player_stats.side_effect = _get_player
    db.get_opponent_stats.side_effect = _get_team

    # CollectionService calls
    mock_db_conn = MagicMock()
    mock_db_conn.list_collection_names.return_value = list(team_data.keys())
    db.connection.get_database.return_value = mock_db_conn

    col = MagicMock()
    col.count_documents.return_value = 1
    db.connection.get_collection.return_value = col
    return db


@pytest.fixture
def client_two_colls():
    db = _mock_db(
        {
            "FEB_LF2_2025_A": [_team_row("TeamX"), _team_row("TeamY")],
            "FEB_LF2_2025_B": [_team_row("TeamX"), _team_row("TeamZ")],
        },
        {
            "FEB_LF2_2025_A": [_player_row("P1"), _player_row("P2")],
            "FEB_LF2_2025_B": [_player_row("P1"), _player_row("P3")],
        },
    )
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def client_empty():
    db = _mock_db({})
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ===========================================================================
# GET /api/v1/multi/team-stats
# ===========================================================================

class TestMultiTeamStats:
    def test_returns_200(self, client_two_colls):
        r = client_two_colls.get(
            f"{V1}/multi/team-stats",
            params={"collections": "FEB_LF2_2025_A,FEB_LF2_2025_B"},
        )
        assert r.status_code == 200

    def test_returns_list(self, client_two_colls):
        r = client_two_colls.get(
            f"{V1}/multi/team-stats",
            params={"collections": "FEB_LF2_2025_A,FEB_LF2_2025_B"},
        )
        assert isinstance(r.json(), list)

    def test_teams_present_in_response(self, client_two_colls):
        r = client_two_colls.get(
            f"{V1}/multi/team-stats",
            params={"collections": "FEB_LF2_2025_A,FEB_LF2_2025_B"},
        )
        names = {row["team_name"] for row in r.json()}
        assert "TeamX" in names
        assert "TeamY" in names
        assert "TeamZ" in names

    def test_missing_collections_param_returns_422(self, client_empty):
        r = client_empty.get(f"{V1}/multi/team-stats")
        assert r.status_code == 422

    def test_empty_list_returns_empty(self, client_empty):
        r = client_empty.get(
            f"{V1}/multi/team-stats",
            params={"collections": ""},
        )
        assert r.status_code == 200
        assert r.json() == []


# ===========================================================================
# GET /api/v1/multi/player-stats
# ===========================================================================

class TestMultiPlayerStats:
    def test_returns_200(self, client_two_colls):
        r = client_two_colls.get(
            f"{V1}/multi/player-stats",
            params={"collections": "FEB_LF2_2025_A,FEB_LF2_2025_B"},
        )
        assert r.status_code == 200

    def test_players_merged(self, client_two_colls):
        r = client_two_colls.get(
            f"{V1}/multi/player-stats",
            params={"collections": "FEB_LF2_2025_A,FEB_LF2_2025_B"},
        )
        names = {row["player_name"] for row in r.json()}
        assert "P1" in names and "P2" in names and "P3" in names


# ===========================================================================
# GET /api/v1/multi/team-stats/breakdown
# ===========================================================================

class TestTeamStatsBreakdown:
    def test_returns_200(self, client_two_colls):
        r = client_two_colls.get(
            f"{V1}/multi/team-stats/breakdown",
            params={"collections": "FEB_LF2_2025_A,FEB_LF2_2025_B"},
        )
        assert r.status_code == 200

    def test_response_is_dict_keyed_by_collection(self, client_two_colls):
        r = client_two_colls.get(
            f"{V1}/multi/team-stats/breakdown",
            params={"collections": "FEB_LF2_2025_A,FEB_LF2_2025_B"},
        )
        body = r.json()
        assert "FEB_LF2_2025_A" in body
        assert "FEB_LF2_2025_B" in body

    def test_each_phase_is_list(self, client_two_colls):
        r = client_two_colls.get(
            f"{V1}/multi/team-stats/breakdown",
            params={"collections": "FEB_LF2_2025_A,FEB_LF2_2025_B"},
        )
        for v in r.json().values():
            assert isinstance(v, list)


# ===========================================================================
# GET /api/v1/multi/player-stats/breakdown
# ===========================================================================

class TestPlayerStatsBreakdown:
    def test_returns_200(self, client_two_colls):
        r = client_two_colls.get(
            f"{V1}/multi/player-stats/breakdown",
            params={"collections": "FEB_LF2_2025_A,FEB_LF2_2025_B"},
        )
        assert r.status_code == 200

    def test_response_keyed_by_collection(self, client_two_colls):
        r = client_two_colls.get(
            f"{V1}/multi/player-stats/breakdown",
            params={"collections": "FEB_LF2_2025_A,FEB_LF2_2025_B"},
        )
        assert "FEB_LF2_2025_A" in r.json()


# ===========================================================================
# GET /api/v1/multi/sibling-collections
# ===========================================================================

class TestSiblingCollections:
    def test_returns_200(self, client_two_colls):
        r = client_two_colls.get(
            f"{V1}/multi/sibling-collections",
            params={"collection": "FEB_LF2_2025_A"},
        )
        assert r.status_code == 200

    def test_returns_list(self, client_two_colls):
        r = client_two_colls.get(
            f"{V1}/multi/sibling-collections",
            params={"collection": "FEB_LF2_2025_A"},
        )
        assert isinstance(r.json(), list)

    def test_self_included_in_siblings(self, client_two_colls):
        r = client_two_colls.get(
            f"{V1}/multi/sibling-collections",
            params={"collection": "FEB_LF2_2025_A"},
        )
        assert "FEB_LF2_2025_A" in r.json()

    def test_missing_collection_param_returns_422(self, client_empty):
        r = client_empty.get(f"{V1}/multi/sibling-collections")
        assert r.status_code == 422
