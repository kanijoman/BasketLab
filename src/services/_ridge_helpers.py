"""Ridge helper functions and constants shared by player prediction services.

Extracted from player_prediction_service.py (FASE 8).
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional

import numpy as np

# Rolling windows to use (shorter than team model — players have fewer games)
PLAYER_ROLLING_WINDOWS = [3, 5]
_MAX_WIN = max(PLAYER_ROLLING_WINDOWS)       # 5
MIN_TRAIN = 7                                # minimum labelled samples to fit
BOOTSTRAP_B = 200
CI_LOW, CI_HIGH = 5, 95                      # 90 % CI

TARGET_STATS = ["pts", "reb", "ast", "val"]

# Feature names (must match build_player_features order)
FEATURE_NAMES = [
    "roll3_stat", "roll5_stat",
    "roll3_min",  "roll5_min",
    "is_home",    "opp_bucket",
]


def normalise_player_record(
    record: Dict[str, Any], is_fbcyl: bool
) -> Dict[str, Any]:
    """Map FEB or FBCYL per-game record to a common schema.

    Common keys: player_id, player_name, team_name, date, is_home,
                 pts, reb, ast, val, minutes, opp_net_rtg
    """
    if is_fbcyl:
        return {
            "player_id":   record.get("uuid") or record.get("player_id", ""),
            "player_name": record.get("name")  or record.get("player_name", ""),
            "team_name":   record.get("team")  or record.get("team_name", ""),
            "date":        record.get("date"),
            "is_home":     record.get("is_home", False),
            "pts":         float(record.get("PTS") or record.get("pts", 0)),
            "reb":         float(record.get("REB") or record.get("reb", 0)),
            "ast":         float(record.get("AST") or record.get("ast", 0)),
            "val":         float(record.get("VAL") or record.get("val", 0)),
            "minutes":     float(record.get("MIN") or record.get("minutes", 0)),
            "opp_net_rtg": float(record.get("opp_net_rtg", 0.0)),
        }
    # FEB: rt = total rebounds, assist = assists
    return {
        "player_id":   record.get("player_id", ""),
        "player_name": record.get("player_name", ""),
        "team_name":   record.get("team_name", ""),
        "date":        record.get("date"),
        "is_home":     record.get("is_home", False),
        "pts":         float(record.get("pts", 0)),
        "reb":         float(record.get("rt") or record.get("reb", 0)),
        "ast":         float(record.get("assist") or record.get("ast", 0)),
        "val":         float(record.get("val", 0)),
        "minutes":     float(record.get("minutes", 0)),
        "opp_net_rtg": float(record.get("opp_net_rtg", 0.0)),
    }


def _rolling_avg(values: List[float], window: int) -> float:
    tail = [v for v in values[-window:] if v is not None and np.isfinite(v)]
    return float(np.mean(tail)) if tail else 0.0


def _opp_bucket(opp_net_rtg: float, history_net_rtgs: List[float]) -> float:
    if not history_net_rtgs:
        return 0.0
    arr = np.array(history_net_rtgs, dtype=float)
    q33 = float(np.percentile(arr, 33))
    q67 = float(np.percentile(arr, 67))
    if opp_net_rtg >= q67:
        return 1.0
    if opp_net_rtg <= q33:
        return -1.0
    return 0.0


def build_player_features(
    records: List[Dict[str, Any]],
    idx: int,
    stat: str,
    is_home: bool,
    opp_net_rtg: float,
) -> Optional[List[float]]:
    """Build a 6-element feature vector for game at position `idx`.

    Uses records[:idx] as history. Returns None if insufficient history.
    """
    history = records[:idx]
    if len(history) < _MAX_WIN:
        return None

    stat_vals = [r.get(stat, 0.0) for r in history]
    min_vals  = [r.get("minutes", 0.0) for r in history]

    roll3_s = _rolling_avg(stat_vals, 3)
    roll5_s = _rolling_avg(stat_vals, 5)
    roll3_m = _rolling_avg(min_vals,  3)
    roll5_m = _rolling_avg(min_vals,  5)
    home    = 1.0 if is_home else 0.0
    bucket  = _opp_bucket(opp_net_rtg, [r.get("opp_net_rtg", 0.0) for r in history])

    return [roll3_s, roll5_s, roll3_m, roll5_m, home, bucket]


def _fit_ridge(X: np.ndarray, y: np.ndarray) -> Optional[Dict[str, Any]]:
    """Fit Ridge (with bootstrap when n >= 20, plain otherwise)."""
    from sklearn.linear_model import Ridge, RidgeCV
    from sklearn.preprocessing import StandardScaler

    if len(y) < 3:
        return None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)
        scale = np.where(scaler.scale_ == 0, 1.0, scaler.scale_)

        if len(y) >= 20:
            ridge = RidgeCV(alphas=[0.01, 0.1, 1.0, 10.0], cv=5)
        else:
            ridge = Ridge(alpha=1.0)
        ridge.fit(Xs, y)

    coef = ridge.coef_.tolist()
    intercept = float(ridge.intercept_)

    rng = np.random.default_rng(42)
    boot: List[List[float]] = []
    for _ in range(BOOTSTRAP_B):
        idx = rng.integers(0, len(y), len(y))
        Xb, yb = Xs[idx], y[idx]
        if len(set(yb)) < 2:
            continue
        try:
            m = Ridge(alpha=float(getattr(ridge, "alpha_", 1.0)))
            m.fit(Xb, yb)
            boot.append(m.coef_.tolist())
        except Exception:
            pass

    ci_low = ci_high = None
    if boot:
        arr = np.array(boot)
        ci_low  = np.percentile(arr, CI_LOW,  axis=0).tolist()
        ci_high = np.percentile(arr, CI_HIGH, axis=0).tolist()

    return {
        "coef":         coef,
        "intercept":    intercept,
        "n_samples":    len(y),
        "ci_low":       ci_low,
        "ci_high":      ci_high,
        "scaler_mean":  scaler.mean_.tolist(),
        "scaler_scale": scale.tolist(),
    }


def _predict(model: Dict[str, Any], feat: List[float]) -> Dict[str, float]:
    """Apply stored Ridge model to a feature vector."""
    x = np.array(feat, dtype=float)
    mean  = np.array(model["scaler_mean"])
    scale = np.array(model["scaler_scale"])
    xs    = (x - mean) / scale

    coef      = np.array(model["coef"])
    intercept = model["intercept"]
    estimate  = float(np.dot(coef, xs) + intercept)

    ci_low_c  = model.get("ci_low")
    ci_high_c = model.get("ci_high")
    if ci_low_c and ci_high_c:
        low  = float(np.dot(np.array(ci_low_c),  xs) + intercept)
        high = float(np.dot(np.array(ci_high_c), xs) + intercept)
    else:
        low = high = estimate

    return {
        "estimate": round(estimate, 2),
        "ci_low":   round(min(low, high), 2),
        "ci_high":  round(max(low, high), 2),
    }
