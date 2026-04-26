"""Elasticity service — Modelo A (global) and Modelo B (conditional).

Uses the HISTORICAL cross-season collection to fit Ridge regression models that
capture how well current-window stats predict near-future performance.

Modelo A (global)
-----------------
For each target stat (net_rtg, efg_pct, tov_rate, oreb_pct, ortg, drtg):
  - Feature matrix X: [rolling-3, rolling-5, rolling-10] averages of the stat
    built from the chronological match history of every team.
  - Target Y: the stat value in the NEXT game.
  - Fitting: RidgeCV (cross-validated alpha) on the full dataset.
  - Bootstrap CI: B=500 resamples → 5th/95th percentile intervals.

Resultado por equipo:
  For a given team, the service reads their last N games from HISTORICAL and
  generates a point estimate + 90% CI of expected performance in the next game.

Modelo B (conditional)
-----------------------
Same as Modelo A but adds two conditioning features:
  - is_home (0/1)
  - opponent_strength_bucket (-1 weak / 0 avg / +1 strong) derived from the
    opponent's season net_rtg quartile stored in HISTORICAL.

Both models are stored in a MongoDB collection (ELASTICITIES) so they do not
need to be re-computed on every request.
"""

from __future__ import annotations

import json
import warnings
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from database.historical_repository import HistoricalRepository

# ── target stats ──────────────────────────────────────────────────────────────
TARGET_STATS = ["net_rtg", "ortg", "drtg", "efg_pct", "tov_rate", "oreb_pct"]
ROLLING_WINDOWS = [3, 5, 10]
ELASTICITIES_COLLECTION = "ELASTICITIES"
BOOTSTRAP_ITERATIONS = 500
CI_LOW, CI_HIGH = 5, 95  # 90 % CI


# ---------------------------------------------------------------------------
# Repository for ELASTICITIES collection
# ---------------------------------------------------------------------------

class ElasticityRepository:
    """Store and retrieve fitted elasticity models from MongoDB."""

    def __init__(self, connection) -> None:
        self._conn = connection

    def _col(self):
        return self._conn.get_collection(ELASTICITIES_COLLECTION)

    def upsert_model(self, doc: Dict[str, Any]) -> bool:
        if not self._conn.is_connected():
            return False
        try:
            col = self._col()
            col.create_index(
                [("model_type", 1), ("stat", 1), ("league", 1), ("competition", 1)],
                background=True, unique=True, name="idx_model_key",
            )
            col.update_one(
                {
                    "model_type": doc["model_type"],
                    "stat":       doc["stat"],
                    "league":     doc.get("league", "ALL"),
                    "competition": doc.get("competition", "ALL"),
                },
                {"$set": doc},
                upsert=True,
            )
            return True
        except Exception:
            return False

    def get_model(
        self,
        model_type: str,
        stat: str,
        league: str = "ALL",
        competition: str = "ALL",
    ) -> Optional[Dict[str, Any]]:
        if not self._conn.is_connected():
            return None
        try:
            return self._col().find_one(
                {"model_type": model_type, "stat": stat,
                 "league": league, "competition": competition},
                {"_id": 0},
            )
        except Exception:
            return None

    def list_models(self) -> List[Dict[str, Any]]:
        if not self._conn.is_connected():
            return []
        try:
            return list(self._col().find({}, {"_id": 0}))
        except Exception:
            return []


# ---------------------------------------------------------------------------
# Dataset builder
# ---------------------------------------------------------------------------

def _build_dataset(
    records: List[Dict[str, Any]],
    stat: str,
    extra_features: bool = False,
) -> Tuple[np.ndarray, np.ndarray, int]:
    """Build (X, y) arrays for Ridge fitting.

    Rows are grouped by team and sorted by date so rolling windows are
    temporally correct.  Each row i generates a sample where:
      - X[i] = [roll3, roll5, roll10] (possibly + [is_home, opp_bucket])
      - y[i] = stat value in game i (the "next game" relative to the rolling window)

    Args:
        records:       Documents from :meth:`HistoricalRepository.get_seasons_for_elasticity`.
        stat:          Key in each document (e.g. ``"net_rtg"``).
        extra_features: If True, add ``is_home`` and ``opp_strength_bucket`` (Modelo B).

    Returns:
        (X, y, n_teams) tuple.  X is shape (N, n_features), y is shape (N,).
    """
    # Group by team, sort chronologically
    by_team: Dict[str, List[Dict]] = defaultdict(list)
    for rec in records:
        tid = rec.get("team_id") or rec.get("team_name", "")
        if tid:
            by_team[tid].append(rec)
    for tid in by_team:
        by_team[tid].sort(key=lambda r: r.get("date") or datetime.min)

    # Compute league-wide net_rtg quartiles for opponent bucketing (Modelo B)
    all_net_rtg = [r.get("net_rtg") for r in records if r.get("net_rtg") is not None]
    q33 = float(np.percentile(all_net_rtg, 33)) if all_net_rtg else 0.0
    q67 = float(np.percentile(all_net_rtg, 67)) if all_net_rtg else 0.0

    X_rows: List[List[float]] = []
    y_vals: List[float] = []

    max_window = max(ROLLING_WINDOWS)

    for tid, games in by_team.items():
        vals = [g.get(stat) for g in games]
        # Skip teams with too few games
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
                    bucket = 1.0   # strong opponent
                elif opp_nr <= q33:
                    bucket = -1.0  # weak opponent
                else:
                    bucket = 0.0
                features += [is_home, bucket]
            X_rows.append(features)
            y_vals.append(float(y_val))

    if not X_rows:
        return np.empty((0, 0)), np.empty(0), 0

    return np.array(X_rows), np.array(y_vals), len(by_team)


