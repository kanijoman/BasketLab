"""Backtesting service — FASE 6: Walk-forward validation of elasticity models.

Evaluates how accurately the Ridge models (Modelo A / Modelo B) predict
real game outcomes by replaying the season chronologically:

  For each game i (from MIN_TRAIN_SIZE onwards):
    1. Train a Ridge model on games [0 … i-1]  (no future data leakage)
    2. Predict stat value at game i
    3. Collect error vs the actual observed value

Metrics returned per stat per model:
  - mae:          Mean Absolute Error
  - rmse:         Root Mean Squared Error
  - mape:         Mean Absolute Percentage Error (None if any actual == 0)
  - n_evaluated:  Number of folds evaluated
"""

from __future__ import annotations

import warnings
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from database.historical_repository import HistoricalRepository
from services.elasticity_service import (
    TARGET_STATS,
    ROLLING_WINDOWS,
    _fit_ridge_with_bootstrap,
    _predict_with_ci,
)

# Minimum number of games needed to form the first training fold.
# Must be > max(ROLLING_WINDOWS) to build features + at least a few samples.
MIN_TRAIN_SIZE = 15
_MAX_WINDOW = max(ROLLING_WINDOWS)


class BacktestingService:
    """Walk-forward cross-validation for elasticity Ridge models."""

    def __init__(self, connection) -> None:
        self._conn = connection
        self._hist = HistoricalRepository(connection)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_backtest(
        self,
        team_id: str,
        season: str,
        leagues: Optional[List[str]] = None,
        competitions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run walk-forward backtesting for a team's season.

        Args:
            team_id:      Team identifier as stored in HISTORICAL.
            season:       Normalised season label ("2024-25").
            leagues:      Optional league filter (passed to data loader).
            competitions: Optional competition filter.

        Returns:
            ``{stat: {model_a: {mae, rmse, mape, n_evaluated},
                      model_b: {mae, rmse, mape, n_evaluated}}}``
        """
        records = self._load_records(team_id, season, leagues, competitions)
        if not records:
            return {}

        records = sorted(records, key=lambda r: r.get("date") or "")

        if len(records) < MIN_TRAIN_SIZE + 1:
            return _empty_result()

        result: Dict[str, Any] = {}
        for stat in TARGET_STATS:
            errors_a, errors_b = self._evaluate_stat(records, stat)
            result[stat] = {
                "model_a": _compute_metrics(errors_a),
                "model_b": _compute_metrics(errors_b),
            }

        return result

    # ------------------------------------------------------------------
    # Internal helpers (patchable in tests)
    # ------------------------------------------------------------------

    def _load_records(
        self,
        team_id: str,
        season: str,
        leagues: Optional[List[str]] = None,
        competitions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch team-season game history from HISTORICAL."""
        if not self._conn.is_connected():
            return []
        all_records = self._hist.get_seasons_for_elasticity(leagues, competitions)
        return [
            r for r in all_records
            if r.get("team_id") == team_id and r.get("season") == season
        ]

    def _fit_fold(
        self,
        train_records: List[Dict[str, Any]],
        stat: str,
        extra_features: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Fit a Ridge model on a training fold and return the model dict.

        Uses bootstrap CI when enough samples exist (>= 20); falls back to
        a plain Ridge fit for smaller folds so backtesting works on short
        seasons (20-30 games) without requiring a large initial window.
        """
        if len(train_records) < _MAX_WINDOW + 1:
            return None

        X_rows, y_vals = _build_fold_dataset(train_records, stat, extra_features)
        if len(y_vals) < 3:
            return None

        X = np.array(X_rows)
        y = np.array(y_vals)

        if len(y) >= 20:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return _fit_ridge_with_bootstrap(X, y)

        return _fit_ridge_simple(X, y)

    def _evaluate_stat(
        self,
        records: List[Dict[str, Any]],
        stat: str,
    ) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
        """Walk-forward evaluation for one stat.

        Returns:
            (errors_a, errors_b) — each is a list of (predicted, actual) pairs.
        """
        errors_a: List[Tuple[float, float]] = []
        errors_b: List[Tuple[float, float]] = []

        for i in range(MIN_TRAIN_SIZE, len(records)):
            train = records[:i]
            actual = records[i].get(stat)
            if actual is None:
                continue

            rolling_feats = _rolling_features(records, i, stat)

            # Modelo A
            model_a = self._fit_fold(train, stat, extra_features=False)
            if model_a:
                pred_a = _predict_with_ci(model_a, rolling_feats)["estimate"]
                errors_a.append((pred_a, float(actual)))

            # Modelo B
            model_b = self._fit_fold(train, stat, extra_features=True)
            if model_b:
                is_home = float(records[i].get("is_home", 0))
                opp_nr = float(records[i].get("opp_net_rtg") or 0.0)
                extra = _opp_bucket_features(
                    opp_nr, [r.get("net_rtg") or 0.0 for r in train]
                )
                pred_b = _predict_with_ci(
                    model_b, rolling_feats, extra_features=[is_home] + extra
                )["estimate"]
                errors_b.append((pred_b, float(actual)))

        return errors_a, errors_b


# ---------------------------------------------------------------------------
# Pure helpers (no side effects)
# ---------------------------------------------------------------------------

def _fit_ridge_simple(X: np.ndarray, y: np.ndarray) -> Optional[Dict[str, Any]]:
    """Plain Ridge fit (no bootstrap CI) for small folds (< 20 samples).

    Returns the same dict shape as ``_fit_ridge_with_bootstrap`` so the rest
    of the pipeline (``_predict_with_ci``) can handle it transparently.
    """
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler()
    # Clip scale to avoid division by zero on constant features
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        X_scaled = scaler.fit_transform(X)
    scale = np.where(scaler.scale_ == 0, 1.0, scaler.scale_)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ridge = Ridge(alpha=1.0)
        ridge.fit(X_scaled, y)

    return {
        "coef":         ridge.coef_.tolist(),
        "intercept":    float(ridge.intercept_),
        "alpha":        1.0,
        "r2_train":     0.0,
        "n_samples":    len(y),
        "ci_low":       None,
        "ci_high":      None,
        "scaler_mean":  scaler.mean_.tolist(),
        "scaler_scale": scale.tolist(),
    }


def _build_fold_dataset(
    records: List[Dict[str, Any]],
    stat: str,
    extra_features: bool,
) -> Tuple[List[List[float]], List[float]]:
    """Build (X_rows, y_vals) for a training fold using rolling windows."""
    vals = [r.get(stat) for r in records]
    net_rtgs = [r.get("net_rtg") or 0.0 for r in records]
    q33, q67 = _quartiles_33_67(net_rtgs)

    X_rows: List[List[float]] = []
    y_vals: List[float] = []

    for i in range(_MAX_WINDOW, len(vals)):
        if vals[i] is None:
            continue
        features = _rolling_features(records, i, stat)
        if extra_features:
            is_home = float(records[i].get("is_home", 0))
            opp_nr = float(records[i].get("opp_net_rtg") or 0.0)
            bucket = _bucket(opp_nr, q33, q67)
            features = features + [is_home, bucket]
        X_rows.append(features)
        y_vals.append(float(vals[i]))

    return X_rows, y_vals


def _rolling_features(
    records: List[Dict[str, Any]], idx: int, stat: str
) -> List[float]:
    """Compute rolling-window averages of stat for position idx (exclusive)."""
    vals = [r.get(stat) for r in records[:idx]]
    features: List[float] = []
    for w in ROLLING_WINDOWS:
        window = [v for v in vals[-w:] if v is not None]
        features.append(float(np.mean(window)) if window else 0.0)
    return features


def _quartiles_33_67(values: List[float]) -> Tuple[float, float]:
    """Return (33rd percentile, 67th percentile) of a list."""
    if not values:
        return 0.0, 0.0
    arr = np.array(values, dtype=float)
    return float(np.percentile(arr, 33)), float(np.percentile(arr, 67))


def _bucket(opp_net_rtg: float, q33: float, q67: float) -> float:
    """Map opponent net_rtg to strength bucket (-1 / 0 / +1)."""
    if opp_net_rtg >= q67:
        return 1.0
    if opp_net_rtg <= q33:
        return -1.0
    return 0.0


def _opp_bucket_features(
    opp_net_rtg: float, train_net_rtgs: List[float]
) -> List[float]:
    """Return [opp_bucket] computed from training set quartiles."""
    q33, q67 = _quartiles_33_67(train_net_rtgs)
    return [_bucket(opp_net_rtg, q33, q67)]


def _compute_metrics(
    errors: List[Tuple[float, float]],
) -> Dict[str, Any]:
    """Compute MAE, RMSE, MAPE from (predicted, actual) pairs."""
    n = len(errors)
    if n == 0:
        return {"mae": None, "rmse": None, "mape": None, "n_evaluated": 0}

    preds = np.array([e[0] for e in errors])
    actuals = np.array([e[1] for e in errors])
    diffs = np.abs(preds - actuals)

    mae = float(np.mean(diffs))
    rmse = float(np.sqrt(np.mean(diffs ** 2)))

    mape: Optional[float] = None
    nonzero = actuals != 0
    if nonzero.any():
        mape = float(np.mean(diffs[nonzero] / np.abs(actuals[nonzero])) * 100)

    return {
        "mae":         round(mae, 4),
        "rmse":        round(rmse, 4),
        "mape":        round(mape, 4) if mape is not None else None,
        "n_evaluated": n,
    }


def _empty_result() -> Dict[str, Any]:
    """Return a result dict signalling no data was available per stat."""
    empty_metrics = {"mae": None, "rmse": None, "mape": None, "n_evaluated": 0}
    return {
        stat: {"model_a": dict(empty_metrics), "model_b": dict(empty_metrics)}
        for stat in TARGET_STATS
    }
