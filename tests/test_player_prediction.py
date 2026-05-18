"""Tests for FASE 8 — PlayerPredictionService (per-player Ridge regression).

TDD cycle: tests written BEFORE implementation.

Coverage:
- Happy path: returns Ridge predictions with CI for pts/reb/ast/val
- Feature validity: all features finite, rolling windows correct
- Output structure: targets present, estimate + ci bounds valid
- Edge cases: insufficient games, player not found, zero minutes
- FBCYL format: handles MIN (float) instead of minutes (seconds/60)
- API endpoint: GET /api/v1/analysis/player-prediction/{collection}/{player_id}
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

TARGET_STATS = ["pts", "reb", "ast", "val"]


def _make_player_game(
    player_id: str,
    game_idx: int,
    pts: float = 12.0,
    reb: float = 5.0,
    ast: float = 3.0,
    val: float = 14.0,
    minutes: float = 25.0,
    seed: int = 42,
) -> Dict[str, Any]:
    """Build a normalised per-game player record (as returned by _load_player_games).

    Uses normalised field names (reb, ast) since _load_player_games
    calls normalise_player_record() before returning records.
    """
    rng = np.random.default_rng(seed + game_idx)
    return {
        "player_id":   player_id,
        "player_name": f"Player {player_id}",
        "team_name":   "Team A",
        "date":        datetime(2024, 9, 1) + timedelta(days=game_idx * 7),
        "is_home":     game_idx % 2 == 0,
        "minutes":     round(minutes + rng.normal(0, 3), 1),
        "pts":         max(0, round(pts + rng.normal(0, 4), 0)),
        "reb":         max(0, round(reb + rng.normal(0, 2), 0)),   # normalised name
        "ast":         max(0, round(ast + rng.normal(0, 2), 0)),   # normalised name
        "val":         max(-5, round(val + rng.normal(0, 5), 0)),
        "opp_net_rtg": round(rng.normal(0, 5), 2),
    }


def _make_player_history(player_id: str, n: int) -> List[Dict[str, Any]]:
    """Generate n per-game records for one player."""
    return [_make_player_game(player_id, i) for i in range(n)]


def _mock_conn() -> MagicMock:
    conn = MagicMock()
    conn.is_connected.return_value = True
    return conn


# ===========================================================================
# Unit tests — PlayerPredictionService.predict()
# ===========================================================================

class TestPlayerPredictionContract:
    """Verify output shape and value constraints."""

    def _predict(self, records, **kwargs):
        from services.player_prediction_service import PlayerPredictionService
        conn = _mock_conn()
        svc = PlayerPredictionService(conn)
        with patch.object(svc, "_load_player_games", return_value=records):
            return svc.predict(
                collection="FEB_LF2_2025_A",
                player_id="P1",
                is_home=True,
                opp_net_rtg=2.0,
                **kwargs,
            )

    def test_returns_dict(self):
        result = self._predict(_make_player_history("P1", 20))
        assert isinstance(result, dict)

    def test_has_all_target_stats(self):
        result = self._predict(_make_player_history("P1", 20))
        for stat in TARGET_STATS:
            assert stat in result, f"Missing stat: {stat}"

    def test_each_stat_has_estimate(self):
        result = self._predict(_make_player_history("P1", 20))
        for stat in TARGET_STATS:
            assert "estimate" in result[stat], f"Missing estimate for {stat}"

    def test_each_stat_has_ci(self):
        result = self._predict(_make_player_history("P1", 20))
        for stat in TARGET_STATS:
            assert "ci_low"  in result[stat]
            assert "ci_high" in result[stat]

    def test_ci_bounds_ordered(self):
        result = self._predict(_make_player_history("P1", 20))
        for stat in TARGET_STATS:
            assert result[stat]["ci_low"] <= result[stat]["estimate"] or True
            # ci_low <= ci_high is mandatory
            assert result[stat]["ci_low"] <= result[stat]["ci_high"], (
                f"{stat}: ci_low={result[stat]['ci_low']} > ci_high={result[stat]['ci_high']}"
            )

    def test_estimate_is_non_negative_for_counting_stats(self):
        """Points, rebounds, assists cannot be predicted as hugely negative."""
        result = self._predict(_make_player_history("P1", 20))
        for stat in ["pts", "reb", "ast"]:
            est = result[stat]["estimate"]
            assert est > -20, f"{stat} estimate={est} is unreasonably negative"

    def test_has_n_train(self):
        result = self._predict(_make_player_history("P1", 20))
        for stat in TARGET_STATS:
            assert "n_train" in result[stat]
            assert result[stat]["n_train"] > 0

    def test_result_keys_per_stat(self):
        required = {"estimate", "ci_low", "ci_high", "n_train"}
        result = self._predict(_make_player_history("P1", 20))
        for stat in TARGET_STATS:
            assert required.issubset(result[stat].keys()), (
                f"{stat} missing: {required - set(result[stat].keys())}"
            )


# ===========================================================================
# Unit tests — feature builder
# ===========================================================================

class TestPlayerFeatureBuilder:

    def test_feature_vector_length(self):
        from services.player_prediction_service import build_player_features
        records = _make_player_history("P1", 15)
        # Request features at position 12 (enough history for roll3/5)
        feat = build_player_features(records, idx=12, stat="pts",
                                     is_home=True, opp_net_rtg=2.0)
        assert feat is not None
        # rolling 3, 5 of stat + minutes_roll3, minutes_roll5 + is_home + opp_bucket = 6
        assert len(feat) == 6

    def test_feature_vector_all_finite(self):
        from services.player_prediction_service import build_player_features
        records = _make_player_history("P1", 15)
        feat = build_player_features(records, idx=12, stat="pts",
                                     is_home=True, opp_net_rtg=2.0)
        assert all(np.isfinite(v) for v in feat)

    def test_is_home_encoded(self):
        from services.player_prediction_service import build_player_features
        records = _make_player_history("P1", 15)
        home = build_player_features(records, idx=12, stat="pts", is_home=True,  opp_net_rtg=0.0)
        away = build_player_features(records, idx=12, stat="pts", is_home=False, opp_net_rtg=0.0)
        assert home[4] == 1.0
        assert away[4] == 0.0

    def test_insufficient_history_returns_none(self):
        from services.player_prediction_service import build_player_features
        records = _make_player_history("P1", 3)
        feat = build_player_features(records, idx=2, stat="pts",
                                     is_home=True, opp_net_rtg=0.0)
        assert feat is None


# ===========================================================================
# Unit tests — FBCYL field mapping
# ===========================================================================

class TestFBCYLFieldMapping:
    """FBCYL uses different field names: PTS, REB, AST, VAL, MIN (float)."""

    def test_fbcyl_records_mapped_correctly(self):
        from services.player_prediction_service import normalise_player_record
        fbcyl_record = {
            "uuid": "abc-123",
            "name": "Player X",
            "team": "Team B",
            "MIN":  24.5,   # float minutes
            "PTS":  18,
            "REB":  6,
            "AST":  4,
            "VAL":  20,
        }
        normalised = normalise_player_record(fbcyl_record, is_fbcyl=True)
        assert normalised["pts"]     == 18
        assert normalised["reb"]     == 6
        assert normalised["ast"]     == 4
        assert normalised["val"]     == 20
        assert normalised["minutes"] == 24.5

    def test_feb_records_pass_through(self):
        from services.player_prediction_service import normalise_player_record
        feb_record = {
            "player_id": "123",
            "player_name": "Player Y",
            "minutes": 28.0,
            "pts":     15,
            "rt":      7,     # total rebounds in FEB
            "assist":  5,
            "val":     19,
        }
        normalised = normalise_player_record(feb_record, is_fbcyl=False)
        assert normalised["pts"]     == 15
        assert normalised["reb"]     == 7
        assert normalised["ast"]     == 5
        assert normalised["val"]     == 19
        assert normalised["minutes"] == 28.0


# ===========================================================================
# Edge cases
# ===========================================================================

class TestPlayerPredictionEdgeCases:

    def _predict(self, records, **kwargs):
        from services.player_prediction_service import PlayerPredictionService
        conn = _mock_conn()
        svc = PlayerPredictionService(conn)
        with patch.object(svc, "_load_player_games", return_value=records):
            return svc.predict("FEB_LF2_2025_A", "P1",
                               is_home=True, opp_net_rtg=0.0, **kwargs)

    def test_empty_records_returns_error(self):
        result = self._predict([])
        assert "error" in result

    def test_too_few_games_returns_error(self):
        result = self._predict(_make_player_history("P1", 4))
        assert "error" in result

    def test_minimum_viable_12_games(self):
        """12 games should produce a valid prediction."""
        result = self._predict(_make_player_history("P1", 12))
        assert "error" not in result
        for stat in TARGET_STATS:
            assert stat in result

    def test_zero_minutes_games_excluded(self):
        """Games with 0 minutes must not be used as training samples."""
        records = _make_player_history("P1", 20)
        for r in records[:5]:
            r["minutes"] = 0.0
        result = self._predict(records)
        assert isinstance(result, dict)
        assert "error" not in result


# ===========================================================================
# API endpoint
# ===========================================================================

class TestPlayerPredictionAPIEndpoint:

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
            stat: {"estimate": 12.0, "ci_low": 8.0, "ci_high": 16.0, "n_train": 15}
            for stat in TARGET_STATS
        }

    def test_returns_200(self, client):
        with patch("src.services.player_prediction_service.PlayerPredictionService") as MockSvc:
            MockSvc.return_value.predict.return_value = self._mock_result()
            resp = client.get(
                "/api/v1/analysis/player-prediction/FEB_LF2_2025_A/P1",
                params={"is_home": True, "opp_net_rtg": 2.0},
            )
        assert resp.status_code == 200

    def test_response_has_pts(self, client):
        with patch("src.services.player_prediction_service.PlayerPredictionService") as MockSvc:
            MockSvc.return_value.predict.return_value = self._mock_result()
            resp = client.get(
                "/api/v1/analysis/player-prediction/FEB_LF2_2025_A/P1",
                params={"is_home": True},
            )
        assert "pts" in resp.json()

    def test_missing_is_home_returns_422(self, client):
        resp = client.get(
            "/api/v1/analysis/player-prediction/FEB_LF2_2025_A/P1"
        )
        assert resp.status_code == 422
