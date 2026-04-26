"""Player Prediction Service — FASE 8: per-player Ridge regression.

Predicts a player's next-game counting stats (pts, reb, ast, val) using
rolling-window features from their game history in a live collection.

Features per target stat (6 total):
  - roll3 of stat      (recent form, short window)
  - roll5 of stat      (medium-term form)
  - roll3 of minutes   (playing time trend short)
  - roll5 of minutes   (playing time trend medium)
  - is_home            (home advantage context)
  - opp_bucket         (opponent strength: -1 / 0 / +1)

The model uses RidgeCV for small datasets and falls back to a plain Ridge
when fewer than 20 labelled samples are available (same pattern as
backtesting_service).  Bootstrap CI (B=200) is computed for every target.

FEB / FBCYL dual-format:
  - FEB pipeline fields: pts, rt (total reb), assist, val, minutes
  - FBCYL fields:        PTS, REB, AST, VAL, MIN (float minutes)
  Both are normalised to a common schema via ``normalise_player_record()``.
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional, Tuple

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


# ---------------------------------------------------------------------------
# Public helpers (importable for unit tests)
# ---------------------------------------------------------------------------

def normalise_player_record(
    record: Dict[str, Any], is_fbcyl: bool
) -> Dict[str, Any]:
    """Map FEB or FBCYL per-game record to a common schema.

    Common keys produced:
        player_id, player_name, team_name, date, is_home,
        pts, reb, ast, val, minutes, opp_net_rtg

    Args:
        record:    Raw per-game document.
        is_fbcyl:  True for FBCYL format, False for FEB.

    Returns:
        Normalised dict with unified field names.
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
    The `stat` is the target stat name in the normalised record schema.
    """
    history = records[:idx]
    if len(history) < _MAX_WIN:
        return None

    stat_vals = [r.get(stat, 0.0) for r in history]
    min_vals  = [r.get("minutes", 0.0) for r in history]

    roll3_s  = _rolling_avg(stat_vals, 3)
    roll5_s  = _rolling_avg(stat_vals, 5)
    roll3_m  = _rolling_avg(min_vals,  3)
    roll5_m  = _rolling_avg(min_vals,  5)
    home     = 1.0 if is_home else 0.0
    bucket   = _opp_bucket(opp_net_rtg, [r.get("opp_net_rtg", 0.0) for r in history])

    return [roll3_s, roll5_s, roll3_m, roll5_m, home, bucket]


# ---------------------------------------------------------------------------
# Fitting helpers
# ---------------------------------------------------------------------------

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

    # Bootstrap CI
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


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

class PlayerPredictionService:
    """Predict a player's next-game stats using Ridge regression."""

    def __init__(self, connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict(
        self,
        collection: str,
        player_id: str,
        is_home: bool,
        opp_net_rtg: float = 0.0,
        is_fbcyl: bool = False,
    ) -> Dict[str, Any]:
        """Predict next-game stats for a player.

        Args:
            collection:  Live MongoDB collection name.
            player_id:   Player identifier (FEB integer string or FBCYL UUID).
            is_home:     Whether the next game is at home.
            opp_net_rtg: Opponent's season net_rtg (for context bucketing).
            is_fbcyl:    True if collection is FBCYL format.

        Returns:
            ``{stat: {estimate, ci_low, ci_high, n_train}}``
            or ``{"error": str}`` on failure.
        """
        records = self._load_player_games(collection, player_id, is_fbcyl)
        if not records:
            return {"error": f"No se encontraron partidos para el jugador {player_id}"}

        records = [r for r in records if r.get("minutes", 0) > 0]
        records = sorted(records, key=lambda r: r.get("date") or "")

        if len(records) < _MAX_WIN + 1:
            return {
                "error": (
                    f"Datos insuficientes: se necesitan al menos "
                    f"{_MAX_WIN + 1} partidos con minutos jugados, hay {len(records)}"
                )
            }

        result: Dict[str, Any] = {}
        for stat in TARGET_STATS:
            X, y = self._build_dataset(records, stat)
            if len(y) < MIN_TRAIN:
                result[stat] = {
                    "estimate": None, "ci_low": None, "ci_high": None, "n_train": len(y)
                }
                continue

            model = _fit_ridge(X, y)
            if model is None:
                result[stat] = {
                    "estimate": None, "ci_low": None, "ci_high": None, "n_train": len(y)
                }
                continue

            feat = build_player_features(
                records, len(records), stat, is_home, opp_net_rtg
            )
            if feat is None:
                result[stat] = {
                    "estimate": None, "ci_low": None, "ci_high": None, "n_train": len(y)
                }
                continue

            pred = _predict(model, feat)
            pred["n_train"] = model["n_samples"]
            result[stat] = pred

        return result

    # ------------------------------------------------------------------
    # Internal helpers (patchable in tests)
    # ------------------------------------------------------------------

    def _load_player_games(
        self, collection: str, player_id: str, is_fbcyl: bool = False
    ) -> List[Dict[str, Any]]:
        """Fetch per-game records for a player from the live collection."""
        if not self._conn.is_connected():
            return []
        try:
            from database.aggregation.pipeline_player_per_game import (
                PlayerPerGamePipelineMixin,
            )
            col = self._conn.get_collection(collection)
            pipeline = PlayerPerGamePipelineMixin.build_per_player_per_game_pipeline()
            pipeline.insert(0, {"$match": {"BOXSCORE.TEAM.PLAYER.id": player_id}})
            raw = list(col.aggregate(pipeline))
            return [normalise_player_record(r, is_fbcyl) for r in raw]
        except Exception:
            return []

    def _build_dataset(
        self, records: List[Dict[str, Any]], stat: str
    ) -> Tuple[np.ndarray, np.ndarray]:
        X_rows: List[List[float]] = []
        y_vals: List[float] = []

        for i in range(_MAX_WIN, len(records)):
            y = records[i].get(stat)
            if y is None or not np.isfinite(float(y)):
                continue
            feat = build_player_features(
                records, i,
                stat=stat,
                is_home=bool(records[i].get("is_home", False)),
                opp_net_rtg=float(records[i].get("opp_net_rtg", 0.0)),
            )
            if feat is None:
                continue
            X_rows.append(feat)
            y_vals.append(float(y))

        if not X_rows:
            return np.empty((0, len(FEATURE_NAMES))), np.empty(0)

        return np.array(X_rows, dtype=float), np.array(y_vals, dtype=float)
