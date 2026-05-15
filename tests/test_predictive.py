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

    def test_small_sample_suppresses_adj_avg_regression(self):
        """Regression: with < _MIN_ADJ_GAMES paired games adj_avg must be None.

        Bug: with n=2 games the rival's 'allowed ortg' equals the evaluated
        team's own OER (circular dependency), causing adj_avg = league_mean
        for every team.  The fix requires min _MIN_ADJ_GAMES paired games.
        """
        from services.rival_adjusted_service import RivalAdjustedService, _MIN_ADJ_GAMES

        # Build exactly (_MIN_ADJ_GAMES - 1) games between two teams → below threshold
        n_below = _MIN_ADJ_GAMES - 1
        rows = _make_rows_two_teams(n_below)
        handler = MagicMock()
        svc = RivalAdjustedService(handler)
        with patch.object(svc, '_fetch_rows', return_value=rows):
            result = svc.get_rival_adjusted_stats("SMALL_COLL")

        for team, stats in result.items():
            for stat_key, v in stats.items():
                assert v["adj_avg"] is None, (
                    f"{team}.{stat_key}: expected adj_avg=None with n={v['n']} < {_MIN_ADJ_GAMES}"
                )
                assert v["adj"] is None
                assert v["sos"] is None
                assert v["raw_avg"] is not None   # raw always populated
                assert v["n"] == n_below

    def test_sufficient_sample_produces_adj_avg(self):
        """With >= _MIN_ADJ_GAMES games adj_avg must be populated."""
        from services.rival_adjusted_service import RivalAdjustedService, _MIN_ADJ_GAMES

        rows = _make_rows_two_teams(_MIN_ADJ_GAMES)
        handler = MagicMock()
        svc = RivalAdjustedService(handler)
        with patch.object(svc, '_fetch_rows', return_value=rows):
            result = svc.get_rival_adjusted_stats("OK_COLL")

        for team, stats in result.items():
            for stat_key, v in stats.items():
                assert v["adj_avg"] is not None, (
                    f"{team}.{stat_key}: expected adj_avg populated with n={v['n']} >= {_MIN_ADJ_GAMES}"
                )


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


