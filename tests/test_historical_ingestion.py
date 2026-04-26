"""Tests for the HISTORICAL ingestion pipeline — FASE 0.

Covers:
- FEB and FBCYL normalizers (unit)
- HistoricalRepository upsert + deduplication (unit, mongomock)
- FastAPI endpoints: ingest, progress, summary (integration via TestClient)

Regression scope:
- Existing scraper tests must still pass (scrapers not modified)
- Existing test_api.py must still pass (new router does not break routing)
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import mongomock
import pytest

# Ensure src/ is on path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from src.services.historical_ingestion_service import (
    normalize_feb_match,
    normalize_fbcyl_match,
    _parse_date,
    _compute_derived,
    _efg,
)
from src.database.historical_repository import HistoricalRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {
    "match_id", "date", "season", "competition", "league", "group",
    "team_id", "team_name", "is_home", "opp_id", "opp_name",
    "pts", "opp_pts", "fga", "fgm", "fg2a", "fg2m", "fg3a", "fg3m",
    "fta", "ftm", "oreb", "dreb", "ast", "stl", "tov", "blk", "pf",
    "poss", "opp_poss", "pace", "ortg", "drtg", "net_rtg",
    "efg_pct", "opp_efg_pct", "tov_rate", "oreb_pct", "ftr", "fg3a_rate",
    "diff_pts_100", "diff_efg", "diff_tov_100", "diff_oreb_100", "diff_ftr",
    "source_collection", "scraped_at",
}


def _make_feb_team_box(team_id: str, name: str, pts: int, p2m=10, p2a=20,
                       p3m=5, p3a=15, p1m=8, p1a=10, ro=5, rd=15,
                       assist=10, st=3, to=8, bs=1, pf=12,
                       win_lose="W") -> dict:
    """Build a minimal FEB BOXSCORE.TEAM entry."""
    return {
        "id": team_id,
        "name": name,
        "win_lose": win_lose,
        "TOTAL": {
            "pts": str(pts), "p2m": str(p2m), "p2a": str(p2a),
            "p3m": str(p3m), "p3a": str(p3a), "p1m": str(p1m), "p1a": str(p1a),
            "ro": str(ro), "rd": str(rd), "assist": str(assist),
            "st": str(st), "to": str(to), "bs": str(bs), "pf": str(pf),
        },
    }


def _make_feb_doc(match_id=12345, home_id="T1", away_id="T2",
                  home_pts=74, away_pts=56) -> dict:
    """Build a minimal FEB game document."""
    return {
        "_id": match_id,
        "HEADER": {
            "game_code": match_id,
            "starttime": "15-01-2025 - 18:00",
            "competition": "L.F.-2",
            "TEAM": [
                {"id": home_id, "name": "Team Local", "pts": str(home_pts)},
                {"id": away_id, "name": "Team Visitante", "pts": str(away_pts)},
            ],
        },
        "BOXSCORE": {
            "TEAM": [
                _make_feb_team_box(home_id, "Team Local", home_pts, win_lose="W"),
                _make_feb_team_box(away_id, "Team Visitante", away_pts, win_lose="L",
                                   p2m=8, p2a=18, p3m=3, p3a=12, p1m=6, p1a=9,
                                   ro=3, rd=20, assist=8, st=2, to=10, bs=0),
            ],
        },
    }


def _make_fbcyl_doc(match_uuid="uuid-abc", home_id="FBT1", away_id="FBT2",
                    home_pts=70, away_pts=65) -> dict:
    """Build a minimal FBCYL game document."""
    return {
        "_id": match_uuid,
        "uuid": match_uuid,
        "date": "2025-02-10",
        "stats": {
            "teams": [
                {
                    "id": home_id, "name": "FBCYL Local",
                    "score": home_pts,
                    "shotsOfTwoSuccessful": 12, "shotsOfTwoAttempted": 22,
                    "shotsOfThreeSuccessful": 4, "shotsOfThreeAttempted": 14,
                    "shotsOfOneSuccessful": 6, "shotsOfOneAttempted": 8,
                    "offensiveRebound": 4, "defensiveRebound": 18,
                    "assists": 12, "steals": 4, "lost": 7, "block": 2, "foulsCommited": 14,
                },
                {
                    "id": away_id, "name": "FBCYL Visitante",
                    "score": away_pts,
                    "shotsOfTwoSuccessful": 11, "shotsOfTwoAttempted": 20,
                    "shotsOfThreeSuccessful": 5, "shotsOfThreeAttempted": 16,
                    "shotsOfOneSuccessful": 5, "shotsOfOneAttempted": 9,
                    "offensiveRebound": 3, "defensiveRebound": 15,
                    "assists": 10, "steals": 3, "lost": 9, "block": 1, "foulsCommited": 16,
                },
            ],
        },
    }


def _make_historical_doc(**overrides) -> dict:
    """Build a minimal valid HISTORICAL document."""
    base = {
        "match_id": "99999",
        "date": datetime(2025, 1, 15),
        "season": "2024-25",
        "competition": "LF2",
        "league": "FEB",
        "gender": None,
        "group": "A",
        "team_id": "T1",
        "team_name": "Team A",
        "is_home": True,
        "opp_id": "T2",
        "opp_name": "Team B",
        "pts": 74,
        "opp_pts": 56,
        "source_collection": "FEB_LF2_2025_A",
        "scraped_at": datetime.utcnow(),
    }
    base.update(overrides)
    return base


def _make_mock_connection(db):
    conn = MagicMock()
    conn.is_connected.return_value = True
    conn.get_collection.side_effect = lambda name: db[name]
    return conn


# ---------------------------------------------------------------------------
# Normalizer — FEB unit tests
# ---------------------------------------------------------------------------

class TestNormalizeFebMatch:
    def test_returns_two_documents(self):
        doc = _make_feb_doc()
        result = normalize_feb_match(doc, "2024-25", "LF2", "A", "FEB_LF2_2025_A")
        assert len(result) == 2

    def test_feb_doc_has_all_required_fields(self):
        doc = _make_feb_doc()
        results = normalize_feb_match(doc, "2024-25", "LF2", "A", "FEB_LF2_2025_A")
        for hdoc in results:
            missing = REQUIRED_FIELDS - set(hdoc.keys())
            assert not missing, f"Missing fields: {missing}"

    def test_home_away_assignment(self):
        doc = _make_feb_doc(home_id="HOME_T", away_id="AWAY_T")
        results = normalize_feb_match(doc, "2024-25", "LF2", "A", "FEB_LF2_2025_A")
        home_doc = next(d for d in results if d["team_id"] == "HOME_T")
        away_doc = next(d for d in results if d["team_id"] == "AWAY_T")
        assert home_doc["is_home"] is True
        assert away_doc["is_home"] is False

    def test_diff_efg_sign_correct_home_away(self):
        """Home + away diff_efg must be mirror images (sum near 0)."""
        doc = _make_feb_doc()
        results = normalize_feb_match(doc, "2024-25", "LF2", "A", "FEB_LF2_2025_A")
        d0 = results[0]["diff_efg"]
        d1 = results[1]["diff_efg"]
        assert abs(d0 + d1) < 0.01, f"diff_efg not mirrored: {d0} + {d1} = {d0 + d1}"

    def test_diff_pts_100_sign_correct(self):
        """Winner has positive diff_pts_100, loser has negative."""
        doc = _make_feb_doc(home_id="W", away_id="L", home_pts=80, away_pts=60)
        results = normalize_feb_match(doc, "2024-25", "LF2", "A", "FEB_LF2_2025_A")
        winner = next(d for d in results if d["team_id"] == "W")
        loser  = next(d for d in results if d["team_id"] == "L")
        assert winner["diff_pts_100"] > 0
        assert loser["diff_pts_100"] < 0

    def test_derived_stats_consistent_with_calculator(self):
        """poss, ortg, efg_pct verify against manual formula."""
        doc = _make_feb_doc(home_pts=74)
        results = normalize_feb_match(doc, "2024-25", "LF2", "A", "FEB_LF2_2025_A")
        home_doc = results[0]
        # poss = FGA + 0.45*FTA + TOV - OREB  (team_box defaults: p2a=20,p3a=15,p1a=10,to=8,ro=5)
        expected_poss = (20 + 15) + 0.45 * 10 + 8 - 5
        assert abs(home_doc["poss"] - expected_poss) < 0.5

    def test_invalid_doc_with_wrong_team_count_returns_empty(self):
        doc = {"_id": 1, "HEADER": {"game_code": 1, "TEAM": [], "starttime": ""},
               "BOXSCORE": {"TEAM": [_make_feb_team_box("T1", "A", 50)]}}
        result = normalize_feb_match(doc, "2024-25", "LF2", "A", "COL")
        assert result == []

    def test_source_collection_stored(self):
        doc = _make_feb_doc()
        results = normalize_feb_match(doc, "2024-25", "LF2", "A", "MY_SOURCE_COL")
        for hdoc in results:
            assert hdoc["source_collection"] == "MY_SOURCE_COL"


# ---------------------------------------------------------------------------
# Normalizer — FBCYL unit tests
# ---------------------------------------------------------------------------

class TestNormalizeFbcylMatch:
    def test_returns_two_documents(self):
        doc = _make_fbcyl_doc()
        result = normalize_fbcyl_match(doc, "2024-25", "SE", "", "F", "FBCYL_SE_2025")
        assert len(result) == 2

    def test_fbcyl_doc_has_all_required_fields(self):
        doc = _make_fbcyl_doc()
        results = normalize_fbcyl_match(doc, "2024-25", "SE", "", "F", "FBCYL_SE_2025")
        for hdoc in results:
            missing = REQUIRED_FIELDS - set(hdoc.keys())
            assert not missing, f"Missing fields: {missing}"

    def test_fbcyl_diff_efg_mirrored(self):
        doc = _make_fbcyl_doc()
        results = normalize_fbcyl_match(doc, "2024-25", "SE", "", "F", "FBCYL_SE_2025")
        d0 = results[0]["diff_efg"]
        d1 = results[1]["diff_efg"]
        assert abs(d0 + d1) < 0.01

    def test_fbcyl_league_field_is_fbcyl(self):
        doc = _make_fbcyl_doc()
        results = normalize_fbcyl_match(doc, "2024-25", "SE", "", "F", "FBCYL_SE_2025")
        for hdoc in results:
            assert hdoc["league"] == "FBCYL"

    def test_fbcyl_gender_stored(self):
        doc = _make_fbcyl_doc()
        results = normalize_fbcyl_match(doc, "2024-25", "SE", "", "F", "FBCYL_SE_2025")
        for hdoc in results:
            assert hdoc["gender"] == "F"


# ---------------------------------------------------------------------------
# _parse_date unit tests
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_feb_format(self):
        dt = _parse_date("15-01-2025 - 18:00")
        assert dt == datetime(2025, 1, 15)

    def test_iso_format(self):
        dt = _parse_date("2025-02-10")
        assert dt == datetime(2025, 2, 10)

    def test_none_input(self):
        assert _parse_date("") is None
        assert _parse_date(None) is None


# ---------------------------------------------------------------------------
# HistoricalRepository — unit tests with mongomock
# ---------------------------------------------------------------------------

class TestHistoricalRepository:
    def setup_method(self):
        client = mongomock.MongoClient()
        self.db = client["basketlab_test"]
        self.conn = _make_mock_connection(self.db)
        self.repo = HistoricalRepository(self.conn)

    def test_upsert_inserts_new_document(self):
        doc = _make_historical_doc()
        self.repo.upsert_match_team(doc)
        assert self.db["HISTORICAL"].count_documents({}) == 1

    def test_upsert_same_match_team_does_not_duplicate(self):
        doc = _make_historical_doc()
        self.repo.upsert_match_team(doc)
        self.repo.upsert_match_team(doc)  # same match_id + team_id
        assert self.db["HISTORICAL"].count_documents({}) == 1

    def test_upsert_different_team_same_match_creates_two_docs(self):
        doc_home = _make_historical_doc(team_id="T1")
        doc_away = _make_historical_doc(team_id="T2")
        self.repo.upsert_match_team(doc_home)
        self.repo.upsert_match_team(doc_away)
        assert self.db["HISTORICAL"].count_documents({}) == 2

    def test_get_seasons_for_elasticity_returns_all_seasons(self):
        for season in ["2022-23", "2023-24", "2024-25"]:
            self.db["HISTORICAL"].insert_one({
                "match_id": f"m_{season}", "team_id": "T1",
                "league": "FEB", "competition": "LF2", "season": season,
                "group": "A", "diff_pts_100": 5.0,
            })
        results = self.repo.get_seasons_for_elasticity(leagues=["FEB"])
        seasons_found = {r["season"] for r in results}
        assert seasons_found == {"2022-23", "2023-24", "2024-25"}

    def test_get_seasons_for_elasticity_filters_by_competition(self):
        self.db["HISTORICAL"].insert_many([
            {"match_id": "m1", "team_id": "T1", "league": "FEB",
             "competition": "LF2", "season": "2024-25", "group": "A"},
            {"match_id": "m2", "team_id": "T1", "league": "FEB",
             "competition": "EBA", "season": "2024-25", "group": "A"},
        ])
        results = self.repo.get_seasons_for_elasticity(competitions=["LF2"])
        assert all(r["competition"] == "LF2" for r in results)

    def test_get_team_profile_filters_by_season(self):
        self.db["HISTORICAL"].insert_many([
            {"match_id": "m1", "team_id": "T1", "season": "2024-25",
             "ortg": 105.0, "drtg": 100.0, "pace": 72.0,
             "efg_pct": 50.0, "tov_rate": 12.0, "oreb_pct": 25.0,
             "ftr": 20.0, "fg3a_rate": 35.0},
            {"match_id": "m2", "team_id": "T1", "season": "2023-24",
             "ortg": 98.0, "drtg": 102.0, "pace": 68.0,
             "efg_pct": 47.0, "tov_rate": 14.0, "oreb_pct": 22.0,
             "ftr": 18.0, "fg3a_rate": 30.0},
        ])
        profile = self.repo.get_team_profile("T1", "2024-25")
        assert profile is not None
        assert profile["season"] == "2024-25"
        assert profile["n"] == 1
        assert abs(profile["avg_ortg"] - 105.0) < 0.01

    def test_get_team_profile_returns_none_when_no_data(self):
        result = self.repo.get_team_profile("NONEXISTENT", "2024-25")
        assert result is None

    def test_get_summary_groups_correctly(self):
        # Insert 2 team docs per match (home + away) = 1 match logically
        for team_id in ["T1", "T2"]:
            self.db["HISTORICAL"].insert_one({
                "match_id": "m1", "team_id": team_id,
                "league": "FEB", "competition": "LF2",
                "season": "2024-25", "group": "A",
            })
        summary = self.repo.get_summary()
        assert len(summary) == 1
        assert summary[0]["match_count"] == 1.0  # 2 docs / 2

    def test_upsert_returns_false_when_not_connected(self):
        conn = MagicMock()
        conn.is_connected.return_value = False
        repo = HistoricalRepository(conn)
        result = repo.upsert_match_team(_make_historical_doc())
        assert result is False

    def test_get_seasons_returns_empty_when_not_connected(self):
        conn = MagicMock()
        conn.is_connected.return_value = False
        repo = HistoricalRepository(conn)
        result = repo.get_seasons_for_elasticity()
        assert result == []


# ---------------------------------------------------------------------------
# FastAPI endpoint tests
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    """TestClient with mocked DB dependency (standard project pattern)."""
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.deps import get_db

    client = mongomock.MongoClient()
    db_mock = client["basketlab_test"]
    conn_mock = _make_mock_connection(db_mock)

    handler = MagicMock()
    handler.is_connected.return_value = True
    handler.connection = conn_mock

    app.dependency_overrides[get_db] = lambda: handler
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestHistoricalAPI:
    def test_historical_ingest_returns_job_id(self, api_client):
        payload = {
            "league": "FEB",
            "feb_seasons": [{
                "competition_url": "https://example.com",
                "season_value": "S1",
                "group_value": "G1",
                "competition_label": "LF2",
                "season_label": "LF2 2024",
                "group_label": "A",
                "normalized_season": "2024-25",
            }],
        }
        # Mock the background task so it doesn't actually scrape
        with patch("src.api.routers.historical._run_feb_ingest"):
            resp = api_client.post("/api/v1/historical/ingest", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert "job_id" in body
        assert isinstance(body["job_id"], str)

    def test_historical_progress_unknown_job_returns_404(self, api_client):
        resp = api_client.get("/api/v1/historical/progress/nonexistent-job-id")
        assert resp.status_code == 404

    def test_historical_summary_returns_list(self, api_client):
        resp = api_client.get("/api/v1/historical/summary")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_historical_ingest_invalid_league_returns_400(self, api_client):
        resp = api_client.post("/api/v1/historical/ingest",
                               json={"league": "INVALID"})
        assert resp.status_code == 400

    def test_historical_ingest_feb_without_seasons_returns_422(self, api_client):
        resp = api_client.post("/api/v1/historical/ingest",
                               json={"league": "FEB"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Regression: existing API routes unaffected
# ---------------------------------------------------------------------------

class TestExistingRoutesUnaffected:
    def test_root_still_returns_ok(self, api_client):
        resp = api_client.get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_collections_list_route_still_works(self, api_client):
        # Endpoint exists even if DB is mocked empty
        resp = api_client.get("/api/v1/collections/list")
        assert resp.status_code == 200
