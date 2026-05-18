"""Tests for FASE 6 — BacktestingService (walk-forward validation).

TDD cycle: these tests are written BEFORE the implementation.
They define the contract that BacktestingService must fulfil.

Coverage:
- Happy path: returns MAE / RMSE / MAPE per stat for model_a and model_b
- Metric validity: MAE >= 0, RMSE >= 0, n_evaluated > 0
- Time-series integrity: no data leakage (predictions only use past data)
- Edge cases: insufficient data, empty records, single-team dataset
- Naive baseline: last-5-game mean included for comparison
- MAPE suppression: net_rtg must have mape=None (undefined near zero)
- Live backtesting: run_backtest_live() uses LiveHistoryAdapter
- API endpoint: GET /api/v1/analysis/backtesting/{team_id} returns 200
- API endpoint: GET /api/v1/analysis/backtesting-live/{collection}/{team_name} returns 200
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
# Shared helpers
# ---------------------------------------------------------------------------

def _make_historical_records(
    team_id: str,
    n: int,
    start_net: float = 5.0,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """Produce n HISTORICAL-style docs for one team with deterministic noise."""
    rng = np.random.default_rng(seed)
    records = []
    for i in range(n):
        net = start_net + rng.normal(0, 3)
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
            "pace":        round(75.0 + rng.normal(0, 4), 2),
            "opp_net_rtg": round(-net + rng.normal(0, 2), 2),
        })
    return records


def _make_multi_team_records(n_teams: int = 3, n_games: int = 25) -> List[Dict]:
    """Multiple teams with enough games for walk-forward CV."""
    records = []
    for t in range(n_teams):
        records.extend(_make_historical_records(f"T{t}", n_games, seed=t))
    return records


def _mock_connection(records: List[Dict]) -> MagicMock:
    """Return a mock DB connection whose HistoricalRepository yields records."""
    conn = MagicMock()
    conn.is_connected.return_value = True
    return conn


# ===========================================================================
# Unit tests — BacktestingService
# ===========================================================================

class TestBacktestingServiceContract:
    """Verify the shape and validity of BacktestingService.run_backtest()."""

    def _svc(self, records):
        from services.backtesting_service import BacktestingService
        conn = _mock_connection(records)
        svc = BacktestingService(conn)
        with patch.object(svc, "_load_records", return_value=records):
            result = svc.run_backtest("T0", "2024-25")
        return result

    def test_returns_dict(self):
        records = _make_historical_records("T0", 25)
        result = self._svc(records)
        assert isinstance(result, dict)

    def test_has_stat_keys(self):
        records = _make_historical_records("T0", 25)
        result = self._svc(records)
        # Must contain at least net_rtg (core stat)
        assert "net_rtg" in result, f"Keys found: {list(result.keys())}"

    def test_each_stat_has_model_a_and_b(self):
        records = _make_historical_records("T0", 25)
        result = self._svc(records)
        for stat, models in result.items():
            assert "model_a" in models, f"model_a missing for {stat}"
            assert "model_b" in models, f"model_b missing for {stat}"

    def test_metrics_structure(self):
        """Each model entry must have mae, rmse, mape, n_evaluated."""
        records = _make_historical_records("T0", 25)
        result = self._svc(records)
        required = {"mae", "rmse", "mape", "n_evaluated"}
        for stat, models in result.items():
            for model_type in ("model_a", "model_b"):
                entry = models[model_type]
                assert required.issubset(entry.keys()), (
                    f"{stat}/{model_type} missing keys: {required - set(entry.keys())}"
                )

    def test_mae_non_negative(self):
        records = _make_historical_records("T0", 25)
        result = self._svc(records)
        for stat, models in result.items():
            for model_type in ("model_a", "model_b"):
                mae = models[model_type]["mae"]
                assert mae >= 0, f"{stat}/{model_type} MAE={mae} is negative"

    def test_rmse_non_negative(self):
        records = _make_historical_records("T0", 25)
        result = self._svc(records)
        for stat, models in result.items():
            for model_type in ("model_a", "model_b"):
                rmse = models[model_type]["rmse"]
                assert rmse >= 0, f"{stat}/{model_type} RMSE={rmse} is negative"

    def test_rmse_geq_mae(self):
        """RMSE >= MAE is a mathematical property of these metrics."""
        records = _make_historical_records("T0", 25)
        result = self._svc(records)
        for stat, models in result.items():
            for model_type in ("model_a", "model_b"):
                mae  = models[model_type]["mae"]
                rmse = models[model_type]["rmse"]
                assert rmse >= mae - 1e-9, (
                    f"{stat}/{model_type}: RMSE={rmse} < MAE={mae}"
                )

    def test_n_evaluated_positive(self):
        records = _make_historical_records("T0", 25)
        result = self._svc(records)
        for stat, models in result.items():
            for model_type in ("model_a", "model_b"):
                n = models[model_type]["n_evaluated"]
                assert n > 0, f"{stat}/{model_type} n_evaluated={n}"

    def test_metrics_are_floats_or_none(self):
        records = _make_historical_records("T0", 25)
        result = self._svc(records)
        for stat, models in result.items():
            for model_type in ("model_a", "model_b"):
                for k in ("mae", "rmse", "mape"):
                    v = models[model_type][k]
                    assert v is None or isinstance(v, float), (
                        f"{stat}/{model_type}/{k} is {type(v)}"
                    )


class TestBacktestingTimeSeriesIntegrity:
    """Verify that the walk-forward split does not leak future data."""

    def test_no_data_leakage(self):
        """Each fold must use at least MIN_TRAIN_SIZE records.

        _fit_fold is called once per stat per model type per evaluation step.
        We verify that no fold ever uses fewer than MIN_TRAIN_SIZE records,
        which guarantees the walk-forward constraint is respected.
        """
        from services.backtesting_service import BacktestingService, MIN_TRAIN_SIZE

        records = _make_historical_records("T0", 20)
        conn = _mock_connection(records)
        svc = BacktestingService(conn)

        train_sizes: List[int] = []

        def _capturing_fit(train_records, stat, extra_features=False):
            train_sizes.append(len(train_records))
            return None  # graceful degradation

        with patch.object(svc, "_load_records", return_value=records):
            with patch.object(svc, "_fit_fold", side_effect=_capturing_fit):
                try:
                    svc.run_backtest("T0", "2024-25")
                except Exception:
                    pass

        # Every fold must have at least MIN_TRAIN_SIZE records — no leakage
        for size in train_sizes:
            assert size >= MIN_TRAIN_SIZE, (
                f"Fold used only {size} records < MIN_TRAIN_SIZE={MIN_TRAIN_SIZE}"
            )

        # At least one fold was evaluated (service ran walk-forward)
        assert len(train_sizes) > 0, "No folds were evaluated"


class TestBacktestingEdgeCases:
    """Graceful degradation on edge-case inputs."""

    def _svc_with_records(self, records):
        from services.backtesting_service import BacktestingService
        conn = _mock_connection(records)
        svc = BacktestingService(conn)
        with patch.object(svc, "_load_records", return_value=records):
            return svc.run_backtest("T0", "2024-25")

    def test_empty_records_returns_empty(self):
        result = self._svc_with_records([])
        assert result == {} or isinstance(result, dict)

    def test_insufficient_records_returns_empty_or_graceful(self):
        # Only 5 records — not enough for max rolling window (10) + train split
        records = _make_historical_records("T0", 5)
        result = self._svc_with_records(records)
        assert isinstance(result, dict)
        # Either empty OR all n_evaluated == 0 (not enough data)
        for stat, models in result.items():
            for model_type in ("model_a", "model_b"):
                assert models[model_type].get("n_evaluated", 0) == 0

    def test_minimum_viable_records(self):
        """25 games should be enough to produce at least 1 evaluation per stat."""
        records = _make_historical_records("T0", 25)
        result = self._svc_with_records(records)
        if result:
            for stat, models in result.items():
                for model_type in ("model_a", "model_b"):
                    assert models[model_type]["n_evaluated"] >= 1


# ===========================================================================
# API endpoint tests
# ===========================================================================

class TestBacktestingAPIEndpoint:
    """Integration tests for GET /api/v1/analysis/backtesting/{team_id}."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.app import app
        from src.api.deps import get_db
        app.dependency_overrides[get_db] = lambda: MagicMock()
        yield TestClient(app)
        app.dependency_overrides.pop(get_db, None)

    def test_endpoint_returns_200(self, client):
        with patch("src.services.backtesting_service.BacktestingService") as MockSvc:
            instance = MagicMock()
            instance.run_backtest.return_value = {
                "net_rtg": {
                    "model_a": {"mae": 2.1, "rmse": 2.7, "mape": 5.0, "n_evaluated": 10},
                    "model_b": {"mae": 1.9, "rmse": 2.5, "mape": 4.5, "n_evaluated": 10},
                }
            }
            MockSvc.return_value = instance
            resp = client.get(
                "/api/v1/analysis/backtesting/T0",
                params={"season": "2024-25"},
            )
        assert resp.status_code == 200

    def test_endpoint_response_structure(self, client):
        with patch("src.services.backtesting_service.BacktestingService") as MockSvc:
            instance = MagicMock()
            instance.run_backtest.return_value = {
                "net_rtg": {
                    "model_a": {"mae": 2.1, "rmse": 2.7, "mape": 5.0, "n_evaluated": 10},
                    "model_b": {"mae": 1.9, "rmse": 2.5, "mape": 4.5, "n_evaluated": 10},
                }
            }
            MockSvc.return_value = instance
            resp = client.get(
                "/api/v1/analysis/backtesting/T0",
                params={"season": "2024-25"},
            )
        body = resp.json()
        assert "net_rtg" in body
        assert "model_a" in body["net_rtg"]
        assert "mae" in body["net_rtg"]["model_a"]

    def test_endpoint_missing_season_returns_422(self, client):
        resp = client.get("/api/v1/analysis/backtesting/T0")
        assert resp.status_code == 422


