"""Elasticity service — Modelo A (global) and Modelo B (conditional).

Fitting helpers live in _elasticity_models.py.
This module provides ElasticityRepository (DB layer) and ElasticityService (orchestration).
"""

from __future__ import annotations

from datetime import datetime
from time import monotonic
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from database.historical_repository import HistoricalRepository
from services.live_history_adapter import LiveHistoryAdapter
from services._elasticity_models import (
    TARGET_STATS, ROLLING_WINDOWS, ROLLING_WINDOWS_C,
    BOOTSTRAP_ITERATIONS, CI_LOW, CI_HIGH,
    _build_dataset, _fit_ridge_with_bootstrap, _predict_with_ci,
    _compute_league_thresholds, _compute_sample_weights, CROSS_STAT_FEATURES,
)
from services._feature_builders import _build_features_for_inference
from services._gbm_models import _fit_gbm_with_quantiles, _predict_gbm

ELASTICITIES_COLLECTION = "ELASTICITIES"


# ---------------------------------------------------------------------------
# Repository for ELASTICITIES collection
# ---------------------------------------------------------------------------

class ElasticityRepository:
    """Store and retrieve fitted elasticity models from MongoDB."""

    _LIST_MODELS_TTL = 60.0  # seconds

    def __init__(self, connection) -> None:
        self._conn = connection
        self._list_models_cache: Optional[List[Dict[str, Any]]] = None
        self._list_models_ts: float = 0.0

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
        now = monotonic()
        if self._list_models_cache is not None and (now - self._list_models_ts) < self._LIST_MODELS_TTL:
            return self._list_models_cache
        if not self._conn.is_connected():
            return []
        try:
            result = list(self._col().find({}, {"_id": 0}))
            self._list_models_cache = result
            self._list_models_ts = now
            return result
        except Exception:
            return []

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
        progress_cb: Optional[Callable[[str], None]] = None,
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
        opp_q33, opp_q67 = _compute_league_thresholds(records)

        total_steps = len(TARGET_STATS) * 4  # A + B + C + D per stat
        step = 0

        # Model configs: (type, extra, momentum, extended_windows, cross_stat, opp_continuous)
        _RIDGE_CONFIGS = [
            ("A", False, False, False, False, False),
            ("B", True,  False, False, False, False),
            ("C", True,  True,  True,  True,  True),
        ]

        for stat in TARGET_STATS:
            stat_summary: Dict[str, Any] = {}
            n_teams_last = 0

            # ── Ridge models A, B, C ─────────────────────────────────────
            # sample_weight is intentionally NOT used for Ridge: _build_dataset
            # iterates by_team in dict order (not global temporal order), so
            # exponential-decay weights would favour the last team in the dict
            # rather than the most recent games, degrading generalisation.
            for mtype, extra, momentum, extended, cross, opp_cont in _RIDGE_CONFIGS:
                step += 1
                if progress_cb:
                    progress_cb(f"Modelo {mtype} — {stat} ({step}/{total_steps})")
                X, y, n_teams = _build_dataset(
                    records, stat,
                    extra_features=extra,
                    add_momentum=momentum,
                    extended_windows=extended,
                    cross_stat_features=cross,
                    opp_continuous=opp_cont,
                )
                if len(y) < 20:
                    continue
                n_teams_last = n_teams
                model = _fit_ridge_with_bootstrap(X, y)
                if not model:
                    continue
                windows = ROLLING_WINDOWS_C if extended else ROLLING_WINDOWS
                n_cross = len(CROSS_STAT_FEATURES.get(stat, [])) if cross else 0
                model.update({
                    "model_type":    mtype,
                    "stat":          stat,
                    "league":        league_tag,
                    "competition":   comp_tag,
                    "n_teams":       n_teams,
                    "trained_at":    trained_at,
                    "windows":       windows,
                    "feature_flags": {
                        "momentum":         momentum,
                        "cross_stats":      cross,
                        "context":          extra,
                        "opp_continuous":   opp_cont,
                        "extended_windows": extended,
                    },
                    "features": (
                        [f"roll_{w}" for w in windows]
                        + (["momentum"] if momentum else [])
                        + (["is_home", "opp_net_rtg" if opp_cont else "opp_bucket"] if extra else [])
                        + ([f"roll3_{cs}" for cs in CROSS_STAT_FEATURES.get(stat, [])] if cross else [])
                    ),
                    **(({"opp_q33": opp_q33, "opp_q67": opp_q67}) if extra else {}),
                })
                self._repo.upsert_model(model)
                stat_summary[f"model_{mtype.lower()}"] = {
                    "r2": model["r2_train"], "n": model["n_samples"]
                }

            # ── Modelo D: GBM with same features as C ────────────────────
            step += 1
            if progress_cb:
                progress_cb(f"Modelo D — {stat} ({step}/{total_steps})")
            X_d, y_d, _ = _build_dataset(
                records, stat,
                extra_features=True, add_momentum=True, extended_windows=True,
                cross_stat_features=True, opp_continuous=True,
            )
            if len(y_d) >= 20:
                # GBM can use sample_weight safely because it is tree-based
                # and not affected by the cross-team ordering issue.
                sw_d    = _compute_sample_weights(len(y_d))
                model_d = _fit_gbm_with_quantiles(X_d, y_d, sample_weight=sw_d)
                if model_d:
                    n_cross = len(CROSS_STAT_FEATURES.get(stat, []))
                    windows_d = ROLLING_WINDOWS_C
                    model_d.update({
                        "model_type":    "D",
                        "stat":          stat,
                        "league":        league_tag,
                        "competition":   comp_tag,
                        "n_teams":       n_teams_last,
                        "trained_at":    trained_at,
                        "windows":       windows_d,
                        "feature_flags": {
                            "momentum":         True,
                            "cross_stats":      True,
                            "context":          True,
                            "opp_continuous":   True,
                            "extended_windows": True,
                        },
                        "opp_q33": opp_q33,
                        "opp_q67": opp_q67,
                    })
                    self._repo.upsert_model(model_d)
                    stat_summary["model_d"] = {
                        "r2": model_d["r2_train"], "n": model_d["n_samples"]
                    }

            summary[stat] = stat_summary

        return summary

    # ------------------------------------------------------------------
    # Inference (called by GET /elasticity/predict/{team_id})
    # ------------------------------------------------------------------

    def _predict_from_records(
        self,
        records: List[Dict[str, Any]],
        is_home: Optional[bool],
        opp_net_rtg: Optional[float],
        leagues: Optional[List[str]],
        competitions: Optional[List[str]],
    ) -> Dict[str, Any]:
        """Core prediction logic over pre-loaded, chronologically sorted records."""
        league_tag = ",".join(leagues) if leagues else "ALL"
        comp_tag   = ",".join(competitions) if competitions else "ALL"

        vals_by_stat: Dict[str, List[float]] = {
            s: [r.get(s) for r in records if r.get(s) is not None]
            for s in TARGET_STATS
        }

        result: Dict[str, Any] = {}
        for stat in TARGET_STATS:
            if not vals_by_stat.get(stat):
                continue
            stat_out: Dict[str, Any] = {}

            for mtype in ("A", "B", "C"):
                doc = self._repo.get_model(mtype, stat, league_tag, comp_tag)
                if not doc:
                    continue
                # Skip context models (B/C) when caller provides no context
                flags = doc.get("feature_flags") or {}
                needs_ctx = flags.get("context") or mtype in ("B", "C")
                if needs_ctx and (is_home is None or opp_net_rtg is None):
                    continue
                feats = _build_features_for_inference(
                    doc, vals_by_stat, stat, is_home, opp_net_rtg
                )
                stat_out[f"model_{mtype.lower()}"] = _predict_with_ci(doc, feats)

            doc_d = self._repo.get_model("D", stat, league_tag, comp_tag)
            if doc_d and "gbm_mean" in doc_d and is_home is not None and opp_net_rtg is not None:
                feats_d = _build_features_for_inference(
                    doc_d, vals_by_stat, stat, is_home, opp_net_rtg
                )
                stat_out["model_d"] = _predict_gbm(doc_d, feats_d)

            if stat_out:
                result[stat] = stat_out

        return result

    def predict_next_game(
        self,
        team_id: str,
        season: str,
        is_home: Optional[bool] = None,
        opp_net_rtg: Optional[float] = None,
        leagues: Optional[List[str]] = None,
        competitions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Predict next-game stats from HISTORICAL data."""
        records = self._hist.get_team_history(team_id, season)
        if not records:
            return {"error": f"Sin historial para equipo {team_id} en temporada {season}"}
        records.sort(key=lambda r: r.get("date") or datetime.min)
        return self._predict_from_records(records, is_home, opp_net_rtg, leagues, competitions)

    def predict_next_game_live(
        self,
        live_collection: str,
        team_name: str,
        is_fbcyl: bool = False,
        is_home: Optional[bool] = None,
        opp_net_rtg: Optional[float] = None,
        leagues: Optional[List[str]] = None,
        competitions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Predict next-game stats from a live collection (current season).

        Uses LiveHistoryAdapter to normalise live docs on-the-fly into the same
        schema as HISTORICAL — the trained model is unchanged.
        """
        adapter = LiveHistoryAdapter(self._conn)
        records = adapter.get_team_history(live_collection, team_name, is_fbcyl)
        if not records:
            return {"error": f"Sin historial para '{team_name}' en colección '{live_collection}'"}
        return self._predict_from_records(records, is_home, opp_net_rtg, leagues, competitions)

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

