"""GBM (HistGradientBoosting) elasticity models — Modelo D.

Fits three complementary models: mean (squared_error), q05, q95
(quantile losses) to provide both point estimates and prediction intervals.
Models are serialised as base64-encoded joblib blobs for MongoDB storage.

Usage: only for next-game point prediction (ElasticityService).
Not used in Monte Carlo simulation (MC requires Ridge for clean Gaussian sampling).
"""

from __future__ import annotations

import base64
import io
import warnings
from typing import Any, Dict, List, Optional

import numpy as np


def _fit_gbm_with_quantiles(
    X: np.ndarray,
    y: np.ndarray,
    sample_weight: Optional[np.ndarray] = None,
) -> Optional[Dict[str, Any]]:
    """Fit mean + q05 + q95 HistGradientBoosting models.

    Args:
        X:             Feature matrix (already built, not scaled — GBM is
                       invariant to scale, but we apply StandardScaler anyway
                       for consistency with Ridge models).
        y:             Target vector.
        sample_weight: Optional per-sample weights.

    Returns:
        Serialisable dict with base64-encoded models, or None on failure.
    """
    try:
        from sklearn.ensemble import HistGradientBoostingRegressor
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return None

    if len(y) < 20:
        return None

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    sw = None
    if sample_weight is not None:
        sw = sample_weight / sample_weight.sum() * len(y)

    fitted: Dict[str, Any] = {}
    configs = [
        ("mean",  {"loss": "squared_error"}),
        ("q05",   {"loss": "quantile", "quantile": 0.05}),
        ("q95",   {"loss": "quantile", "quantile": 0.95}),
    ]
    for key, kwargs in configs:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                m = HistGradientBoostingRegressor(max_iter=300, random_state=42, **kwargs)
                m.fit(X_scaled, y, sample_weight=sw)
                fitted[key] = m
            except Exception:
                return None

    y_pred  = fitted["mean"].predict(X_scaled)
    ss_res  = float(np.sum((y - y_pred) ** 2))
    ss_tot  = float(np.sum((y - y.mean()) ** 2))
    r2      = round(1 - ss_res / ss_tot, 4) if ss_tot > 0 else 0.0
    rmse    = round(float(np.sqrt(ss_res / len(y))), 4)

    def _serialise(model: Any) -> str:
        buf = io.BytesIO()
        import joblib
        joblib.dump(model, buf, compress=3)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    return {
        "gbm_mean":     _serialise(fitted["mean"]),
        "gbm_q05":      _serialise(fitted["q05"]),
        "gbm_q95":      _serialise(fitted["q95"]),
        "scaler_mean":  scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "r2_train":     r2,
        "rmse_train":   rmse,
        "n_samples":    len(y),
    }


def _predict_gbm(
    model_doc: Dict[str, Any],
    features: List[float],
) -> Dict[str, float]:
    """Run inference using stored GBM models.

    Returns the same shape as ``_predict_with_ci`` from _elasticity_models.
    """
    import joblib

    scaler_mean  = np.array(model_doc["scaler_mean"])
    scaler_scale = np.array(model_doc["scaler_scale"])
    x_scaled = ((np.array(features, dtype=float) - scaler_mean) / scaler_scale).reshape(1, -1)

    def _load(key: str) -> Any:
        buf = io.BytesIO(base64.b64decode(model_doc[key]))
        return joblib.load(buf)

    estimate = float(_load("gbm_mean").predict(x_scaled)[0])
    ci_low   = float(_load("gbm_q05").predict(x_scaled)[0])
    ci_high  = float(_load("gbm_q95").predict(x_scaled)[0])

    return {
        "estimate": round(estimate, 2),
        "ci_low":   round(min(ci_low, ci_high), 2),
        "ci_high":  round(max(ci_low, ci_high), 2),
        "r2":       model_doc.get("r2_train", 0.0),
    }