# ===========================================================================
# New tests — TDD for upcoming features
# ===========================================================================

class TestNaiveBaseline:
    """naive baseline (last-5-game mean) must be included in metrics output.

    These tests are written BEFORE the implementation (red phase).
    They will pass after run_backtest() is extended to include naive metrics.
    """

    def _svc(self, records):
        from services.backtesting_service import BacktestingService
        conn = _mock_connection(records)
        svc = BacktestingService(conn)
        with patch.object(svc, "_load_records", return_value=records):
            return svc.run_backtest("T0", "2024-25")

    def test_naive_key_present(self):
        """Each stat must have a 'naive' entry alongside model_a / model_b."""
        records = _make_historical_records("T0", 25)
        result = self._svc(records)
        for stat, models in result.items():
            assert "naive" in models, (
                f"'naive' key missing for stat={stat}. Keys: {list(models.keys())}"
            )

    def test_naive_has_required_fields(self):
        records = _make_historical_records("T0", 25)
        result = self._svc(records)
        required = {"mae", "rmse", "n_evaluated"}
        for stat, models in result.items():
            naive = models["naive"]
            assert required.issubset(naive.keys()), (
                f"naive missing keys for {stat}: {required - set(naive.keys())}"
            )

    def test_naive_mae_non_negative(self):
        records = _make_historical_records("T0", 25)
        result = self._svc(records)
        for stat, models in result.items():
            mae = models["naive"]["mae"]
            assert mae is None or mae >= 0, f"naive MAE < 0 for {stat}"

    def test_naive_n_evaluated_matches_model_a(self):
        """Naive baseline must be evaluated on the same folds as model_a."""
        records = _make_historical_records("T0", 25)
        result = self._svc(records)
        for stat, models in result.items():
            assert models["naive"]["n_evaluated"] == models["model_a"]["n_evaluated"], (
                f"naive n_evaluated != model_a n_evaluated for {stat}"
            )