# ---------------------------------------------------------------------------
# Fitting helpers
# ---------------------------------------------------------------------------

def _fit_ridge_with_bootstrap(
    X: np.ndarray,
    y: np.ndarray,
) -> Optional[Dict[str, Any]]:
    """Fit a RidgeCV model and compute Bootstrap CIs.

    Returns a serialisable dict with coefficients, intercept, alpha, and CI
    bounds, or None if not enough samples.
    """
    from sklearn.linear_model import RidgeCV
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

    # Bootstrap CI on coefficients
    rng = np.random.default_rng(42)
    boot_coefs: List[List[float]] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        idx = rng.integers(0, len(y), len(y))
        X_b, y_b = X_scaled[idx], y[idx]
        if len(set(y_b)) < 2:
            continue
        try:
            from sklearn.linear_model import Ridge
            m = Ridge(alpha=alpha)
            m.fit(X_b, y_b)
            boot_coefs.append(m.coef_.tolist())
        except Exception:
            pass

    ci_low = ci_high = None
    if boot_coefs:
        arr = np.array(boot_coefs)
        ci_low  = np.percentile(arr, CI_LOW, axis=0).tolist()
        ci_high = np.percentile(arr, CI_HIGH, axis=0).tolist()

    # R² on training set
    y_pred = ridge.predict(X_scaled)
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = round(1 - ss_res / ss_tot, 4) if ss_tot > 0 else 0.0

    # Store scaler params for inference
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


# ---------------------------------------------------------------------------
# Inference helper
# ---------------------------------------------------------------------------

def _predict_with_ci(
    model_doc: Dict[str, Any],
    rolling_features: List[float],
    extra_features: Optional[List[float]] = None,
) -> Dict[str, float]:
    """Apply a stored model to produce a point estimate + CI.

    Args:
        model_doc:       Stored model from ELASTICITIES collection.
        rolling_features: [roll3, roll5, roll10] values for the target stat.
        extra_features:  Optional [is_home, opp_bucket] for Modelo B.

    Returns:
        ``{"estimate": float, "ci_low": float, "ci_high": float, "r2": float}``
    """
    features = list(rolling_features)
    if extra_features:
        features += list(extra_features)

    x = np.array(features, dtype=float)
    mean = np.array(model_doc["scaler_mean"])
    scale = np.array(model_doc["scaler_scale"])
    x_scaled = (x - mean) / scale

    coef = np.array(model_doc["coef"])
    intercept = model_doc["intercept"]
    estimate = float(np.dot(coef, x_scaled) + intercept)

    # CI from Bootstrap coefficient spread
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


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

