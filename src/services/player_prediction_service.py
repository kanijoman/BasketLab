"""Player Prediction Service - FASE 8: per-player Ridge regression.

Predicts a player's next-game counting stats (pts, reb, ast, val).
Pure-computation helpers live in _ridge_helpers.py.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np

from services._ridge_helpers import (
    FEATURE_NAMES, MIN_TRAIN, TARGET_STATS, _MAX_WIN,
    _fit_ridge, _predict, build_player_features, normalise_player_record,
)

# Re-export constants so existing imports keep working
PLAYER_ROLLING_WINDOWS = [3, 5]
BOOTSTRAP_B = 200
CI_LOW, CI_HIGH = 5, 95

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