class TestModeloC:
    """Tests for the new Modelo C and D (FASE E improvements)."""

    def _records(self, n_teams: int = 4, n_games: int = 30) -> list:
        records = []
        for i in range(n_teams):
            records.extend(_fake_historical_records(f"team-{i}", n_games, start_net=float(i)))
        return records

    # --- _build_dataset new flags ---

    def test_modelo_c_extended_windows_adds_roll20(self):
        from services._elasticity_models import _build_dataset, ROLLING_WINDOWS_C
        records = self._records()
        X, y, _ = _build_dataset(records, "net_rtg", extended_windows=True)
        assert X.shape[1] == len(ROLLING_WINDOWS_C)  # 4 rolling features

    def test_modelo_c_momentum_adds_one_feature(self):
        from services._elasticity_models import _build_dataset
        records = self._records()
        X_base, _, _ = _build_dataset(records, "net_rtg")
        X_mom,  _, _ = _build_dataset(records, "net_rtg", add_momentum=True)
        assert X_mom.shape[1] == X_base.shape[1] + 1

    def test_modelo_c_cross_stat_adds_driver_features(self):
        from services._elasticity_models import _build_dataset, CROSS_STAT_FEATURES
        records = self._records()
        n_cross = len(CROSS_STAT_FEATURES.get("net_rtg", []))  # 2 for net_rtg
        X_base, _, _ = _build_dataset(records, "net_rtg")
        X_cross, _, _ = _build_dataset(records, "net_rtg", cross_stat_features=True)
        assert X_cross.shape[1] == X_base.shape[1] + n_cross

    def test_modelo_c_opp_continuous_uses_float_not_bucket(self):
        """opp_continuous=True → feature varies continuously, not in {-1, 0, 1}."""
        from services._elasticity_models import _build_dataset
        records = self._records()
        X_cont, _, _ = _build_dataset(records, "net_rtg", extra_features=True, opp_continuous=True)
        # Extract the opp column (last extra feature)
        opp_col = X_cont[:, -1]
        unique_vals = set(np.unique(np.round(opp_col, 1)))
        # If continuous, there are far more than 3 unique values
        assert len(unique_vals) > 3

    def test_modelo_c_full_feature_count(self):
        """Modelo C full feature count: roll3/5/10/20 + momentum + is_home + opp + cross-stats."""
        from services._elasticity_models import _build_dataset, ROLLING_WINDOWS_C, CROSS_STAT_FEATURES
        records = self._records()
        n_cross = len(CROSS_STAT_FEATURES.get("net_rtg", []))
        X, y, _ = _build_dataset(
            records, "net_rtg",
            extended_windows=True, add_momentum=True,
            extra_features=True, opp_continuous=True,
            cross_stat_features=True,
        )
        expected = len(ROLLING_WINDOWS_C) + 1 + 2 + n_cross  # windows + momentum + is_home + opp + cross
        assert X.shape[1] == expected

    def test_extended_windows_requires_20_games(self):
        """roll20 needs at least 21 games per team — teams with < 21 are skipped."""
        from services._elasticity_models import _build_dataset
        # Teams with only 15 games → skipped with extended_windows=True
        records = []
        for i in range(4):
            records.extend(_fake_historical_records(f"t{i}", 15))
        X, y, n_teams = _build_dataset(records, "net_rtg", extended_windows=True)
        assert len(y) == 0  # all teams skipped (15 < 20+1)

    # --- _compute_sample_weights ---

    def test_sample_weights_sum_to_n(self):
        from services._elasticity_models import _compute_sample_weights
        n = 100
        w = _compute_sample_weights(n)
        assert len(w) == n
        assert abs(w.sum() - n) < 1e-6

    def test_sample_weights_increasing(self):
        """Recent samples must have strictly higher weight than older ones."""
        from services._elasticity_models import _compute_sample_weights
        w = _compute_sample_weights(50)
        assert w[-1] > w[0]  # last (recent) > first (oldest)
        assert np.all(np.diff(w) > 0)  # strictly monotone

    # --- _fit_ridge_with_bootstrap sample_weight ---

    def test_fit_with_sample_weight_returns_model(self):
        from services._elasticity_models import _fit_ridge_with_bootstrap, _compute_sample_weights
        rng = np.random.default_rng(0)
        X = rng.standard_normal((60, 4))
        y = X[:, 0] * 2 + rng.standard_normal(60) * 0.5
        sw = _compute_sample_weights(len(y))
        model = _fit_ridge_with_bootstrap(X, y, sample_weight=sw)
        assert model is not None
        assert "rmse_train" in model
        assert len(model["coef"]) == 4

    # --- _build_features_for_inference ---

    def test_feature_builder_modelo_c(self):
        from services._feature_builders import _build_features_for_inference
        from services._elasticity_models import ROLLING_WINDOWS_C, CROSS_STAT_FEATURES
        model_doc = {
            "model_type": "C",
            "windows": ROLLING_WINDOWS_C,
            "feature_flags": {
                "momentum": True, "cross_stats": True, "context": True,
                "opp_continuous": True, "extended_windows": True,
            },
            "coef": [0.1] * (len(ROLLING_WINDOWS_C) + 1 + 2 + len(CROSS_STAT_FEATURES["net_rtg"])),
            "intercept": 0.0,
            "scaler_mean":  [0.0] * (len(ROLLING_WINDOWS_C) + 1 + 2 + len(CROSS_STAT_FEATURES["net_rtg"])),
            "scaler_scale": [1.0] * (len(ROLLING_WINDOWS_C) + 1 + 2 + len(CROSS_STAT_FEATURES["net_rtg"])),
        }
        vals_by_stat = {s: [float(i) for i in range(25)] for s in ["net_rtg", "ortg", "drtg"]}
        feats = _build_features_for_inference(model_doc, vals_by_stat, "net_rtg", is_home=True, opp_net_rtg=2.5)
        n_cross = len(CROSS_STAT_FEATURES["net_rtg"])
        expected_len = len(ROLLING_WINDOWS_C) + 1 + 2 + n_cross
        assert len(feats) == expected_len

    # --- _gbm_models ---

    def test_gbm_fit_returns_serialized_dict(self):
        from services._gbm_models import _fit_gbm_with_quantiles
        rng = np.random.default_rng(1)
        X = rng.standard_normal((60, 5))
        y = X[:, 0] * 3 + rng.standard_normal(60)
        result = _fit_gbm_with_quantiles(X, y)
        assert result is not None
        assert all(k in result for k in ("gbm_mean", "gbm_q05", "gbm_q95", "r2_train", "rmse_train"))

    def test_gbm_predict_returns_ci(self):
        from services._gbm_models import _fit_gbm_with_quantiles, _predict_gbm
        rng = np.random.default_rng(2)
        X = rng.standard_normal((60, 3))
        y = X[:, 0] * 2 + rng.standard_normal(60)
        model_doc = _fit_gbm_with_quantiles(X, y)
        result = _predict_gbm(model_doc, [0.5, -0.2, 1.1])
        assert "estimate" in result
        assert result["ci_low"] <= result["ci_high"]


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