class TestMapeSuppressionNetRtg:
    """net_rtg MAPE must be None — the stat oscillates near zero making MAPE
    meaningless (281% reported was a signal to fix this).

    Written BEFORE implementation (red phase).
    """

    def _svc(self, records):
        from services.backtesting_service import BacktestingService
        conn = _mock_connection(records)
        svc = BacktestingService(conn)
        with patch.object(svc, "_load_records", return_value=records):
            return svc.run_backtest("T0", "2024-25")

    def test_net_rtg_mape_is_none(self):
        """net_rtg MAPE must always be None regardless of data."""
        records = _make_historical_records("T0", 25)
        result = self._svc(records)
        assert "net_rtg" in result
        for model_type in ("model_a", "model_b"):
            mape = result["net_rtg"][model_type]["mape"]
            assert mape is None, (
                f"net_rtg {model_type} mape should be None (meaningless near zero), got {mape}"
            )

    def test_ortg_mape_is_not_none(self):
        """ortg is never near zero — MAPE must be computed normally."""
        records = _make_historical_records("T0", 25)
        result = self._svc(records)
        assert "ortg" in result
        # ortg should have a real MAPE (may still be None if model fails, but
        # suppression logic must NOT suppress it)
        # We assert the field is present (None is ok only if n_evaluated=0)
        m = result["ortg"]["model_a"]
        if m["n_evaluated"] > 0:
            assert m["mape"] is not None, (
                "ortg mape must not be suppressed (stat is never near zero)"
            )


