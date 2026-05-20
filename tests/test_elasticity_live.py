"""Tests for ElasticityService live-mode prediction (FASE predict_next_game_live).

Covers:
- _predict_from_records delegation from predict_next_game
- predict_next_game_live uses LiveHistoryAdapter records
- predict_next_game_live returns error dict when adapter returns []
- Router dispatches to live path when live_collection param provided
- Router returns 422 when live_collection provided but live_team_name missing
- Router dispatches to historical path when no live_collection
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_records(n: int = 20, team_id: str = "T1") -> list:
    """Synthetic HISTORICAL-schema records (same fields as HistoricalRepository output)."""
    rng = np.random.default_rng(42)
    records = []
    for i in range(n):
        net = float(rng.normal(0, 5))
        records.append({
            "team_id":    team_id,
            "team_name":  f"Team {team_id}",
            "season":     "2025-26",
            "league":     "FEB",
            "competition": "LF2",
            "date":       datetime(2025, 9, 1) + timedelta(days=i * 7),
            "is_home":    i % 2 == 0,
            "net_rtg":    round(net, 2),
            "ortg":       round(100.0 + net / 2, 2),
            "drtg":       round(100.0 - net / 2, 2),
            "efg_pct":    round(50.0 + float(rng.normal(0, 3)), 2),
            "tov_rate":   round(15.0 + float(rng.normal(0, 2)), 2),
            "oreb_pct":   round(25.0 + float(rng.normal(0, 3)), 2),
            "opp_net_rtg": round(-net + float(rng.normal(0, 2)), 2),
        })
    return records


def _make_service_with_models():
    """Build an ElasticityService with a mock connection that holds trained ELASTICITIES."""
    from services.elasticity_service import ElasticityService

    conn = MagicMock()
    conn.is_connected.return_value = True

    svc = ElasticityService(conn)

    # Modelo A: 3 features (rolling 3/5/10)
    model_a_doc = {
        "coef":         [1.0, 0.5, 0.2],
        "intercept":    2.0,
        "scaler_mean":  [0.0, 0.0, 0.0],
        "scaler_scale": [1.0, 1.0, 1.0],
        "ci_low":       [0.8, 0.4, 0.1],
        "ci_high":      [1.2, 0.6, 0.3],
        "r2_train":     0.15,
        "n_samples":    100,
        "model_type":   "A",
    }
    # Modelo B: 5 features (rolling 3/5/10 + is_home + opp_bucket)
    model_b_doc = {
        "coef":         [1.0, 0.5, 0.2, 0.3, -0.1],
        "intercept":    2.0,
        "scaler_mean":  [0.0, 0.0, 0.0, 0.0, 0.0],
        "scaler_scale": [1.0, 1.0, 1.0, 1.0, 1.0],
        "ci_low":       [0.8, 0.4, 0.1, 0.2, -0.2],
        "ci_high":      [1.2, 0.6, 0.3, 0.4, 0.0],
        "r2_train":     0.18,
        "n_samples":    100,
        "model_type":   "B",
    }

    def _get_model(model_type: str, stat: str, league: str = "ALL", competition: str = "ALL"):
        return model_b_doc if model_type == "B" else model_a_doc

    svc._repo.get_model = MagicMock(side_effect=_get_model)
    return svc


# ---------------------------------------------------------------------------
# _predict_from_records — unit tests
# ---------------------------------------------------------------------------

class TestPredictFromRecords:
    def test_returns_all_target_stats(self):
        from services.elasticity_service import ElasticityService
        from services._elasticity_models import TARGET_STATS

        svc = _make_service_with_models()
        records = _fake_records(20)
        result = svc._predict_from_records(records, None, None, None, None)

        for stat in TARGET_STATS:
            assert stat in result, f"Expected {stat} in result"

    def test_model_a_always_present(self):
        svc = _make_service_with_models()
        records = _fake_records(20)
        result = svc._predict_from_records(records, None, None, None, None)
        for v in result.values():
            assert "model_a" in v

    def test_model_b_absent_without_is_home(self):
        """Model B needs is_home + opp_net_rtg — without them it should be absent."""
        svc = _make_service_with_models()
        records = _fake_records(20)
        result = svc._predict_from_records(records, None, None, None, None)
        for v in result.values():
            assert "model_b" not in v

    def test_model_b_present_with_context(self):
        svc = _make_service_with_models()
        records = _fake_records(20)
        result = svc._predict_from_records(records, True, 2.0, None, None)
        for v in result.values():
            assert "model_b" in v

    def test_empty_records_returns_empty_dict(self):
        svc = _make_service_with_models()
        result = svc._predict_from_records([], None, None, None, None)
        assert result == {}


# ---------------------------------------------------------------------------
# predict_next_game — still works after refactor
# ---------------------------------------------------------------------------

class TestPredictNextGameHistorical:
    def test_delegates_to_predict_from_records(self):
        from services.elasticity_service import ElasticityService

        svc = _make_service_with_models()
        records = _fake_records(20)

        # Patch _hist.get_team_history to return synthetic records
        with patch.object(svc._hist, "get_team_history", return_value=records) as mock_get:
            result = svc.predict_next_game("T1", "2024-25")
            mock_get.assert_called_once_with("T1", "2024-25")

        assert "net_rtg" in result

    def test_returns_error_when_no_history(self):
        from services.elasticity_service import ElasticityService

        svc = _make_service_with_models()
        with patch.object(svc._hist, "get_team_history", return_value=[]):
            result = svc.predict_next_game("UNKNOWN", "2024-25")
        assert "error" in result


# ---------------------------------------------------------------------------
# predict_next_game_live — new method
# ---------------------------------------------------------------------------

class TestPredictNextGameLive:
    def test_uses_live_history_adapter(self):
        """predict_next_game_live must call LiveHistoryAdapter.get_team_history."""
        from services.elasticity_service import ElasticityService

        svc = _make_service_with_models()
        records = _fake_records(20)

        with patch(
            "services.elasticity_service.LiveHistoryAdapter"
        ) as MockAdapter:
            instance = MockAdapter.return_value
            instance.get_team_history.return_value = records

            result = svc.predict_next_game_live(
                live_collection="FEB_2526_Liga",
                team_name="Club Baloncesto Test",
                is_fbcyl=False,
            )
            instance.get_team_history.assert_called_once_with(
                "FEB_2526_Liga", "Club Baloncesto Test", False
            )

        assert "net_rtg" in result

    def test_returns_error_when_adapter_empty(self):
        from services.elasticity_service import ElasticityService

        svc = _make_service_with_models()
        with patch("services.elasticity_service.LiveHistoryAdapter") as MockAdapter:
            MockAdapter.return_value.get_team_history.return_value = []
            result = svc.predict_next_game_live(
                live_collection="FEB_2526_Liga",
                team_name="Nonexistent",
                is_fbcyl=False,
            )
        assert "error" in result

    def test_fbcyl_flag_forwarded_to_adapter(self):
        from services.elasticity_service import ElasticityService

        svc = _make_service_with_models()
        records = _fake_records(20)
        with patch("services.elasticity_service.LiveHistoryAdapter") as MockAdapter:
            MockAdapter.return_value.get_team_history.return_value = records
            svc.predict_next_game_live(
                live_collection="FBCYL_Temporada_20252026",
                team_name="BALONCESTO TEST",
                is_fbcyl=True,
            )
            MockAdapter.return_value.get_team_history.assert_called_once_with(
                "FBCYL_Temporada_20252026", "BALONCESTO TEST", True
            )

    def test_model_b_works_in_live_mode(self):
        from services.elasticity_service import ElasticityService

        svc = _make_service_with_models()
        records = _fake_records(20)
        with patch("services.elasticity_service.LiveHistoryAdapter") as MockAdapter:
            MockAdapter.return_value.get_team_history.return_value = records
            result = svc.predict_next_game_live(
                live_collection="FEB_2526_Liga",
                team_name="Team T1",
                is_fbcyl=False,
                is_home=True,
                opp_net_rtg=3.5,
            )
        for v in result.values():
            assert "model_b" in v


# ---------------------------------------------------------------------------
# Router dispatch — via FastAPI TestClient
# ---------------------------------------------------------------------------

class TestPredictRouterDispatch:
    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from src.api.routers.analysis import router
        from src.api.deps import get_db

        app = FastAPI()
        app.include_router(router, prefix="/analysis")

        mock_db = MagicMock()
        mock_db.connection.is_connected.return_value = True
        app.dependency_overrides[get_db] = lambda: mock_db
        return TestClient(app)

    def test_live_dispatch_calls_predict_next_game_live(self, client):
        with patch(
            "src.services.elasticity_service.ElasticityService.predict_next_game_live",
            return_value={"net_rtg": {"model_a": {"estimate": 1.0, "ci_low": 0.5, "ci_high": 1.5, "r2": 0.1}}},
        ) as mock_live:
            resp = client.get(
                "/analysis/elasticity/predict/_live",
                params={
                    "live_collection": "FEB_2526_Liga",
                    "live_team_id":    "Club Test",
                    "live_is_fbcyl":   "false",
                },
            )
        assert resp.status_code == 200
        mock_live.assert_called_once()

    def test_live_mode_missing_team_name_returns_422(self, client):
        resp = client.get(
            "/analysis/elasticity/predict/_live",
            params={"live_collection": "FEB_2526_Liga"},
        )
        assert resp.status_code == 422

    def test_historical_dispatch_calls_predict_next_game(self, client):
        with patch(
            "src.services.elasticity_service.ElasticityService.predict_next_game",
            return_value={"net_rtg": {"model_a": {"estimate": 1.0, "ci_low": 0.5, "ci_high": 1.5, "r2": 0.1}}},
        ) as mock_hist:
            resp = client.get(
                "/analysis/elasticity/predict/TEAM_123",
                params={"season": "2024-25"},
            )
        assert resp.status_code == 200
        mock_hist.assert_called_once()

    def test_historical_mode_missing_season_returns_422(self, client):
        resp = client.get("/analysis/elasticity/predict/TEAM_123")
        assert resp.status_code == 422
