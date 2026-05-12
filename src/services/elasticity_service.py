"""Elasticity service — Modelo A (global) and Modelo B (conditional).

Fitting helpers live in _elasticity_models.py.
This module provides ElasticityRepository (DB layer) and ElasticityService (orchestration).
"""

from __future__ import annotations

from datetime import datetime
from time import monotonic
from typing import Any, Dict, List, Optional

import numpy as np

from database.historical_repository import HistoricalRepository
from services.live_history_adapter import LiveHistoryAdapter
from services._elasticity_models import (
    TARGET_STATS, ROLLING_WINDOWS, BOOTSTRAP_ITERATIONS, CI_LOW, CI_HIGH,
    _build_dataset, _fit_ridge_with_bootstrap, _predict_with_ci,
)

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

