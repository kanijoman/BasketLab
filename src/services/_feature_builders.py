"""Feature vector builders for elasticity model inference and MC simulation.

Shared by ElasticityService (scalar prediction) and MonteCarloService
(vectorized simulation), ensuring training and inference use identical
feature engineering.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from services._elasticity_models import (
    ROLLING_WINDOWS,
    ROLLING_WINDOWS_C,
    CROSS_STAT_FEATURES,
    _opp_bucket,
)


def _build_features_for_inference(
    model_doc: Dict[str, Any],
    vals_by_stat: Dict[str, List[float]],
    target_stat: str,
    is_home: Optional[bool] = None,
    opp_net_rtg: Optional[float] = None,
) -> List[float]:
    """Build a feature vector for scalar (single-game) inference.

    Reads ``model_doc["feature_flags"]`` to reconstruct the same feature
    engineering used during training.  Falls back to model_type-based
    heuristics for legacy models without ``feature_flags``.

    Args:
        model_doc:    Stored model document (from ELASTICITIES collection).
        vals_by_stat: Recent game values per stat, e.g.
                      ``{"net_rtg": [4.2, 3.1, ...], ...}``.
        target_stat:  The stat being predicted (key in vals_by_stat).
        is_home:      True/False for context models; None → default 0.5.
        opp_net_rtg:  Opponent net rating; None → 0.0.
    """
    flags   = model_doc.get("feature_flags") or {}
    windows = model_doc.get("windows") or (
        ROLLING_WINDOWS_C if flags.get("extended_windows") else ROLLING_WINDOWS
    )

    target_vals = vals_by_stat.get(target_stat, [])
    features: List[float] = []
    roll_vals: List[float] = []

    # Rolling features for target stat
    for w in windows:
        window = target_vals[-w:] if len(target_vals) >= w else target_vals
        rv = float(np.mean(window)) if window else 0.0
        features.append(rv)
        roll_vals.append(rv)

    # Momentum: roll3 − roll10
    if flags.get("momentum"):
        roll3  = roll_vals[0]
        roll10_idx = next((i for i, w in enumerate(windows) if w == 10), 2)
        roll10 = roll_vals[roll10_idx] if roll10_idx < len(roll_vals) else 0.0
        features.append(roll3 - roll10)

    # Context features (is_home + opp)
    _has_context = flags.get("context") or model_doc.get("model_type") in ("B", "C", "D")
    if _has_context:
        features.append(float(is_home) if is_home is not None else 0.5)
        opp_val = float(opp_net_rtg) if opp_net_rtg is not None else 0.0
        if flags.get("opp_continuous"):
            features.append(opp_val)
        else:
            # Legacy bucket (Modelo B backward-compat)
            opp_q33 = float(model_doc.get("opp_q33", -2.0))
            opp_q67 = float(model_doc.get("opp_q67",  2.0))
            features.append(_opp_bucket(opp_val, opp_q33, opp_q67))

    # Cross-stat driver roll3 features
    if flags.get("cross_stats"):
        for cs in CROSS_STAT_FEATURES.get(target_stat, []):
            cs_vals = vals_by_stat.get(cs, [])
            cs_win  = cs_vals[-3:] if len(cs_vals) >= 3 else cs_vals
            features.append(float(np.mean(cs_win)) if cs_win else 0.0)

    return features


def _build_feat_matrix_for_mc(
    model_doc: Dict[str, Any],
    sim_paths: Dict[str, np.ndarray],
    target_stat: str,
    is_home_flag: float,
    opp_nr: float,
) -> np.ndarray:
    """Build feature matrix (n_simulations, n_features) for vectorized MC inference.

    Uses the same feature_flags as ``_build_features_for_inference`` but
    operates on the full matrix of simulation paths simultaneously.

    Args:
        model_doc:    Stored model document.
        sim_paths:    Dict mapping stat → array of shape (n_sims, n_history).
        target_stat:  Stat being predicted.
        is_home_flag: 1.0 = home, 0.0 = away for this future game.
        opp_nr:       Opponent net_rtg for this future game.
    """
    flags   = model_doc.get("feature_flags") or {}
    windows = model_doc.get("windows") or (
        ROLLING_WINDOWS_C if flags.get("extended_windows") else ROLLING_WINDOWS
    )

    paths = sim_paths.get(target_stat)
    if paths is None:
        raise KeyError(f"stat '{target_stat}' not found in sim_paths")

    n_sims = paths.shape[0]
    feat_parts: List[np.ndarray] = []
    roll_cols: List[np.ndarray] = []

    # Rolling features for target stat
    for w in windows:
        window = paths[:, -w:] if paths.shape[1] >= w else paths
        rv = np.mean(window, axis=1)
        feat_parts.append(rv.reshape(-1, 1))
        roll_cols.append(rv)

    # Momentum: roll3 − roll10
    if flags.get("momentum"):
        roll3  = roll_cols[0]
        roll10_idx = next((i for i, w in enumerate(windows) if w == 10), 2)
        roll10 = roll_cols[roll10_idx] if roll10_idx < len(roll_cols) else np.zeros(n_sims)
        feat_parts.append((roll3 - roll10).reshape(-1, 1))

    # Context features
    _has_context = flags.get("context") or model_doc.get("model_type") in ("B", "C", "D")
    if _has_context:
        feat_parts.append(np.full((n_sims, 1), is_home_flag))
        if flags.get("opp_continuous"):
            feat_parts.append(np.full((n_sims, 1), opp_nr))
        else:
            # Legacy bucket
            opp_q33 = float(model_doc.get("opp_q33", -2.0))
            opp_q67 = float(model_doc.get("opp_q67",  2.0))
            bucket  = _opp_bucket(opp_nr, opp_q33, opp_q67)
            feat_parts.append(np.full((n_sims, 1), bucket))

    # Cross-stat driver roll3 features
    if flags.get("cross_stats"):
        for cs in CROSS_STAT_FEATURES.get(target_stat, []):
            if cs in sim_paths:
                cs_paths = sim_paths[cs]
                cs_win   = cs_paths[:, -3:] if cs_paths.shape[1] >= 3 else cs_paths
                cs_roll3 = np.mean(cs_win, axis=1)
            else:
                cs_roll3 = np.zeros(n_sims)
            feat_parts.append(cs_roll3.reshape(-1, 1))

    return np.hstack(feat_parts)  # (n_sims, total_features)
