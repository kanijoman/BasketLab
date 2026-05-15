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
ROLLING_WINDOWS   = [3, 5, 10]        # Modelo A / B (backward-compat)
ROLLING_WINDOWS_C = [3, 5, 10, 20]    # Modelo C / D (extended horizon)
BOOTSTRAP_ITERATIONS = 500
CI_LOW, CI_HIGH = 5, 95  # 90 % CI
TEMPORAL_DECAY = 0.02    # exponential decay: w_i = exp(-λ*(i-n)) for sample_weight

# Cross-stat driver features for Modelo C — roll3 of each listed stat is added
CROSS_STAT_FEATURES: Dict[str, List[str]] = {
    "net_rtg":  ["ortg",    "drtg"],
    "ortg":     ["efg_pct", "tov_rate"],
    "drtg":     ["oreb_pct"],
    "efg_pct":  ["ortg"],
    "tov_rate": ["ortg"],
    "oreb_pct": ["drtg"],
}


def _compute_sample_weights(n: int) -> np.ndarray:
    """Exponential-decay sample weights: recent samples weighted higher.

    w_i = exp(TEMPORAL_DECAY * (i - (n-1))), normalised so sum == n.
    """
    indices = np.arange(n, dtype=float)
    w = np.exp(TEMPORAL_DECAY * (indices - (n - 1)))
    return w / w.sum() * n  # keep effective count ≈ n for Ridge compatibility


def _build_dataset(
    records: List[Dict[str, Any]],
    stat: str,
    extra_features: bool = False,
    add_momentum: bool = False,
    extended_windows: bool = False,
    cross_stat_features: bool = False,
    opp_continuous: bool = False,
) -> Tuple[np.ndarray, np.ndarray, int]:
    """Build (X, y, n_teams) arrays for Ridge fitting.

    Feature columns per model type:
      Modelo A: [roll3, roll5, roll10]
      Modelo B: [roll3, roll5, roll10, is_home, opp_bucket]
      Modelo C: [roll3, roll5, roll10, roll20, momentum,
                 is_home, opp_net_rtg_continuous, cross_stat_roll3s...]

    Args:
        extra_features:    Add is_home + opp feature (Modelo B/C).
        add_momentum:      Add roll3−roll10 as momentum feature (Modelo C).
        extended_windows:  Use ROLLING_WINDOWS_C [3,5,10,20] (Modelo C).
        cross_stat_features: Add roll3 of driver stats (Modelo C).
        opp_continuous:    Use float opp_net_rtg instead of bucket (Modelo C).
    """
    windows = ROLLING_WINDOWS_C if extended_windows else ROLLING_WINDOWS
    max_window = max(windows)

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

    for tid, games in by_team.items():
        vals = [g.get(stat) for g in games]
        if len(vals) < max_window + 1:
            continue
        for i in range(max_window, len(vals)):
            y_val = vals[i]
            if y_val is None:
                continue
            features: List[float] = []

            # Rolling features for target stat
            roll_vals: List[float] = []
            for w in windows:
                window = [v for v in vals[i - w: i] if v is not None]
                rv = float(np.mean(window)) if window else 0.0
                features.append(rv)
                roll_vals.append(rv)

            # Momentum: roll3 − roll10
            if add_momentum:
                roll3  = roll_vals[0]
                roll10 = roll_vals[windows.index(10)] if 10 in windows else roll_vals[2]
                features.append(roll3 - roll10)

            # Context features
            if extra_features:
                is_home = float(games[i].get("is_home", 0))
                opp_nr  = float(games[i].get("opp_net_rtg") or 0.0)
                features.append(is_home)
                if opp_continuous:
                    features.append(opp_nr)
                else:
                    # Legacy bucket for Modelo B backward-compat
                    if opp_nr >= q67:
                        features.append(1.0)
                    elif opp_nr <= q33:
                        features.append(-1.0)
                    else:
                        features.append(0.0)

            # Cross-stat driver roll3 features
            if cross_stat_features:
                for cs in CROSS_STAT_FEATURES.get(stat, []):
                    cs_vals = [g.get(cs) for g in games]
                    cs_win  = [v for v in cs_vals[max(0, i - 3): i] if v is not None]
                    features.append(float(np.mean(cs_win)) if cs_win else 0.0)

            X_rows.append(features)
            y_vals.append(float(y_val))

    if not X_rows:
        return np.empty((0, 0)), np.empty(0), 0

    return np.array(X_rows), np.array(y_vals), len(by_team)


def _fit_ridge_with_bootstrap(
    X: np.ndarray,
    y: np.ndarray,
    sample_weight: Optional[np.ndarray] = None,
) -> Optional[Dict[str, Any]]:
    """Fit a RidgeCV model and compute Bootstrap CIs.

    Args:
        X:             Feature matrix.
        y:             Target vector.
        sample_weight: Optional per-sample weights (e.g. from
                       ``_compute_sample_weights``). When provided, weights
                       are applied to both RidgeCV fitting and bootstrap
                       resampling via stratified resampling probability.

    Returns a serialisable dict or None if not enough samples.
    """
    from sklearn.linear_model import Ridge, RidgeCV
    from sklearn.preprocessing import StandardScaler

    if len(y) < 20:
        return None

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Normalise weights so they sum to n (Ridge expects unbounded non-neg weights)
    sw = None
    if sample_weight is not None:
        sw = sample_weight / sample_weight.sum() * len(y)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ridge = RidgeCV(alphas=[0.01, 0.1, 1.0, 10.0, 100.0], cv=5)
        ridge.fit(X_scaled, y, sample_weight=sw)

    coef = ridge.coef_.tolist()
    intercept = float(ridge.intercept_)
    alpha = float(ridge.alpha_)

    # Bootstrap: sample with probability proportional to weights
    boot_probs = sw / sw.sum() if sw is not None else None
    rng = np.random.default_rng(42)
    boot_coefs: List[List[float]] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        idx = rng.choice(len(y), size=len(y), replace=True, p=boot_probs)
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
    rmse_train = round(float(np.sqrt(ss_res / len(y))), 4)

    return {
        "coef":          coef,
        "intercept":     intercept,
        "alpha":         alpha,
        "r2_train":      r2,
        "rmse_train":    rmse_train,
        "n_samples":     len(y),
        "ci_low":        ci_low,
        "ci_high":       ci_high,
        "scaler_mean":   scaler.mean_.tolist(),
        "scaler_scale":  scaler.scale_.tolist(),
    }


def _opp_bucket(opp_nr: float, q33: float, q67: float) -> float:
    """Categorise opponent strength into {-1, 0, 1} bucket."""
    if opp_nr >= q67:
        return 1.0
    if opp_nr <= q33:
        return -1.0
    return 0.0


def _compute_league_thresholds(records: List[Dict[str, Any]]) -> tuple:
    """Return (q33, q67) of net_rtg across all records."""
    vals = [r.get("net_rtg") for r in records if r.get("net_rtg") is not None]
    if not vals:
        return -2.0, 2.0
    return float(np.percentile(vals, 33)), float(np.percentile(vals, 67))


def _vectorized_ridge_predict(
    model_doc: Dict[str, Any],
    feat_mat: np.ndarray,
) -> np.ndarray:
    """Apply a stored Ridge model to a feature matrix (n_samples, n_features).

    Returns estimates array of shape (n_samples,).
    """
    mean      = np.array(model_doc["scaler_mean"])
    scale     = np.array(model_doc["scaler_scale"])
    coef      = np.array(model_doc["coef"])
    intercept = float(model_doc["intercept"])
    X_scaled  = (feat_mat - mean) / scale
    return X_scaled @ coef + intercept


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