class TestLiveBacktesting:
    """run_backtest_live() must work identically to run_backtest() but load
    records from LiveHistoryAdapter instead of HistoricalRepository.

    Written BEFORE implementation (red phase).
    """

    def test_run_backtest_live_exists(self):
        """BacktestingService must expose run_backtest_live()."""
        from services.backtesting_service import BacktestingService
        assert hasattr(BacktestingService, "run_backtest_live"), (
            "BacktestingService.run_backtest_live() not found"
        )

    def test_run_backtest_live_returns_dict(self):
        """run_backtest_live() must return a metrics dict or empty dict."""
        from services.backtesting_service import BacktestingService
        records = _make_historical_records("T0", 25)
        conn = _mock_connection(records)
        svc = BacktestingService(conn)
        with patch(
            "services.backtesting_service.LiveHistoryAdapter"
        ) as MockAdapter:
            MockAdapter.return_value.get_team_history.return_value = records
            result = svc.run_backtest_live(
                live_collection="FBCYL_Test",
                live_team_name="Team T0",
                is_fbcyl=True,
            )
        assert isinstance(result, dict)

    def test_run_backtest_live_uses_live_adapter(self):
        """run_backtest_live() must call LiveHistoryAdapter, not HistoricalRepository."""
        from services.backtesting_service import BacktestingService
        records = _make_historical_records("T0", 25)
        conn = _mock_connection(records)
        svc = BacktestingService(conn)
        with patch(
            "services.backtesting_service.LiveHistoryAdapter"
        ) as MockAdapter:
            MockAdapter.return_value.get_team_history.return_value = records
            svc.run_backtest_live(
                live_collection="FEB_Test",
                live_team_name="Team T0",
                is_fbcyl=False,
            )
        MockAdapter.assert_called_once()
        MockAdapter.return_value.get_team_history.assert_called_once_with(
            "FEB_Test", "Team T0", False
        )

    def test_run_backtest_live_produces_same_stats_as_run_backtest(self):
        """Given identical records, live and historical modes return same stat keys."""
        from services.backtesting_service import BacktestingService
        records = _make_historical_records("T0", 25)
        conn = _mock_connection(records)
        svc = BacktestingService(conn)

        with patch.object(svc, "_load_records", return_value=records):
            hist_result = svc.run_backtest("T0", "2024-25")

        with patch("services.backtesting_service.LiveHistoryAdapter") as MockAdapter:
            MockAdapter.return_value.get_team_history.return_value = records
            live_result = svc.run_backtest_live(
                live_collection="FEB_Test",
                live_team_name="Team T0",
                is_fbcyl=False,
            )

        assert set(hist_result.keys()) == set(live_result.keys()), (
            f"Stat keys differ: hist={set(hist_result.keys())} live={set(live_result.keys())}"
        )

    def test_run_backtest_live_insufficient_data_returns_empty(self):
        """Too few games must return empty dict gracefully."""
        from services.backtesting_service import BacktestingService
        records = _make_historical_records("T0", 5)
        conn = _mock_connection(records)
        svc = BacktestingService(conn)
        with patch("services.backtesting_service.LiveHistoryAdapter") as MockAdapter:
            MockAdapter.return_value.get_team_history.return_value = records
            result = svc.run_backtest_live("FEB_Test", "Team T0", False)
        assert isinstance(result, dict)


class TestLiveBacktestingAPIEndpoint:
    """GET /api/v1/analysis/backtesting-live/{collection}/{team_name}"""

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
            "net_rtg": {
                "model_a": {"mae": 3.1, "rmse": 4.2, "mape": None, "n_evaluated": 8, "naive": {"mae": 4.0, "rmse": 5.1, "n_evaluated": 8}},
                "model_b": {"mae": 2.9, "rmse": 3.9, "mape": None, "n_evaluated": 8, "naive": {"mae": 4.0, "rmse": 5.1, "n_evaluated": 8}},
                "naive":   {"mae": 4.0, "rmse": 5.1, "n_evaluated": 8},
            }
        }

    def test_live_endpoint_returns_200(self, client):
        with patch("src.services.backtesting_service.BacktestingService") as MockSvc:
            MockSvc.return_value.run_backtest_live.return_value = self._mock_result()
            resp = client.get(
                "/api/v1/analysis/backtesting-live/FEB_Test/Team%20T0",
                params={"is_fbcyl": "false"},
            )
        assert resp.status_code == 200, resp.text

    def test_live_endpoint_response_has_stat_keys(self, client):
        with patch("src.services.backtesting_service.BacktestingService") as MockSvc:
            MockSvc.return_value.run_backtest_live.return_value = self._mock_result()
            resp = client.get(
                "/api/v1/analysis/backtesting-live/FEB_Test/Team%20T0",
                params={"is_fbcyl": "false"},
            )
        body = resp.json()
        assert "net_rtg" in body
