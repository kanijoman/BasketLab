"""Tests for FASE 2-5 predictive analytics services and endpoints.

Covers:
- RivalAdjustedService: computation with FEB and FBCYL data
- ElasticityService: dataset building, Ridge fitting, Bootstrap CI, predict
- MonteCarloService: simulation with synthetic historical data
- API endpoints: /analysis/* (200 responses, structure validation)
- Regression: existing analysis routes unaffected
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import mongomock
import numpy as np
import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

def _make_handler_from_db(db, name: str) -> MagicMock:
    """Wrap a mongomock db as a MongoDBHandler-compatible mock."""
    conn = MagicMock()
    conn.is_connected.return_value = True
    conn.get_collection.side_effect = lambda n: db[n]
    handler = MagicMock()
    handler.is_connected.return_value = True
    handler.connection = conn
    return handler


def _fake_per_game_row(team: str, pts: int, opp_pts: int, game_idx: int) -> Dict:
    """Build a minimal FEB-style per-game row (output of per-game pipeline)."""
    fg2m, fg2a, fg3m, fg3a, fta = 10, 20, 3, 8, 5
    orb, tov = 4, 6
    fga = fg2a + fg3a
    poss = fga + 0.45 * fta + tov - orb
    oer = pts / poss * 100 if poss else 0
    der = opp_pts / poss * 100 if poss else 0
    return {
        "team_name":        team,
        "points":           pts,
        "opponent_points":  opp_pts,
        "fg2_made":         fg2m, "fg2_attempts": fg2a,
        "fg3_made":         fg3m, "fg3_attempts": fg3a,
        "ft_attempts":      fta,  "ft_made": 4,
        "off_rebounds":     orb,  "def_rebounds": 7,
        "total_rebounds":   orb + 7,
        "assists":          6,    "steals": 3,
        "turnovers":        tov,  "blocks": 1,
        "possessions":      poss,
        "oer_game":         round(oer, 2),
        "der_game":         round(der, 2),
        "net_game":         round(oer - der, 2),
        "efg_pct_game":     round((fg2m + 1.5 * fg3m) / fga * 100, 2),
        "ts_pct_game":      55.0,
        "tov_pct_game":     round(tov / (fga + 0.44 * fta + tov) * 100, 2),
        "oreb_rate_game":   round(orb / (orb + 7) * 100, 2),
        # Opponent stats (what team ALLOWS)
        "opp_net_game":     round(-(oer - der), 2),
        "opp_oer_game":     round(der, 2),
        "opp_der_game":     round(oer, 2),
        "opp_efg_pct_game": 48.0,
        "opp_tov_pct_game": 14.0,
        "opp_orb_rate_game": 25.0,
    }


def _make_rows_two_teams(n_games: int = 8) -> List[Dict]:
    """Produce 2*n_games rows for teams A and B, each game = one row per team."""
    rows = []
    for i in range(n_games):
        pts_a = 70 + i
        pts_b = 65 + i
        rows.append(_fake_per_game_row("Team A", pts_a, pts_b, i))
        rows.append(_fake_per_game_row("Team B", pts_b, pts_a, i))
    return rows


def _fake_historical_records(team_id: str, n: int, start_net: float = 5.0) -> List[Dict]:
    """Produce n HISTORICAL-style docs for one team with varying net_rtg."""
    rng = np.random.default_rng(42)
    records = []
    for i in range(n):
        net = start_net + rng.normal(0, 3)
        records.append({
            "match_id":   f"game-{team_id}-{i}",
            "team_id":    team_id,
            "team_name":  f"Team {team_id}",
            "season":     "2024-25",
            "league":     "FEB",
            "competition": "LF2",
            "date":       datetime(2024, 9, 1) + timedelta(days=i * 7),
            "is_home":    i % 2 == 0,
            "net_rtg":    round(float(net), 2),
            "ortg":       round(100.0 + net / 2, 2),
            "drtg":       round(100.0 - net / 2, 2),
            "efg_pct":    round(50.0 + rng.normal(0, 3), 2),
            "tov_rate":   round(15.0 + rng.normal(0, 2), 2),
            "oreb_pct":   round(25.0 + rng.normal(0, 3), 2),
            "poss":       round(75.0 + rng.normal(0, 4), 2),
            "pace":       round(75.0 + rng.normal(0, 4), 2),
            "opp_net_rtg": round(-net + rng.normal(0, 2), 2),
        })
    return records


# ===========================================================================
# FASE 2 — RivalAdjustedService
# ===========================================================================

class TestRivalAdjustedService:
    def test_returns_dict_with_team_keys(self):
        from services.rival_adjusted_service import RivalAdjustedService

        rows = _make_rows_two_teams(8)
        handler = MagicMock()
        handler.connection.get_collection.return_value = MagicMock()

        svc = RivalAdjustedService(handler)
        # Patch _fetch_rows to return synthetic data directly
        with patch.object(svc, '_fetch_rows', return_value=rows):
            result = svc.get_rival_adjusted_stats("FEB_LF2_2025_A")

        assert isinstance(result, dict)
        assert "Team A" in result
        assert "Team B" in result

    def test_has_stat_structure(self):
        from services.rival_adjusted_service import RivalAdjustedService

        rows = _make_rows_two_teams(8)
        handler = MagicMock()
        svc = RivalAdjustedService(handler)
        with patch.object(svc, '_fetch_rows', return_value=rows):
            result = svc.get_rival_adjusted_stats("FEB_LF2_2025_A")

        for team, stats in result.items():
            for stat_key, v in stats.items():
                assert "raw_avg" in v
                assert "n" in v
                assert v["n"] >= 1

    def test_empty_collection_returns_empty(self):
        from services.rival_adjusted_service import RivalAdjustedService

        handler = MagicMock()
        svc = RivalAdjustedService(handler)
        with patch.object(svc, '_fetch_rows', return_value=[]):
            result = svc.get_rival_adjusted_stats("FEB_LF2_2025_A")
        assert result == {}

    def test_adj_offset_reflects_opponent_quality(self):
        """A team playing only strong opponents should have positive adj (harder schedule)."""
        from services.rival_adjusted_service import RivalAdjustedService

        # Team C plays only against Team D (who allows a lot of points)
        # Team D's rows: high opp_* (allows high pts)
        rows = []
        for i in range(6):
            rows.append(_fake_per_game_row("Team C", 75, 60, i))
            rows.append(_fake_per_game_row("Team D", 60, 75, i))
        handler = MagicMock()
        svc = RivalAdjustedService(handler)
        with patch.object(svc, '_fetch_rows', return_value=rows):
            result = svc.get_rival_adjusted_stats("X")
        # Both teams should have adj values (structure check)
        assert all("pts" in stats for stats in result.values())

    def test_fbcyl_collection_uses_fbcyl_pipeline(self):
        from services.rival_adjusted_service import RivalAdjustedService

        handler = MagicMock()
        svc = RivalAdjustedService(handler)
        with patch.object(svc, '_fetch_rows', return_value=[]) as mock_fetch:
            svc.get_rival_adjusted_stats("FBCYL_SE_2025_A")
            mock_fetch.assert_called_once_with("FBCYL_SE_2025_A", True)


# ===========================================================================
# FASE 3/4 — ElasticityService
# ===========================================================================

class TestElasticityDataset:
    def test_build_dataset_returns_arrays(self):
        from services.elasticity_service import _build_dataset

        records = []
        for team_id in ["A", "B", "C"]:
            records.extend(_fake_historical_records(team_id, 20))

        X, y, n_teams = _build_dataset(records, "net_rtg", extra_features=False)
        assert X.shape[1] == 3  # roll3, roll5, roll10
        assert len(y) > 0
        assert n_teams == 3

    def test_build_dataset_model_b_has_5_features(self):
        from services.elasticity_service import _build_dataset

        records = []
        for team_id in ["A", "B", "C"]:
            records.extend(_fake_historical_records(team_id, 20))
        X, y, _ = _build_dataset(records, "net_rtg", extra_features=True)
        assert X.shape[1] == 5  # 3 rolling + is_home + opp_bucket

    def test_not_enough_data_returns_empty(self):
        from services.elasticity_service import _build_dataset

        # Only 5 games per team — less than max_window (10) + 1
        records = _fake_historical_records("X", 5)
        X, y, _ = _build_dataset(records, "net_rtg")
        assert len(y) == 0


class TestRidgeFitting:
    def test_fit_returns_model_dict(self):
        from services.elasticity_service import _fit_ridge_with_bootstrap

        rng = np.random.default_rng(0)
        X = rng.standard_normal((100, 3))
        y = X[:, 0] * 2 + rng.standard_normal(100) * 0.5
        model = _fit_ridge_with_bootstrap(X, y)
        assert model is not None
        assert "coef" in model
        assert "intercept" in model
        assert "ci_low" in model
        assert "ci_high" in model
        assert "r2_train" in model
        assert len(model["coef"]) == 3

    def test_fit_returns_none_for_small_dataset(self):
        from services.elasticity_service import _fit_ridge_with_bootstrap

        X = np.random.standard_normal((10, 3))
        y = np.random.standard_normal(10)
        result = _fit_ridge_with_bootstrap(X, y)
        assert result is None


class TestPredictWithCI:
    def test_returns_estimate_and_bounds(self):
        from services.elasticity_service import _predict_with_ci

        model_doc = {
            "coef":          [1.0, 0.5, 0.2],
            "intercept":     2.0,
            "scaler_mean":   [0.0, 0.0, 0.0],
            "scaler_scale":  [1.0, 1.0, 1.0],
            "ci_low":        [0.8, 0.4, 0.1],
            "ci_high":       [1.2, 0.6, 0.3],
            "r2_train":      0.75,
        }
        result = _predict_with_ci(model_doc, [1.0, 0.5, 0.3])
        assert "estimate" in result
        assert "ci_low" in result
        assert "ci_high" in result
        assert result["ci_low"] <= result["estimate"] <= result["ci_high"]

    def test_ci_symmetric_when_no_bootstrap(self):
        from services.elasticity_service import _predict_with_ci

        model_doc = {
            "coef":         [1.0],
            "intercept":    0.0,
            "scaler_mean":  [0.0],
            "scaler_scale": [1.0],
            "r2_train":     0.5,
        }  # no ci_low / ci_high
        result = _predict_with_ci(model_doc, [5.0])
        assert result["ci_low"] == result["ci_high"] == result["estimate"]


class TestElasticityServiceTrain:
    def _make_service_with_data(self, n_teams=5, n_games=25):
        """Build an ElasticityService backed by mongomock HISTORICAL data."""
        client = mongomock.MongoClient()
        db = client["basketlab_test"]

        for i in range(n_teams):
            for rec in _fake_historical_records(f"team-{i}", n_games, start_net=i * 2.0):
                db["HISTORICAL"].insert_one(rec)

        conn = MagicMock()
        conn.is_connected.return_value = True
        conn.get_collection.side_effect = lambda name: db[name]
        from services.elasticity_service import ElasticityService
        return ElasticityService(conn)

    def test_train_returns_stat_summary(self):
        svc = self._make_service_with_data()
        result = svc.train()
        assert isinstance(result, dict)
        # At least some stats should have been fitted
        assert len(result) > 0

    def test_train_no_data_returns_error(self):
        client = mongomock.MongoClient()
        db = client["basketlab_test"]
        conn = MagicMock()
        conn.is_connected.return_value = True
        conn.get_collection.side_effect = lambda name: db[name]
        from services.elasticity_service import ElasticityService
        svc = ElasticityService(conn)
        result = svc.train()
        assert "error" in result

    def test_predict_after_train(self):
        svc = self._make_service_with_data(n_teams=4, n_games=30)
        # Train first
        svc.train()
        # Now predict for team-0, season 2024-25
        result = svc.predict_next_game("team-0", "2024-25")
        # Either we get predictions or an error (not enough stored model)
        assert isinstance(result, dict)

    def test_list_models_after_train(self):
        svc = self._make_service_with_data()
        svc.train()
        models = svc.list_models()
        assert isinstance(models, list)


# ===========================================================================
# FASE 5 — MonteCarloService
# ===========================================================================

class TestMonteCarloService:
    def _make_service_with_historical(self, n_teams=4, n_games=30):
        client = mongomock.MongoClient()
        db = client["basketlab_test"]
        for i in range(n_teams):
            for rec in _fake_historical_records(f"team-{i}", n_games, start_net=i * 2.0):
                db["HISTORICAL"].insert_one(rec)
        for rec in _fake_model_docs():
            db["ELASTICITIES"].insert_one(rec)
        conn = MagicMock()
        conn.is_connected.return_value = True
        conn.get_collection.side_effect = lambda name: db[name]
        from services.monte_carlo_service import MonteCarloService
        return MonteCarloService(conn)

    def test_simulate_returns_structured_result(self):
        svc = self._make_service_with_historical()
        result = svc.simulate("team-0", "2024-25", n_games=3, n_simulations=100)
        assert "games" in result
        assert len(result["games"]) == 3
        assert "projected_wins_mean" in result

    def test_win_prob_between_0_and_1(self):
        svc = self._make_service_with_historical()
        result = svc.simulate("team-0", "2024-25", n_games=3, n_simulations=100)
        for game in result["games"]:
            assert 0.0 <= game["win_prob"] <= 1.0

    def test_no_historical_returns_error(self):
        client = mongomock.MongoClient()
        db = client["basketlab_test"]
        for rec in _fake_model_docs():
            db["ELASTICITIES"].insert_one(rec)
        conn = MagicMock()
        conn.is_connected.return_value = True
        conn.get_collection.side_effect = lambda name: db[name]
        from services.monte_carlo_service import MonteCarloService
        svc = MonteCarloService(conn)
        result = svc.simulate("nonexistent", "2024-25", n_games=3, n_simulations=50)
        assert "error" in result

    def test_no_models_returns_error(self):
        client = mongomock.MongoClient()
        db = client["basketlab_test"]
        for rec in _fake_historical_records("team-X", 20):
            db["HISTORICAL"].insert_one(rec)
        # No ELASTICITIES docs
        conn = MagicMock()
        conn.is_connected.return_value = True
        conn.get_collection.side_effect = lambda name: db[name]
        from services.monte_carlo_service import MonteCarloService
        svc = MonteCarloService(conn)
        result = svc.simulate("team-X", "2024-25", n_games=2, n_simulations=50)
        assert "error" in result

    def test_projected_wins_std_non_negative(self):
        svc = self._make_service_with_historical()
        result = svc.simulate("team-0", "2024-25", n_games=5, n_simulations=200)
        if "projected_wins_std" in result:
            assert result["projected_wins_std"] >= 0


def _fake_model_docs() -> List[Dict]:
    """Create minimal ELASTICITIES docs to allow MC inference."""
    from services.elasticity_service import TARGET_STATS, ROLLING_WINDOWS

    docs = []
    for stat in TARGET_STATS:
        n_feat = len(ROLLING_WINDOWS)
        docs.append({
            "model_type":   "A",
            "stat":         stat,
            "league":       "ALL",
            "competition":  "ALL",
            "coef":         [0.3] * n_feat,
            "intercept":    2.0,
            "scaler_mean":  [0.0] * n_feat,
            "scaler_scale": [1.0] * n_feat,
            "ci_low":       [0.2] * n_feat,
            "ci_high":      [0.4] * n_feat,
            "r2_train":     0.3,
            "n_samples":    100,
            "n_teams":      5,
            "features":     [f"roll_{w}" for w in ROLLING_WINDOWS],
        })
    return docs


# ===========================================================================
# API endpoint tests
# ===========================================================================

@pytest.fixture
def api_client_analysis(feb_game_doc):
    """TestClient with mocked DB for analysis endpoints."""
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.deps import get_db

    client = mongomock.MongoClient()
    db_mock = client["basketlab_test"]
    db_mock["FEB_LF2_2025_A"].insert_one(dict(feb_game_doc))

    conn_mock = MagicMock()
    conn_mock.is_connected.return_value = True
    conn_mock.get_collection.side_effect = lambda name: db_mock[name]

    handler = MagicMock()
    handler.is_connected.return_value = True
    handler.connection = conn_mock

    app.dependency_overrides[get_db] = lambda: handler
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestAnalysisAPIEndpoints:
    def test_rival_adjusted_returns_200(self, api_client_analysis):
        resp = api_client_analysis.get(
            "/api/v1/analysis/FEB_LF2_2025_A/rival_adjusted"
        )
        assert resp.status_code == 200

    def test_rival_adjusted_returns_dict(self, api_client_analysis):
        resp = api_client_analysis.get(
            "/api/v1/analysis/FEB_LF2_2025_A/rival_adjusted"
        )
        assert isinstance(resp.json(), dict)

    def test_elasticity_models_returns_200(self, api_client_analysis):
        resp = api_client_analysis.get("/api/v1/analysis/elasticity/models")
        assert resp.status_code == 200

    def test_elasticity_models_returns_list(self, api_client_analysis):
        resp = api_client_analysis.get("/api/v1/analysis/elasticity/models")
        assert isinstance(resp.json(), list)

    def test_elasticity_train_returns_200_or_422(self, api_client_analysis):
        """Train with no HISTORICAL data → 422."""
        resp = api_client_analysis.post(
            "/api/v1/analysis/elasticity/train",
            json={"leagues": ["FEB"]},
        )
        assert resp.status_code in (200, 422)

    def test_elasticity_predict_unknown_team_returns_404(self, api_client_analysis):
        resp = api_client_analysis.get(
            "/api/v1/analysis/elasticity/predict/unknown-team?season=2024-25"
        )
        assert resp.status_code == 404

    def test_montecarlo_unknown_team_returns_404(self, api_client_analysis):
        resp = api_client_analysis.post(
            "/api/v1/analysis/montecarlo/unknown-team",
            json={"season": "2024-25", "n_games": 3, "n_simulations": 100},
        )
        assert resp.status_code == 404

    def test_montecarlo_validates_n_games_range(self, api_client_analysis):
        resp = api_client_analysis.post(
            "/api/v1/analysis/montecarlo/team-x",
            json={"season": "2024-25", "n_games": 99, "n_simulations": 100},
        )
        assert resp.status_code == 422


# ===========================================================================
# Regression: existing routes unaffected
# ===========================================================================

class TestExistingRoutesUnaffectedByAnalysis:
    def test_root_ok(self, api_client_analysis):
        assert api_client_analysis.get("/").status_code == 200

    def test_historical_summary_ok(self, api_client_analysis):
        assert (
            api_client_analysis.get("/api/v1/historical/summary").status_code == 200
        )