class ElasticityService:
    """Train and serve Ridge elasticity models over HISTORICAL data."""

    def __init__(self, connection) -> None:
        self._conn  = connection
        self._hist  = HistoricalRepository(connection)
        self._repo  = ElasticityRepository(connection)

    # ------------------------------------------------------------------
    # Training (called by POST /elasticity/train)
    # ------------------------------------------------------------------

    def train(
        self,
        leagues: Optional[List[str]] = None,
        competitions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Train Modelo A and Modelo B for all target stats, persist results.

        Args:
            leagues:      Filter HISTORICAL data by league.
            competitions: Filter HISTORICAL data by competition.

        Returns:
            Summary dict ``{stat: {model_a: {r2, n}, model_b: {r2, n}}}``
        """
        records = self._hist.get_seasons_for_elasticity(leagues, competitions)
        if not records:
            return {"error": "No hay datos en HISTORICAL para los filtros indicados"}

        summary: Dict[str, Any] = {}
        league_tag = ",".join(leagues) if leagues else "ALL"
        comp_tag   = ",".join(competitions) if competitions else "ALL"
        trained_at = datetime.utcnow().isoformat()

        for stat in TARGET_STATS:
            stat_summary: Dict[str, Any] = {}

            # Modelo A
            X_a, y_a, n_teams = _build_dataset(records, stat, extra_features=False)
            if len(y_a) >= 20:
                model_a = _fit_ridge_with_bootstrap(X_a, y_a)
                if model_a:
                    model_a.update({
                        "model_type":  "A",
                        "stat":        stat,
                        "league":      league_tag,
                        "competition": comp_tag,
                        "n_teams":     n_teams,
                        "trained_at":  trained_at,
                        "features":    [f"roll_{w}" for w in ROLLING_WINDOWS],
                    })
                    self._repo.upsert_model(model_a)
                    stat_summary["model_a"] = {
                        "r2": model_a["r2_train"], "n": model_a["n_samples"]
                    }

            # Modelo B
            X_b, y_b, _ = _build_dataset(records, stat, extra_features=True)
            if len(y_b) >= 20:
                model_b = _fit_ridge_with_bootstrap(X_b, y_b)
                if model_b:
                    model_b.update({
                        "model_type":  "B",
                        "stat":        stat,
                        "league":      league_tag,
                        "competition": comp_tag,
                        "n_teams":     n_teams,
                        "trained_at":  trained_at,
                        "features":    [f"roll_{w}" for w in ROLLING_WINDOWS] + ["is_home", "opp_bucket"],
                    })
                    self._repo.upsert_model(model_b)
                    stat_summary["model_b"] = {
                        "r2": model_b["r2_train"], "n": model_b["n_samples"]
                    }

            summary[stat] = stat_summary

        return summary

    # ------------------------------------------------------------------
    # Inference (called by GET /elasticity/predict/{team_id})
    # ------------------------------------------------------------------

    def predict_next_game(
        self,
        team_id: str,
        season: str,
        is_home: Optional[bool] = None,
        opp_net_rtg: Optional[float] = None,
        leagues: Optional[List[str]] = None,
        competitions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Predict next-game stats for a team using trained elasticity models.

        Args:
            team_id:     Team identifier (as stored in HISTORICAL).
            season:      Normalised season label ("2024-25").
            is_home:     Whether the next game is at home (for Modelo B).
            opp_net_rtg: Opponent's season net_rtg (for Modelo B bucketing).
            leagues:     League filter for model retrieval.
            competitions: Competition filter for model retrieval.

        Returns:
            ``{stat: {model_a: {...}, model_b: {...}}}`` or error dict.
        """
        # Fetch team's game-by-game history for this season
        records = self._hist.get_team_history(team_id, season)
        if not records:
            return {"error": f"Sin historial para equipo {team_id} en temporada {season}"}

        records.sort(key=lambda r: r.get("date") or datetime.min)

        league_tag = ",".join(leagues) if leagues else "ALL"
        comp_tag   = ",".join(competitions) if competitions else "ALL"

        result: Dict[str, Any] = {}

        for stat in TARGET_STATS:
            vals = [r.get(stat) for r in records if r.get(stat) is not None]
            if not vals:
                continue

            rolling: List[float] = []
            for w in ROLLING_WINDOWS:
                window = vals[-w:] if len(vals) >= w else vals
                rolling.append(float(np.mean(window)))

            stat_out: Dict[str, Any] = {}

            # Modelo A
            doc_a = self._repo.get_model("A", stat, league_tag, comp_tag)
            if doc_a:
                stat_out["model_a"] = _predict_with_ci(doc_a, rolling)

            # Modelo B
            doc_b = self._repo.get_model("B", stat, league_tag, comp_tag)
            if doc_b and is_home is not None and opp_net_rtg is not None:
                all_net = [r.get("net_rtg") for r in records if r.get("net_rtg") is not None]
                q33 = float(np.percentile(all_net, 33)) if all_net else 0.0
                q67 = float(np.percentile(all_net, 67)) if all_net else 0.0
                bucket = 1.0 if opp_net_rtg >= q67 else (-1.0 if opp_net_rtg <= q33 else 0.0)
                extra = [float(is_home), bucket]
                stat_out["model_b"] = _predict_with_ci(doc_b, rolling, extra)

            if stat_out:
                result[stat] = stat_out

        return result

    def list_models(self) -> List[Dict[str, Any]]:
        """Return metadata for all stored models (no coefficients)."""
        docs = self._repo.list_models()
        return [
            {
                "model_type":  d.get("model_type"),
                "stat":        d.get("stat"),
                "league":      d.get("league"),
                "competition": d.get("competition"),
                "r2_train":    d.get("r2_train"),
                "n_samples":   d.get("n_samples"),
                "n_teams":     d.get("n_teams"),
                "trained_at":  d.get("trained_at"),
                "features":    d.get("features"),
            }
            for d in docs
        ]
