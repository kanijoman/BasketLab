"""Tests for matches router — TDD red phase.

Covers HTTP contract for:
  GET /api/v1/matches/{collection}            → match list
  GET /api/v1/matches/{collection}/{match_id} → full comparison
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
# Shared mock factories
# ---------------------------------------------------------------------------

def _mock_db(docs: List[Dict]) -> MagicMock:
    col = MagicMock()
    col.find.return_value = docs
    col.find_one.side_effect = lambda q, *a, **kw: next(
        (d for d in docs if d["_id"] == q.get("_id")), None
    )
    db = MagicMock()
    db.is_connected.return_value = True
    db.connection.get_collection.return_value = col
    return db


def _feb_doc(match_id: int = 1, home_pts: int = 70, away_pts: int = 65) -> Dict:
    return {
        "_id": match_id,
        "HEADER": {
            "game_code": match_id,
            "starttime": "01-10-2025 - 19:00",
            "place": "Pabellón",
            "round": "1",
            "TEAM": [
                {"id": "111", "name": "LOCAL", "pts": str(home_pts)},
                {"id": "222", "name": "VISITOR", "pts": str(away_pts)},
            ],
        },
        "BOXSCORE": {
            "TEAM": [
                {
                    "id": "111", "name": "LOCAL",
                    "pts": str(home_pts), "ro": "8", "rd": "22",
                    "st": "6", "to": "10", "pf": "16",
                    "PLAYER": [{
                        "pts": str(home_pts), "fgm": "25", "fga": "55",
                        "p2m": "18", "p2a": "38", "p3m": "7", "p3a": "17",
                        "p1m": "8", "p1a": "10", "ro": "8", "rd": "22",
                        "assist": "15", "st": "6", "to": "10",
                        "bs": "3", "pf": "16", "val": "20", "inn": "1",
                    }],
                },
                {
                    "id": "222", "name": "VISITOR",
                    "pts": str(away_pts), "ro": "9", "rd": "20",
                    "st": "4", "to": "13", "pf": "18",
                    "PLAYER": [{
                        "pts": str(away_pts), "fgm": "22", "fga": "52",
                        "p2m": "15", "p2a": "35", "p3m": "7", "p3a": "17",
                        "p1m": "6", "p1a": "8", "ro": "9", "rd": "20",
                        "assist": "12", "st": "4", "to": "13",
                        "bs": "2", "pf": "18", "val": "18", "inn": "1",
                    }],
                },
            ],
        },
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client_feb():
    docs = [_feb_doc(match_id=1), _feb_doc(match_id=2)]
    db = _mock_db(docs)
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def client_empty():
    db = _mock_db([])
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ===========================================================================
# GET /api/v1/matches/{collection}  — match list
# ===========================================================================

class TestMatchListEndpoint:
    def test_returns_200(self, client_feb):
        r = client_feb.get(f"{V1}/matches/FEB_LF2_2025_A")
        assert r.status_code == 200

    def test_returns_list(self, client_feb):
        r = client_feb.get(f"{V1}/matches/FEB_LF2_2025_A")
        body = r.json()
        assert isinstance(body, list)
        assert len(body) == 2

    def test_each_item_has_required_fields(self, client_feb):
        r = client_feb.get(f"{V1}/matches/FEB_LF2_2025_A")
        item = r.json()[0]
        for field in ("match_id", "home_team", "away_team",
                      "home_score", "away_score", "date"):
            assert field in item, f"Missing field: {field}"

    def test_empty_collection_returns_empty_list(self, client_empty):
        r = client_empty.get(f"{V1}/matches/FEB_LF2_2025_A")
        assert r.status_code == 200
        assert r.json() == []

    def test_fbcyl_flag_accepted(self):
        fbcyl_doc = {
            "_id": "aabb",
            "stats": {
                "time": "May 4, 2026",
                "localId": 1, "visitId": 2,
                "score": [{"local": 70, "visit": 65, "period": 4}],
                "teams": [
                    {"teamIdIntern": 1, "name": "LOCAL", "players": []},
                    {"teamIdIntern": 2, "name": "VISITOR", "players": []},
                ],
            },
        }
        db = _mock_db([fbcyl_doc])
        app.dependency_overrides[get_db] = lambda: db
        try:
            c = TestClient(app)
            r = c.get(f"{V1}/matches/FBCYL_LF2_2025?is_fbcyl=true")
            assert r.status_code == 200
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# GET /api/v1/matches/{collection}/{match_id}  — single match analysis
# ===========================================================================

class TestMatchAnalysisEndpoint:
    def test_existing_match_returns_200(self, client_feb):
        r = client_feb.get(f"{V1}/matches/FEB_LF2_2025_A/1")
        assert r.status_code == 200

    def test_missing_match_returns_404(self, client_feb):
        r = client_feb.get(f"{V1}/matches/FEB_LF2_2025_A/9999")
        assert r.status_code == 404

    def test_response_has_home_away_comparison_keys(self, client_feb):
        r = client_feb.get(f"{V1}/matches/FEB_LF2_2025_A/1")
        body = r.json()
        assert "home" in body
        assert "away" in body
        assert "comparison" in body

    def test_comparison_is_list(self, client_feb):
        r = client_feb.get(f"{V1}/matches/FEB_LF2_2025_A/1")
        assert isinstance(r.json()["comparison"], list)

    def test_comparison_rows_have_required_fields(self, client_feb):
        r = client_feb.get(f"{V1}/matches/FEB_LF2_2025_A/1")
        rows = r.json()["comparison"]
        assert rows, "Comparison list is empty"
        for row in rows:
            for f in ("stat_key", "label", "home_value", "away_value",
                      "delta", "winner", "lower_is_better", "section"):
                assert f in row, f"Missing field {f!r} in row {row.get('stat_key')}"

    def test_winner_values_are_valid(self, client_feb):
        r = client_feb.get(f"{V1}/matches/FEB_LF2_2025_A/1")
        for row in r.json()["comparison"]:
            assert row["winner"] in ("home", "away", "tie"), (
                f"Invalid winner: {row['winner']} for {row['stat_key']}")

    def test_home_team_name_in_response(self, client_feb):
        r = client_feb.get(f"{V1}/matches/FEB_LF2_2025_A/1")
        assert r.json()["home"]["team_name"] == "LOCAL"

    def test_integer_match_id_parsed_correctly(self, client_feb):
        # match_id=2 must be resolved as int
        r = client_feb.get(f"{V1}/matches/FEB_LF2_2025_A/2")
        assert r.status_code == 200
