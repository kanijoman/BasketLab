"""Elasticity model fitting and inference helpers.

Pure-computation functions extracted from elasticity_service.py.
Importable by backtesting_service and monte_carlo_service.
"""

from __future__ import annotations

import warnings
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ── shared constants ──────────────────────────────────────────────────────────
TARGET_STATS = ["net_rtg", "ortg", "drtg", "efg_pct", "tov_rate", "oreb_pct"]
ROLLING_WINDOWS = [3, 5, 10]
BOOTSTRAP_ITERATIONS = 500
CI_LOW, CI_HIGH = 5, 95  # 90 % CI


def _build_dataset(
    records: List[Dict[str, Any]],
    stat: str,
    extra_features: bool = False,
) -> Tuple[np.ndarray, np.ndarray, int]:
    """Build (X, y, n_teams) arrays for Ridge fitting.

    Each row i generates a sample where:
      - X[i] = [roll3, roll5, roll10] (optionally + [is_home, opp_bucket])
      - y[i] = stat value in game i (the "next game" relative to the window)
    """
    by_team: Dict[str, List[Dict]] = defaultdict(list)
    for rec in records:
        tid = rec.get("team_id") or rec.get("team_name", "")
        if tid:
            by_team[tid].append(rec)
    for tid in by_team:
        by_team[tid].sort(key=lambda r: r.get("date") or datetime.min)

    all_net_rtg = [r.get("net_rtg") for r in records if r.get("net_rtg") is not None]
    q33 = float(np.percentile(all_net_rtg, 33)) if all_net_rtg else 0.0
    q67 = float(np.percentile(all_net_rtg, 67)) if all_net_rtg else 0.0

    X_rows: List[List[float]] = []
    y_vals: List[float] = []
    max_window = max(ROLLING_WINDOWS)

    for tid, games in by_team.items():
        vals = [g.get(stat) for g in games]
        if len(vals) < max_window + 1:
            continue
        for i in range(max_window, len(vals)):
            y_val = vals[i]
            if y_val is None:
                continue
            features: List[float] = []
            for w in ROLLING_WINDOWS:
                window = [v for v in vals[i - w: i] if v is not None]
                features.append(float(np.mean(window)) if window else 0.0)
            if extra_features:
                is_home = float(games[i].get("is_home", 0))
                opp_nr = games[i].get("opp_net_rtg") or 0.0
                if opp_nr >= q67:
                    bucket = 1.0
                elif opp_nr <= q33:
                    bucket = -1.0
                else:
                    bucket = 0.0
                features += [is_home, bucket]
            X_rows.append(features)
            y_vals.append(float(y_val))

    if not X_rows:
        return np.empty((0, 0)), np.empty(0), 0

    return np.array(X_rows), np.array(y_vals), len(by_team)


def _fit_ridge_with_bootstrap(
    X: np.ndarray,
    y: np.ndarray,
) -> Optional[Dict[str, Any]]:
    """Fit a RidgeCV model and compute Bootstrap CIs.

    Returns a serialisable dict or None if not enough samples.
    """
    from sklearn.linear_model import Ridge, RidgeCV
    from sklearn.preprocessing import StandardScaler

    if len(y) < 20:
        return None

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ridge = RidgeCV(alphas=[0.01, 0.1, 1.0, 10.0, 100.0], cv=5)
        ridge.fit(X_scaled, y)

    coef = ridge.coef_.tolist()
    intercept = float(ridge.intercept_)
    alpha = float(ridge.alpha_)

    rng = np.random.default_rng(42)
    boot_coefs: List[List[float]] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        idx = rng.integers(0, len(y), len(y))
        X_b, y_b = X_scaled[idx], y[idx]
        if len(set(y_b)) < 2:
            continue
        try:
            m = Ridge(alpha=alpha)
            m.fit(X_b, y_b)
            boot_coefs.append(m.coef_.tolist())
        except Exception:
            pass

    ci_low = ci_high = None
    if boot_coefs:
        arr = np.array(boot_coefs)
        ci_low  = np.percentile(arr, CI_LOW,  axis=0).tolist()
        ci_high = np.percentile(arr, CI_HIGH, axis=0).tolist()

    y_pred = ridge.predict(X_scaled)
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = round(1 - ss_res / ss_tot, 4) if ss_tot > 0 else 0.0

    return {
        "coef":          coef,
        "intercept":     intercept,
        "alpha":         alpha,
        "r2_train":      r2,
        "n_samples":     len(y),
        "ci_low":        ci_low,
        "ci_high":       ci_high,
        "scaler_mean":   scaler.mean_.tolist(),
        "scaler_scale":  scaler.scale_.tolist(),
    }


def _predict_with_ci(
    model_doc: Dict[str, Any],
    rolling_features: List[float],
    extra_features: Optional[List[float]] = None,
) -> Dict[str, float]:
    """Apply a stored model to produce a point estimate + CI."""
    features = list(rolling_features)
    if extra_features:
        features += list(extra_features)

    x = np.array(features, dtype=float)
    mean  = np.array(model_doc["scaler_mean"])
    scale = np.array(model_doc["scaler_scale"])
    x_scaled = (x - mean) / scale

    coef      = np.array(model_doc["coef"])
    intercept = model_doc["intercept"]
    estimate  = float(np.dot(coef, x_scaled) + intercept)

    ci_low_coef  = model_doc.get("ci_low")
    ci_high_coef = model_doc.get("ci_high")
    if ci_low_coef and ci_high_coef:
        low  = float(np.dot(np.array(ci_low_coef),  x_scaled) + intercept)
        high = float(np.dot(np.array(ci_high_coef), x_scaled) + intercept)
    else:
        low = high = estimate

    return {
        "estimate": round(estimate, 2),
        "ci_low":   round(min(low, high), 2),
        "ci_high":  round(max(low, high), 2),
        "r2":       model_doc.get("r2_train", 0.0),
    }
