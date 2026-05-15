"""Game Prediction Service — FASE 7: Win/Loss binary classifier.

Trains a Logistic Regression classifier (with Platt calibration via
CalibratedClassifierCV) on a team's historical game records from HISTORICAL.
Features are rolling-window averages of key stats plus context variables.

Model
-----
Features (11 total):
  - roll3/5/10 of net_rtg  (3 features: recent form signal)
  - roll3/5/10 of efg_pct  (3 features: shooting form)
  - roll3/5/10 of tov_rate (3 features: ball-security form)
  - is_home                (1 feature: home advantage)
  - opp_bucket             (1 feature: opponent strength -1/0/+1)

Target:
  win = 1 if net_rtg > 0, else 0

Calibration:
  CalibratedClassifierCV (cv=3, method="sigmoid") → well-calibrated P(win)

Output of predict():
  win_prob          — P(win) calibrated
  ci_low / ci_high  — bootstrap CI (B=200, 90 % interval)
  feature_importances — dict of feature_name → normalised |coef|
  n_train           — number of training samples
  accuracy          — walk-forward LOO-style accuracy (None if < MIN_EVAL)
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from database.historical_repository import HistoricalRepository
from services._elasticity_models import ROLLING_WINDOWS

# Minimum records to attempt fitting
MIN_TRAIN = 12
_MAX_WINDOW = max(ROLLING_WINDOWS)   # 10
_BOOTSTRAP_B = 200
_CI_LOW, _CI_HIGH = 5, 95   # 90 % CI
_GAME_PREDICTION_COLLECTION = "GAME_PREDICTION_MODELS"

# Rolling feature stats
_ROLLING_STATS = ["net_rtg", "efg_pct", "tov_rate"]

# Feature names in order (must match _build_feature_vector)
FEATURE_NAMES: List[str] = [
    f"roll{w}_{s}"
    for s in _ROLLING_STATS
    for w in ROLLING_WINDOWS
] + ["is_home", "opp_bucket"]


# ---------------------------------------------------------------------------
# Public helpers (importable for unit tests)
# ---------------------------------------------------------------------------

def _derive_label(net_rtg: Optional[float]) -> Optional[int]:
    """Return 1 (win) if net_rtg > 0, 0 (loss) otherwise. None if missing."""
    if net_rtg is None:
        return None
    return 1 if net_rtg > 0 else 0


def _rolling_avg(values: List[Optional[float]], window: int) -> float:
    """Mean of the last `window` non-None values, or 0.0 if none."""
    tail = [v for v in values[-window:] if v is not None]
    return float(np.mean(tail)) if tail else 0.0


def _opp_strength_bucket(opp_net_rtg: float, train_net_rtgs: List[float]) -> float:
    """Map opponent net_rtg to -1/0/+1 bucket using training-set quartiles."""
    if not train_net_rtgs:
        return 0.0
    arr = np.array(train_net_rtgs, dtype=float)
    q33 = float(np.percentile(arr, 33))
    q67 = float(np.percentile(arr, 67))
    if opp_net_rtg >= q67:
        return 1.0
    if opp_net_rtg <= q33:
        return -1.0
    return 0.0


def _build_feature_vector(
    records: List[Dict[str, Any]],
    idx: int,
    is_home: bool,
    opp_net_rtg: float,
) -> Optional[List[float]]:
    """Build a feature vector for game at position `idx` using records[:idx].

    Returns None if there are fewer than _MAX_WINDOW prior games.
    """
    history = records[:idx]
    if len(history) < _MAX_WINDOW:
        return None

    features: List[float] = []
    for stat in _ROLLING_STATS:
        vals = [r.get(stat) for r in history]
        for w in ROLLING_WINDOWS:
            features.append(_rolling_avg(vals, w))

    # Context features
    features.append(1.0 if is_home else 0.0)
    train_net_rtgs = [r.get("net_rtg") or 0.0 for r in history]
    features.append(_opp_strength_bucket(opp_net_rtg, train_net_rtgs))

    return features


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

class GamePredictionService:
    """Predict Win/Loss probability for a team's next game."""

    def __init__(self, connection) -> None:
        self._conn = connection
        self._hist = HistoricalRepository(connection)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict(
        self,
        team_id: str,
        season: str,
        is_home: bool,
        opp_net_rtg: float,
        leagues: Optional[List[str]] = None,
        competitions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Predict win probability for the team's next game.

        Args:
            team_id:     Team ID as stored in HISTORICAL.
            season:      Normalised season label ("2024-25").
            is_home:     Whether the next game is at home.
            opp_net_rtg: Opponent's season net_rtg (for strength bucket).
            leagues:     Optional filter.
            competitions: Optional filter.

        Returns:
            ``{win_prob, ci_low, ci_high, feature_importances, n_train, accuracy}``
            or ``{"error": str}`` on failure.
        """
        records = self._load_records(team_id, season, leagues, competitions)
        if not records:
            return {"error": "Sin datos en HISTORICAL para este equipo y temporada"}

        records = sorted(records, key=lambda r: r.get("date") or "")

        if len(records) < MIN_TRAIN + _MAX_WINDOW:
            return {
                "error": (
                    f"Datos insuficientes: se necesitan al menos "
                    f"{MIN_TRAIN + _MAX_WINDOW} partidos, hay {len(records)}"
                )
            }

        X, y = self._build_dataset(records)
        if len(y) < MIN_TRAIN:
            return {"error": f"Muestras insuficientes tras construir features: {len(y)}"}

        # Handle monotone class — classifier cannot learn anything
        unique_labels = set(y)
        if len(unique_labels) < 2:
            only = int(list(unique_labels)[0]) if unique_labels else 0
            return {
                "win_prob":            float(only),
                "ci_low":              float(only),
                "ci_high":             float(only),
                "feature_importances": {name: 0.0 for name in FEATURE_NAMES},
                "n_train":             len(y),
                "accuracy":            float(only),
            }

        model = self._fit(X, y)
        if model is None:
            return {"error": "No se pudo ajustar el clasificador"}

        # Build inference feature vector from ALL records
        feat_vec = _build_feature_vector(records, len(records), is_home, opp_net_rtg)
        if feat_vec is None:
            return {"error": "No hay suficiente historial para construir features de inferencia"}

        win_prob, ci_low, ci_high = self._predict_with_ci(model, feat_vec, X, y)
        importances, coefficients = self._feature_importances(model)
        accuracy = self._walk_forward_accuracy(records)

        return {
            "win_prob":              round(win_prob, 4),
            "ci_low":               round(ci_low, 4),
            "ci_high":              round(ci_high, 4),
            "feature_importances":  importances,
            "feature_coefficients": coefficients,
            "n_train":              len(y),
            "accuracy":             round(accuracy, 4) if accuracy is not None else None,
        }

    # ------------------------------------------------------------------
    # Internal helpers (patchable in tests)
    # ------------------------------------------------------------------

    def predict_live(
        self,
        live_collection: str,
        live_team_name: str,
        is_fbcyl: bool,
        is_home: bool,
        opp_net_rtg: float,
    ) -> Dict[str, Any]:
        """Predict win probability using live (current-season) collection data."""
        from services.live_history_adapter import LiveHistoryAdapter
        adapter = LiveHistoryAdapter(self._conn)
        records = adapter.get_team_history(live_collection, live_team_name, is_fbcyl)
        if not records:
            return {"error": "Sin partidos en la colección en vivo para este equipo"}

        records = sorted(records, key=lambda r: r.get("date") or "")

        if len(records) < MIN_TRAIN + _MAX_WINDOW:
            return {
                "error": (
                    f"Datos insuficientes: se necesitan al menos "
                    f"{MIN_TRAIN + _MAX_WINDOW} partidos, hay {len(records)}"
                )
            }

        X, y = self._build_dataset(records)
        if len(y) < MIN_TRAIN:
            return {"error": f"Muestras insuficientes tras construir features: {len(y)}"}

        unique_labels = set(y)
        if len(unique_labels) < 2:
            only = int(list(unique_labels)[0]) if unique_labels else 0
            return {
                "win_prob":              float(only),
                "ci_low":               float(only),
                "ci_high":              float(only),
                "feature_importances":  {name: 0.0 for name in FEATURE_NAMES},
                "feature_coefficients": {name: 0.0 for name in FEATURE_NAMES},
                "n_train":              len(y),
                "accuracy":             float(only),
            }

        model = self._fit(X, y)
        if model is None:
            return {"error": "No se pudo ajustar el clasificador"}

        feat_vec = _build_feature_vector(records, len(records), is_home, opp_net_rtg)
        if feat_vec is None:
            return {"error": "No hay suficiente historial para construir features de inferencia"}

        win_prob, ci_low, ci_high = self._predict_with_ci(model, feat_vec, X, y)
        importances, coefficients = self._feature_importances(model)
        accuracy = self._walk_forward_accuracy(records)

        return {
            "win_prob":              round(win_prob, 4),
            "ci_low":               round(ci_low, 4),
            "ci_high":              round(ci_high, 4),
            "feature_importances":  importances,
            "feature_coefficients": coefficients,
            "n_train":              len(y),
            "accuracy":             round(accuracy, 4) if accuracy is not None else None,
        }

    def _load_records(
        self,
        team_id: str,
        season: str,
        leagues: Optional[List[str]] = None,
        competitions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        if not self._conn.is_connected():
            return []
        all_records = self._hist.get_seasons_for_elasticity(leagues, competitions)
        return [
            r for r in all_records
            if r.get("team_id") == team_id and r.get("season") == season
        ]

    def _build_dataset(
        self, records: List[Dict[str, Any]]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Build (X, y) from chronological records."""
        X_rows: List[List[float]] = []
        y_vals: List[int] = []

        for i in range(_MAX_WINDOW, len(records)):
            label = _derive_label(records[i].get("net_rtg"))
            if label is None:
                continue
            feat = _build_feature_vector(
                records, i,
                is_home=bool(records[i].get("is_home", False)),
                opp_net_rtg=float(records[i].get("opp_net_rtg") or 0.0),
            )
            if feat is None:
                continue
            X_rows.append(feat)
            y_vals.append(label)

        if not X_rows:
            return np.empty((0, len(FEATURE_NAMES))), np.empty(0, dtype=int)

        return np.array(X_rows, dtype=float), np.array(y_vals, dtype=int)

    def _fit(
        self, X: np.ndarray, y: np.ndarray
    ) -> Optional[Any]:
        """Fit a calibrated Logistic Regression classifier."""
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                n_cv = min(3, len(y) // max(1, int(sum(y))))
                n_cv = max(2, n_cv)
                base = LogisticRegression(max_iter=1000, C=1.0, solver="lbfgs")
                calibrated = CalibratedClassifierCV(base, cv=n_cv, method="sigmoid")
                pipeline = Pipeline([
                    ("scaler", StandardScaler()),
                    ("clf",    calibrated),
                ])
                pipeline.fit(X, y)
                return pipeline
            except Exception:
                return None

    def _predict_with_ci(
        self,
        model: Any,
        feat_vec: List[float],
        X_train: np.ndarray,
        y_train: np.ndarray,
    ) -> Tuple[float, float, float]:
        """Return (win_prob, ci_low, ci_high) via bootstrap resampling."""
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline

        x = np.array(feat_vec, dtype=float).reshape(1, -1)
        win_prob = float(model.predict_proba(x)[0][1])

        # Bootstrap CI
        rng = np.random.default_rng(42)
        boot_probs: List[float] = []
        for _ in range(_BOOTSTRAP_B):
            idx = rng.integers(0, len(y_train), len(y_train))
            X_b, y_b = X_train[idx], y_train[idx]
            if len(set(y_b)) < 2:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    base = LogisticRegression(max_iter=500, C=1.0, solver="lbfgs")
                    cal = CalibratedClassifierCV(base, cv=2, method="sigmoid")
                    pipe = Pipeline([("scaler", StandardScaler()), ("clf", cal)])
                    pipe.fit(X_b, y_b)
                    p = float(pipe.predict_proba(x)[0][1])
                    boot_probs.append(p)
                except Exception:
                    pass

        if boot_probs:
            ci_low  = float(np.percentile(boot_probs, _CI_LOW))
            ci_high = float(np.percentile(boot_probs, _CI_HIGH))
        else:
            ci_low = ci_high = win_prob

        return (
            win_prob,
            max(0.0, min(1.0, ci_low)),
            max(0.0, min(1.0, ci_high)),
        )

    def _feature_importances(self, model: Any) -> Dict[str, float]:
        """Extract normalised absolute feature importances from the pipeline."""
        try:
            calibrated = model.named_steps["clf"]
            coef_arrays: List[Any] = []
            for cc in calibrated.calibrated_classifiers_:
                # sklearn >= 1.2: base_estimator renamed to estimator
                base = getattr(cc, "estimator", None) or getattr(cc, "base_estimator", None)
                if base is not None and hasattr(base, "coef_"):
                    coef_arrays.append(base.coef_[0])
            if not coef_arrays:
                return {name: 0.0 for name in FEATURE_NAMES}
            coefs = np.mean(coef_arrays, axis=0)
            abs_coefs = np.abs(coefs)
            total = abs_coefs.sum()
            norm = abs_coefs / total if total > 0 else np.zeros_like(abs_coefs)
            # Signed: preserves direction (positive = helps win, negative = hurts)
            signed = coefs / total if total > 0 else np.zeros_like(coefs)
            return (
                {name: round(float(v), 4) for name, v in zip(FEATURE_NAMES, norm)},
                {name: round(float(v), 4) for name, v in zip(FEATURE_NAMES, signed)},
            )
        except Exception:
            return (
                {name: 0.0 for name in FEATURE_NAMES},
                {name: 0.0 for name in FEATURE_NAMES},
            )

    def _walk_forward_accuracy(
        self, records: List[Dict[str, Any]]
    ) -> Optional[float]:
        """Walk-forward accuracy: train on [0..i-1], predict game i.

        Uses the same CalibratedClassifierCV pipeline as predict() so the
        reported accuracy reflects the deployed model, not a bare classifier.
        """
        correct = 0
        total = 0
        start = _MAX_WINDOW + MIN_TRAIN

        for i in range(start, len(records)):
            label = _derive_label(records[i].get("net_rtg"))
            if label is None:
                continue
            X_tr, y_tr = self._build_dataset(records[:i])
            if len(y_tr) < MIN_TRAIN or len(set(y_tr)) < 2:
                continue
            feat = _build_feature_vector(
                records, i,
                is_home=bool(records[i].get("is_home", False)),
                opp_net_rtg=float(records[i].get("opp_net_rtg") or 0.0),
            )
            if feat is None:
                continue
            pipe = self._fit(X_tr, y_tr)
            if pipe is None:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    pred = int(np.argmax(pipe.predict_proba(np.array(feat).reshape(1, -1))[0]))
                    correct += int(pred == label)
                    total += 1
                except Exception:
                    pass

        return round(correct / total, 4) if total > 0 else None