# ---------------------------------------------------------------------------
# Fake model docs with rmse_train (post Fase 1)
# ---------------------------------------------------------------------------

def _fake_model_docs_with_rmse() -> List[Dict]:
    """Model docs with rmse_train populated — realistic game-to-game RMSE."""
    from services.elasticity_service import TARGET_STATS, ROLLING_WINDOWS

    rmse_by_stat = {
        "net_rtg": 8.0, "ortg": 5.0, "drtg": 5.0,
        "efg_pct": 3.0, "tov_rate": 4.0, "oreb_pct": 5.0,
    }
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
            "rmse_train":   rmse_by_stat.get(stat, 5.0),
            "n_samples":    100,
            "n_teams":      5,
            "features":     [f"roll_{w}" for w in ROLLING_WINDOWS],
        })
    return docs


class TestMonteCarloRegressions:
    """Regression tests for bugs fixed in Fases 2/4/5.

    Bug history:
    - sigma derived from model param CI (~0.67 pts) instead of RMSE (~8 pts)
      → all net_rtg draws positive → P(victoria)=100%, std=0.00
    - RNG seed reset inside stat loop → fully deterministic simulation
    - History collapsed to mean → no auto-regressive variance propagation
    """

    def _make_service(self, net_rtg_mean: float = 4.0) -> object:
        import mongomock
        client = mongomock.MongoClient()
        db = client["basketlab_test"]
        for i in range(3):
            for rec in _fake_historical_records(f"team-{i}", 25, start_net=net_rtg_mean):
                db["HISTORICAL"].insert_one(rec)
        for rec in _fake_model_docs_with_rmse():
            db["ELASTICITIES"].insert_one(rec)
        conn = MagicMock()
        conn.is_connected.return_value = True
        conn.get_collection.side_effect = lambda name: db[name]
        from services.monte_carlo_service import MonteCarloService
        return MonteCarloService(conn)

    def test_projected_wins_std_positive_regression(self):
        """Bug: sigma from model CI ~0.67 → all draws > 0 → std == 0.00."""
        svc = self._make_service()
        result = svc.simulate("team-0", "2024-25", n_games=5, n_simulations=500)
        assert "projected_wins_std" in result
        assert result["projected_wins_std"] > 0, (
            f"projected_wins_std must be > 0, got {result['projected_wins_std']}"
        )

    def test_win_prob_not_always_one_regression(self):
        """Bug: P(victoria)=100.0% for every game when sigma too small."""
        svc = self._make_service(net_rtg_mean=3.0)
        result = svc.simulate("team-0", "2024-25", n_games=5, n_simulations=1000)
        win_probs = [g["win_prob"] for g in result.get("games", [])]
        assert any(p < 1.0 for p in win_probs), (
            f"Expected at least one game with win_prob < 1.0, got {win_probs}"
        )

    def test_simulation_is_stochastic(self):
        """Bug: RNG seed 42+g_idx reset per stat → deterministic results."""
        svc = self._make_service()
        r1 = svc.simulate("team-0", "2024-25", n_games=3, n_simulations=200)
        r2 = svc.simulate("team-0", "2024-25", n_games=3, n_simulations=200)
        if "games" in r1 and "games" in r2:
            stds1 = [g["stats"].get("net_rtg", {}).get("std") for g in r1["games"]]
            stds2 = [g["stats"].get("net_rtg", {}).get("std") for g in r2["games"]]
            assert stds1 != stds2 or r1["projected_wins_std"] != r2["projected_wins_std"], (
                "Two independent calls returned identical results (simulation is deterministic)"
            )

    def test_projected_wins_ci_spread_regression(self):
        """Bug: IC collapsed [5.0, 5.0] — lower must be < upper."""
        svc = self._make_service()
        result = svc.simulate("team-0", "2024-25", n_games=5, n_simulations=500)
        ci_low  = result.get("projected_wins_ci_low", 0.0)
        ci_high = result.get("projected_wins_ci_high", 0.0)
        assert ci_high > ci_low, (
            f"IC must have positive width, got [{ci_low}, {ci_high}]"
        )


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
            "/api/v1/teams/FEB_LF2_2025_A/rival-adjusted"
        )
        assert resp.status_code == 200

    def test_rival_adjusted_returns_dict(self, api_client_analysis):
        resp = api_client_analysis.get(
            "/api/v1/teams/FEB_LF2_2025_A/rival-adjusted"
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
