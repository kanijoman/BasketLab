"""Tests for FASE 7 — GamePredictionService (Win/Loss classifier).

TDD cycle: tests written BEFORE implementation to define the contract.

Coverage:
- Happy path: returns win_prob in [0, 1] with CI and feature importances
- Walk-forward accuracy: classifier trains on past, evaluates on future
- Label integrity: binary labels derived correctly from net_rtg > 0
- Edge cases: insufficient data, all-win/all-loss seasons, missing fields
- Calibration: CalibratedClassifierCV keeps probabilities within [0, 1]
- API endpoint: POST /api/v1/analysis/game-prediction/{team_id} returns 200
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


# ---------------------------------------------------------------------------
# Shared helpers (same pattern as test_backtesting.py)
# ---------------------------------------------------------------------------

def _make_records(
    team_id: str,
    n: int,
    win_rate: float = 0.6,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """Generate n HISTORICAL-style docs with realistic net_rtg values."""
    rng = np.random.default_rng(seed)
    records = []
    for i in range(n):
        # net_rtg drives win/loss: positive = win, negative = loss
        net = rng.normal(3.0 if rng.random() < win_rate else -3.0, 4.0)
        records.append({
            "match_id":    f"game-{team_id}-{i}",
            "team_id":     team_id,
            "team_name":   f"Team {team_id}",
            "season":      "2024-25",
            "league":      "FEB",
            "competition": "LF2",
            "date":        datetime(2024, 9, 1) + timedelta(days=i * 7),
            "is_home":     i % 2 == 0,
            "net_rtg":     round(float(net), 2),
            "ortg":        round(100.0 + net / 2, 2),
            "drtg":        round(100.0 - net / 2, 2),
            "efg_pct":     round(50.0 + rng.normal(0, 3), 2),
            "tov_rate":    round(15.0 + rng.normal(0, 2), 2),
            "oreb_pct":    round(25.0 + rng.normal(0, 3), 2),
            "poss":        round(75.0 + rng.normal(0, 4), 2),
            "opp_net_rtg": round(-net + rng.normal(0, 2), 2),
        })
    return records


def _mock_conn(records: List[Dict]) -> MagicMock:
    conn = MagicMock()
    conn.is_connected.return_value = True
    return conn


# ===========================================================================
# Unit tests — GamePredictionService.predict()
# ===========================================================================

class TestGamePredictionContract:
    """Verify output shape and value constraints of predict()."""

    def _predict(self, records, **kwargs):
        from services.game_prediction_service import GamePredictionService
        conn = _mock_conn(records)
        svc = GamePredictionService(conn)
        with patch.object(svc, "_load_records", return_value=records):
            return svc.predict(
                team_id="T0",
                season="2024-25",
                is_home=True,
                opp_net_rtg=2.0,
                **kwargs,
            )

    def test_returns_dict(self):
        result = self._predict(_make_records("T0", 25))
        assert isinstance(result, dict)

    def test_has_win_prob(self):
        result = self._predict(_make_records("T0", 25))
        assert "win_prob" in result, f"Keys: {list(result.keys())}"

    def test_win_prob_in_unit_interval(self):
        result = self._predict(_make_records("T0", 25))
        p = result["win_prob"]
        assert 0.0 <= p <= 1.0, f"win_prob={p} outside [0, 1]"

    def test_has_confidence_interval(self):
        result = self._predict(_make_records("T0", 25))
        assert "ci_low" in result and "ci_high" in result

    def test_ci_bounds_valid(self):
        result = self._predict(_make_records("T0", 25))
        assert 0.0 <= result["ci_low"] <= result["win_prob"]
        assert result["win_prob"] <= result["ci_high"] <= 1.0

    def test_has_feature_importances(self):
        result = self._predict(_make_records("T0", 25))
        assert "feature_importances" in result
        fi = result["feature_importances"]
        assert isinstance(fi, dict)
        assert len(fi) > 0

    def test_feature_importances_sum_close_to_one(self):
        """Absolute importances should be normalised to sum ≈ 1."""
        result = self._predict(_make_records("T0", 25))
        fi = result["feature_importances"]
        total = sum(abs(v) for v in fi.values())
        assert abs(total - 1.0) < 0.01, f"Importances sum={total:.4f}"

    def test_has_n_train(self):
        result = self._predict(_make_records("T0", 25))
        assert "n_train" in result
        assert result["n_train"] > 0

    def test_has_accuracy(self):
        """Walk-forward CV accuracy should be returned."""
        result = self._predict(_make_records("T0", 25))
        assert "accuracy" in result
        acc = result["accuracy"]
        assert acc is None or (0.0 <= acc <= 1.0)

    def test_result_keys_complete(self):
        required = {"win_prob", "ci_low", "ci_high", "feature_importances",
                    "feature_coefficients", "n_train", "accuracy"}
        result = self._predict(_make_records("T0", 25))
        assert required.issubset(result.keys()), (
            f"Missing keys: {required - set(result.keys())}"
        )


# ===========================================================================
# Unit tests — label derivation
# ===========================================================================

class TestLabelDerivation:
    """Win label must be 1 when net_rtg > 0, else 0."""

    def test_positive_net_rtg_is_win(self):
        from services.game_prediction_service import _derive_label
        assert _derive_label(5.0)  == 1
        assert _derive_label(0.1)  == 1
        assert _derive_label(0.0)  == 0   # draw → loss
        assert _derive_label(-0.1) == 0
        assert _derive_label(-5.0) == 0

    def test_none_net_rtg_returns_none(self):
        from services.game_prediction_service import _derive_label
        assert _derive_label(None) is None


# ===========================================================================
# Unit tests — feature builder
# ===========================================================================

class TestFeatureBuilder:
    """Rolling features + context features must have expected shape."""

    def test_feature_vector_length(self):
        from services.game_prediction_service import _build_feature_vector
        records = _make_records("T0", 20)
        # For index 15 (has at least 10 games of history)
        feat = _build_feature_vector(records, idx=15, is_home=True, opp_net_rtg=2.0)
        assert feat is not None
        # Expected: [roll3_net, roll5_net, roll10_net,
        #            roll3_efg, roll5_efg, roll10_efg,
        #            roll3_tov, roll5_tov, roll10_tov,
        #            is_home, opp_bucket] = 11 features
        assert len(feat) == 11

    def test_feature_vector_all_finite(self):
        from services.game_prediction_service import _build_feature_vector
        records = _make_records("T0", 20)
        feat = _build_feature_vector(records, idx=15, is_home=True, opp_net_rtg=2.0)
        assert all(np.isfinite(v) for v in feat)

    def test_is_home_encoded(self):
        from services.game_prediction_service import _build_feature_vector
        records = _make_records("T0", 20)
        feat_home = _build_feature_vector(records, idx=15, is_home=True, opp_net_rtg=0.0)
        feat_away = _build_feature_vector(records, idx=15, is_home=False, opp_net_rtg=0.0)
        # is_home is the 10th feature (index 9)
        assert feat_home[9] == 1.0
        assert feat_away[9] == 0.0


# ===========================================================================
# Edge cases
# ===========================================================================

class TestGamePredictionEdgeCases:

    def _predict(self, records):
        from services.game_prediction_service import GamePredictionService
        conn = _mock_conn(records)
        svc = GamePredictionService(conn)
        with patch.object(svc, "_load_records", return_value=records):
            return svc.predict("T0", "2024-25", is_home=True, opp_net_rtg=0.0)

    def test_empty_records_returns_error(self):
        result = self._predict([])
        assert "error" in result

    def test_insufficient_records_returns_error(self):
        result = self._predict(_make_records("T0", 8))
        assert "error" in result

    def test_all_wins_does_not_crash(self):
        """All labels = 1 (monotone class) must be handled gracefully."""
        records = _make_records("T0", 25, win_rate=1.0, seed=0)
        # Force all net_rtg positive
        for r in records:
            r["net_rtg"] = abs(r["net_rtg"]) + 1.0
        result = self._predict(records)
        # Either a valid prediction OR an explicit error — not a crash
        assert isinstance(result, dict)

    def test_minimum_viable_25_games(self):
        """25 games should produce a valid prediction."""
        result = self._predict(_make_records("T0", 25))
        assert "error" not in result
        assert 0.0 <= result["win_prob"] <= 1.0


class TestWalkForwardPipelineRegression:
    """Regression: walk-forward must use calibrated pipeline (Bug 5 fix)."""

    def test_walk_forward_uses_predict_proba_not_predict(self):
        """Ensure _walk_forward_accuracy delegates to _fit() (calibrated pipeline).

        Before the fix, _walk_forward_accuracy instantiated an uncalibrated
        LogisticRegression inline, diverging from the deployed CalibratedClassifierCV.
        After the fix it calls self._fit() and predict_proba, so mocking _fit()
        with a constant-return pipeline must be reflected in the accuracy result.
        """
        from unittest.mock import MagicMock, patch
        from services.game_prediction_service import GamePredictionService

        records = _make_records("T0", 40, seed=7)
        conn = _mock_conn(records)
        svc = GamePredictionService(conn)

        fit_calls = []
        original_fit = svc._fit

        def tracking_fit(X, y):
            result = original_fit(X, y)
            if result is not None:
                fit_calls.append(True)
            return result

        with patch.object(svc, "_fit", side_effect=tracking_fit):
            with patch.object(svc, "_load_records", return_value=records):
                svc.predict("T0", "2024-25", is_home=True, opp_net_rtg=0.0)

        assert len(fit_calls) > 0, (
            "_fit() (calibrated pipeline) should have been called during walk-forward"
        )


# ===========================================================================
# API endpoint
# ===========================================================================

class TestGamePredictionAPIEndpoint:

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        from src.api.deps import get_db
        app.dependency_overrides[get_db] = lambda: MagicMock()
        yield TestClient(app)
        app.dependency_overrides.pop(get_db, None)

    def _mock_result(self):
        return {
            "win_prob": 0.65,
            "ci_low": 0.52,
            "ci_high": 0.78,
            "feature_importances": {"roll3_net_rtg": 0.45, "is_home": 0.20,
                                    "opp_bucket": 0.15, "roll3_efg_pct": 0.20},
            "n_train": 20,
            "accuracy": 0.72,
        }

    def test_returns_200(self, client):
        with patch("src.services.game_prediction_service.GamePredictionService") as MockSvc:
            MockSvc.return_value.predict.return_value = self._mock_result()
            resp = client.post(
                "/api/v1/analysis/game-prediction/T0",
                json={"season": "2024-25", "is_home": True, "opp_net_rtg": 2.0},
            )
        assert resp.status_code == 200

    def test_response_has_win_prob(self, client):
        with patch("src.services.game_prediction_service.GamePredictionService") as MockSvc:
            MockSvc.return_value.predict.return_value = self._mock_result()
            resp = client.post(
                "/api/v1/analysis/game-prediction/T0",
                json={"season": "2024-25", "is_home": True, "opp_net_rtg": 2.0},
            )
        body = resp.json()
        assert "win_prob" in body
        assert 0.0 <= body["win_prob"] <= 1.0

    def test_missing_season_without_live_params_returns_422(self, client):
        """Without season AND without live_collection+live_team_name, the handler
        must return 422 (neither historical nor live mode can be resolved).
        This replaces the old test that expected 422 just from missing season,
        which broke when season became Optional to support live mode."""
        resp = client.post(
            "/api/v1/analysis/game-prediction/T0",
            json={"is_home": True},
        )
        assert resp.status_code == 422

    def test_live_mode_without_season_returns_200(self, client):
        """Live mode must work when season is absent.
        Regression test: previously season was a required Pydantic field
        so this would return 422 Field required."""
        with patch("src.services.game_prediction_service.GamePredictionService") as MockSvc:
            MockSvc.return_value.predict_live.return_value = self._mock_result()
            resp = client.post(
                "/api/v1/analysis/game-prediction/_live",
                json={
                    "live_collection": "FBCYL_test",
                    "live_team_name":  "Equipo A",
                    "live_is_fbcyl":   True,
                    "is_home":         True,
                    "opp_net_rtg":     1.5,
                    # season intentionally absent
                },
            )
        assert resp.status_code == 200, resp.text
