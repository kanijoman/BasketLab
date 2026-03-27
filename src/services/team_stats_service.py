"""Team statistics service.

Encapsulates the orchestration logic for loading and enriching team statistics
from the database.  Decouples this logic from the PyQt6 UI so it can be reused
by FastAPI endpoints and tested without a display server.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Optional, Any

import numpy as np

if TYPE_CHECKING:
    from database import MongoDBHandler

from src.database.team_stats_aggregator import TeamStatsAggregator
from utils.collection_utils import is_fbcyl as _is_fbcyl


class TeamStatsService:
    """High-level service for team statistics.

    Responsibilities
    ----------------
    - Load raw team and opponent stats from the database (with optional filters).
    - Compute league-wide quartiles.
    - Expose team lists and detailed per-team aggregations.

    This class is intentionally free of PyQt6 imports so it can be used in
    headless contexts (unit tests, FastAPI).

    Example
    -------
    ::

        from database import MongoDBHandler
        from services import TeamStatsService

        handler = MongoDBHandler()
        svc = TeamStatsService(handler)
        result = svc.load_season_data("FEB_LF2_2025_A")
        team_stats = result["team_stats"]
        opponent_stats = result["opponent_stats"]
    """

    def __init__(self, db_handler: "MongoDBHandler") -> None:
        self._db = db_handler

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_season_data(
        self,
        collection_name: str,
        date_filter: Optional[Dict] = None,
        venue_filter: Optional[bool] = None,
        result_filter: Optional[str] = None,
    ) -> Dict[str, List[Dict]]:
        """Load team and opponent stats for a collection.

        Args:
            collection_name: MongoDB collection, e.g. ``"FEB_LF2_2025_A"``.
            date_filter: Optional MongoDB date range dict, e.g.
                ``{"$gte": datetime(2025, 1, 1)}``.
            venue_filter: ``True`` = home only, ``False`` = away only,
                ``None`` = all venues.
            result_filter: ``"won"``, ``"lost"``, or ``None`` for all results.

        Returns:
            Dict with two keys:

            - ``"team_stats"`` — list of per-team aggregated stat dicts.
            - ``"opponent_stats"`` — list of per-team opponent stat dicts.

            Either list may be empty if the collection has no data.
        """
        team_stats = self._db.get_team_stats(
            collection_name, date_filter, venue_filter, result_filter
        )
        opponent_stats = self._db.get_opponent_stats(
            collection_name, date_filter, venue_filter, result_filter
        )
        return {"team_stats": team_stats or [], "opponent_stats": opponent_stats or []}

    def get_quartiles(self, collection_name: str) -> Dict[str, Dict[str, float]]:
        """Compute league-wide quartile thresholds for all tracked statistics.

        Uses ``TeamStatsAggregator`` so the calculation is consistent with the
        rest of the codebase.

        Args:
            collection_name: MongoDB collection name.

        Returns:
            Dict mapping stat field names to ``{"min", "q1", "q2", "q3", "max",
            "count"}`` dicts.  Returns an empty dict on failure.
        """
        aggregator = TeamStatsAggregator(self._db, collection_name)
        try:
            return aggregator.calculate_league_quartiles()
        except Exception:
            return {}

    def get_all_teams(self, collection_name: str) -> List[str]:
        """Return a sorted list of unique team names in the collection.

        Args:
            collection_name: MongoDB collection name.

        Returns:
            Sorted list of team name strings (may be empty).
        """
        return self._db.get_all_teams(collection_name) or []

    def get_consistency(self, collection_name: str) -> Dict[str, Dict[str, Any]]:
        """Compute intra-team per-game variability (std dev + CV) for key stats.

        For each team, queries raw per-game counting stats via a MongoDB
        aggregation and then computes, **in Python**, the standard deviation
        (σ) and coefficient of variation (CV = σ/μ × 100) across all games in
        the collection.

        This captures how *consistent* a team is game-to-game — e.g. a team
        with an average %T3 of 30 % but CV of 40 % is very volatile, while one
        with CV of 12 % is predictable.

        Only available for FEB collections (FBCYL uses a different document
        schema).  Returns an empty dict for FBCYL or on error.

        Args:
            collection_name: MongoDB collection name.

        Returns:
            ``{team_name: {stat_key: {"mean": float, "std": float, "cv": float,
            "n": int}}}``
            where *stat_key* mirrors the keys used in the team-stats table
            (``points_per_game``, ``fg3_percentage``, …).
        """
        if _is_fbcyl(collection_name):
            return {}

        from src.database.aggregation.pipeline_builder import AggregationPipelineBuilder

        try:
            collection = self._db.connection.get_collection(collection_name)
            pipeline = AggregationPipelineBuilder.build_per_game_raw_pipeline()
            rows = list(collection.aggregate(pipeline))
        except Exception:
            return {}

        if not rows:
            return {}

        def _build_cv_map(field_map: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
            """Helper: accumulate per-game values and compute CV for a given field map."""
            by_team: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
            for row in rows:
                team = row.get("team_name")
                if not team:
                    continue
                for stat_key, raw_field in field_map.items():
                    val = row.get(raw_field)
                    if val is not None:
                        try:
                            by_team[team][stat_key].append(float(val))
                        except (TypeError, ValueError):
                            pass
            cv_result: Dict[str, Dict[str, Any]] = {}
            for team, stats in by_team.items():
                cv_result[team] = {}
                for stat_key, values in stats.items():
                    if len(values) < 3:
                        continue
                    arr = np.array(values)
                    mean = float(np.mean(arr))
                    std = float(np.std(arr))
                    cv = (std / mean * 100) if mean > 0 else 0.0
                    cv_result[team][stat_key] = {
                        "mean": round(mean, 2),
                        "std":  round(std, 2),
                        "cv":   round(cv, 1),
                        "n":    len(values),
                    }
            return cv_result

        # stat_key → raw field in the per-game document (own team stats)
        OWN_FIELD_MAP = {
            "points_per_game":             "points",
            "points_against_per_game":     "opponent_points",
            "fg3_percentage":              "fg3_pct_game",
            "fg2_percentage":              "fg2_pct_game",
            "ft_percentage":               "ft_pct_game",
            "rebounds_per_game":           "total_rebounds",
            "offensive_rebounds_per_game": "off_rebounds",
            "defensive_rebounds_per_game": "def_rebounds",
            "assists_per_game":            "assists",
            "steals_per_game":             "steals",
            "turnovers_per_game":          "turnovers",
            "blocks_per_game":             "blocks",
            "possessions_per_game":        "possessions",
            "offensive_rating":            "oer_game",
            "oer":                         "oer_game",
            "defensive_rating":            "der_game",
            "der":                         "der_game",
            "net_rating":                  "net_game",
            "efg_percentage":              "efg_pct_game",
            "true_shooting":               "ts_pct_game",
            "turnover_rate":               "tov_pct_game",
            "three_point_rate":            "three_point_rate_game",
            "free_throw_rate":             "free_throw_rate_game",
            "assist_fg_rate":              "assist_fg_rate_game",
            "assist_rate":                 "assist_rate_game",
            "steal_rate":                  "steal_rate_game",
            "block_rate":                  "block_rate_game",
            "offensive_rebound_rate":      "oreb_rate_game",
            "defensive_rebound_rate":      "dreb_rate_game",
        }

        # stat_key → opponent raw field (rival columns use the same frontend keys)
        RIVAL_FIELD_MAP = {
            "points_per_game":             "opponent_points",
            "points_against_per_game":     "points",
            "fg3_percentage":              "opp_fg3_pct_game",
            "fg2_percentage":              "opp_fg2_pct_game",
            "ft_percentage":               "opp_ft_pct_game",
            "rebounds_per_game":           "opp_total_rebounds",
            "offensive_rebounds_per_game": "opp_off_rebounds",
            "defensive_rebounds_per_game": "opp_def_rebounds",
            "assists_per_game":            "opp_assists",
            "steals_per_game":             "opp_steals",
            "turnovers_per_game":          "opp_turnovers",
            "blocks_per_game":             "opp_blocks",
            "possessions_per_game":        "opp_possessions",
            "offensive_rating":            "opp_oer_game",
            "defensive_rating":            "opp_der_game",
            "net_rating":                  "opp_net_game",
            "efg_percentage":              "opp_efg_pct_game",
            "true_shooting":               "opp_ts_pct_game",
            "turnover_rate":               "opp_tov_pct_game",
            "three_point_rate":            "opp_three_point_rate_game",
            "free_throw_rate":             "opp_free_throw_rate_game",
            "assist_fg_rate":              "opp_assist_fg_rate_game",
            "assist_rate":                 "opp_assist_rate_game",
            "steal_rate":                  "opp_steal_rate_game",
            "block_rate":                  "opp_block_rate_game",
            "offensive_rebound_rate":      "opp_orb_rate_game",
            "defensive_rebound_rate":      "opp_drb_rate_game",
        }

        return {
            "own":   _build_cv_map(OWN_FIELD_MAP),
            "rival": _build_cv_map(RIVAL_FIELD_MAP),
        }

    def get_team_detailed_stats(
        self, collection_name: str, team_name: str
    ) -> Dict[str, Any]:
        """Return aggregated stats for a single team across all games.

        Args:
            collection_name: MongoDB collection name.
            team_name: Exact team name as stored in the DB.

        Returns:
            Dictionary of aggregated stats, or empty dict if not found.
        """
        return self._db.get_aggregated_team_stats(collection_name, team_name) or {}

    def get_opponent_detailed_stats(
        self, collection_name: str, team_name: str
    ) -> Dict[str, Any]:
        """Return aggregated opponent stats for a single team.

        Args:
            collection_name: MongoDB collection name.
            team_name: Exact team name.

        Returns:
            Dictionary of aggregated opponent stats, or empty dict.
        """
        return self._db.get_aggregated_opponent_stats(collection_name, team_name) or {}

    def get_league_stats(self, collection_name: str) -> Dict[str, Any]:
        """Return league-wide aggregate statistics.

        Args:
            collection_name: MongoDB collection name.

        Returns:
            Dict of league averages, totals, etc.
        """
        return self._db.get_league_stats(collection_name) or {}

    # ------------------------------------------------------------------
    # Evolution (per-game time series) — delegated to EvolutionService
    # ------------------------------------------------------------------

    def get_team_evolution(
        self,
        collection_name: str,
        team_name: str,
        stat: str = "points",
        rolling_window: int = 5,
    ) -> List[Dict[str, Any]]:
        """Delegate to EvolutionService.get_team_evolution.

        Kept here for backward compatibility with callers that hold a reference
        to ``TeamStatsService``.
        """
        from src.services.evolution_service import EvolutionService
        return EvolutionService(self._db).get_team_evolution(
            collection_name, team_name, stat=stat, rolling_window=rolling_window
        )

    # ------------------------------------------------------------------
    # Possession league-wide stats for scatter analysis
    # ------------------------------------------------------------------

    def get_possession_stats(self, collection_name: str) -> List[Dict[str, Any]]:
        """Return per-team possession efficiency stats (OER, DER, Pace).

        Derives all values from the existing team stats aggregation — no extra
        DB query needed.  OER and DER are the ``offensive_rating`` and
        ``defensive_rating`` already computed by the pipeline; Pace is
        ``possessions_per_game``.

        Args:
            collection_name: MongoDB collection name.

        Returns:
            List of dicts with ``team_name``, ``pace``, ``oer``, ``der``,
            ``net_rating``, ``possessions_per_game``.
        """
        raw = self._db.get_team_stats(collection_name) or []
        result = []
        for t in raw:
            result.append({
                "team_name":           t.get("team_name", ""),
                "possessions_per_game": round(float(t.get("possessions_per_game") or 0), 2),
                "pace":                round(float(t.get("possessions_per_game") or 0), 2),
                "oer":                 round(float(t.get("offensive_rating") or 0), 2),
                "der":                 round(float(t.get("defensive_rating") or 0), 2),
                "net_rating":          round(float(t.get("net_rating") or 0), 2),
                "total_games":         int(t.get("total_games") or 0),
            })
        return result
