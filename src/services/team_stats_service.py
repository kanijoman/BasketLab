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
from cachetools import TTLCache

if TYPE_CHECKING:
    from database import MongoDBHandler

from src.database.team_stats_aggregator import TeamStatsAggregator
from src.ui.team_utils import get_available_teams_from_collection
from utils.collection_utils import is_fbcyl as _is_fbcyl

# Cache possession stats per collection for 1 hour — play-by-play analysis is expensive
_possession_cache: TTLCache = TTLCache(maxsize=32, ttl=3600)


def _add_derived_indexes(own_map: dict) -> None:
    """Compute per-team derived dispersion indexes and append them in-place.

    ``own_map`` is the ``{team_name: {stat_key: {mean, std, cv, n}}}`` dict
    returned by ``_build_cv_map``.  Two indexes are added per team:

    * **volatilidad_triple** — ``std(3PT%) × mean(fg3_attempts_per_game)``.
      Measures how volatile the 3PT-shooting contribution is, weighted by volume.

    * **sostenibilidad_efg** — ``mean(eFG%) − league_mean_eFG``.
      Positive values indicate a team shoots above the league average (regression-
      to-mean risk); negative means below average.
    """
    # League mean eFG across all teams that have enough data
    efg_means = [
        v["efg_percentage"]["mean"]
        for v in own_map.values()
        if "efg_percentage" in v
    ]
    league_efg = float(np.mean(efg_means)) if efg_means else None

    for team, stats in own_map.items():
        # Volatilidad triple
        fg3_pct = stats.get("fg3_percentage", {})
        fg3_vol = stats.get("fg3_attempts_per_game", {})
        if fg3_pct.get("std") is not None and fg3_vol.get("mean") is not None:
            stats["volatilidad_triple"] = {
                "value": round(fg3_pct["std"] * fg3_vol["mean"], 2),
                "n":     min(fg3_pct.get("n", 0), fg3_vol.get("n", 0)),
            }
        # Sostenibilidad eFG
        efg = stats.get("efg_percentage", {})
        if efg.get("mean") is not None and league_efg is not None:
            stats["sostenibilidad_efg"] = {
                "value": round(efg["mean"] - league_efg, 2),
                "n":     efg.get("n", 0),
            }


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
        # FEB pipelines use _id as the team identifier (group key); normalise so
        # every row always carries an explicit team_id field for the frontend.
        for row in team_stats or []:
            if not row.get("team_id"):
                row["team_id"] = row.get("_id")
        for row in opponent_stats or []:
            if not row.get("team_id"):
                row["team_id"] = row.get("_id")
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
            return self._get_consistency_fbcyl(collection_name)

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
            "fg3_attempts_per_game":       "fg3_attempts",
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

        own_map   = _build_cv_map(OWN_FIELD_MAP)
        rival_map = _build_cv_map(RIVAL_FIELD_MAP)
        _add_derived_indexes(own_map)
        return {
            "own":   own_map,
            "rival": rival_map,
        }

    def _get_consistency_fbcyl(self, collection_name: str) -> Dict[str, Any]:
        """FBCYL-specific consistency computation (one per-game raw pipeline +
        Python enrichment, then the same CV accumulation as FEB)."""
        from src.database.aggregation.fbcyl_per_game_pipeline import (
            build_fbcyl_team_per_game_pipeline, enrich_fbcyl_team_row,
        )
        from collections import defaultdict

        try:
            collection = self._db.connection.get_collection(collection_name)
            pipeline   = build_fbcyl_team_per_game_pipeline()
            raw_rows   = list(collection.aggregate(pipeline))
        except Exception:
            return {}

        if not raw_rows:
            return {}

        rows = [enrich_fbcyl_team_row(r) for r in raw_rows]

        # Supported subset (excludes FEB-only rate stats that need opp pipeline data)
        FBCYL_OWN_FIELD_MAP = {
            "points_per_game":             "points",
            "points_against_per_game":     "opponent_points",
            "fg3_percentage":              "fg3_pct_game",
            "fg2_percentage":              "fg2_pct_game",
            "ft_percentage":               "ft_pct_game",
            "fg3_attempts_per_game":       "fg3_attempts",
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
        FBCYL_RIVAL_FIELD_MAP = {
            "points_per_game":             "opp_points",
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

        def _build_cv_map_from_rows(field_map):
            by_team = defaultdict(lambda: defaultdict(list))
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
            result = {}
            for team, stats in by_team.items():
                result[team] = {}
                for stat_key, values in stats.items():
                    if len(values) < 3:
                        continue
                    arr  = np.array(values)
                    mean = float(np.mean(arr))
                    std  = float(np.std(arr))
                    cv   = (std / mean * 100) if mean > 0 else 0.0
                    result[team][stat_key] = {
                        "mean": round(mean, 2),
                        "std":  round(std, 2),
                        "cv":   round(cv, 1),
                        "n":    len(values),
                    }
            return result

        own_map   = _build_cv_map_from_rows(FBCYL_OWN_FIELD_MAP)
        rival_map = _build_cv_map_from_rows(FBCYL_RIVAL_FIELD_MAP)
        _add_derived_indexes(own_map)
        return {"own": own_map, "rival": rival_map}

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
        """Return per-team possession efficiency stats enriched with play-by-play
        per-category breakdown (fast/medium/slow possessions, OER per category,
        estimated possessions per 40 min).

        Results are cached per collection for 1 hour (TTLCache) because the
        play-by-play analysis is expensive on first call.

        Args:
            collection_name: MongoDB collection name.

        Returns:
            List of dicts with ``team_name``, ``pace``, ``oer``, ``der``,
            ``net_rating``, ``possessions_per_game``, plus play-by-play fields
            ``avg_duration``, ``pct_fast``, ``pct_medium``, ``pct_slow``,
            ``oer_fast``, ``oer_medium``, ``oer_slow``,
            ``est_possessions_per_game`` (all ``None`` when unavailable).
        """
        cached = _possession_cache.get(collection_name)
        if cached is not None:
            return cached

        raw = self._db.get_team_stats(collection_name) or []

        # Build team_name -> team_id map once for all teams
        teams_info = get_available_teams_from_collection(self._db, collection_name)
        name_to_id = {t["name"]: t["id"] for t in teams_info}

        result = []
        for t in raw:
            team_name = t.get("team_name", "")
            team_id = name_to_id.get(team_name)

            entry: Dict[str, Any] = {
                "team_name":            team_name,
                "team_id":              str(team_id) if team_id else None,
                "possessions_per_game": round(float(t.get("possessions_per_game") or 0), 2),
                "pace":                 round(float(t.get("possessions_per_game") or 0), 2),
                "oer":                  round(float(t.get("offensive_rating") or 0), 2),
                "der":                  round(float(t.get("defensive_rating") or 0), 2),
                "net_rating":           round(float(t.get("net_rating") or 0), 2),
                "total_games":          int(t.get("total_games") or 0),
                # Play-by-play derived fields — None when no PBP data available
                "avg_duration":           None,
                "pct_fast":               None,
                "pct_medium":             None,
                "pct_slow":               None,
                "oer_fast":               None,
                "oer_medium":             None,
                "oer_slow":               None,
                "est_possessions_per_game": None,
            }

            if team_id:
                poss = self._db.repository.get_team_possession_stats(
                    collection_name, team_id
                )
                total = poss.get("total_possessions", 0) if poss else 0
                if total > 0:
                    avg_dur = poss["avg_duration"]
                    by_dur  = poss.get("possessions_by_duration", {})
                    fast    = by_dur.get("<=8s",  {})
                    medium  = by_dur.get("8-16s", {})
                    slow    = by_dur.get(">16s",  {})

                    def _pct(count: int) -> Optional[float]:
                        return round(count / total * 100, 1) if total > 0 else None

                    entry["avg_duration"]             = avg_dur
                    entry["pct_fast"]                 = _pct(fast.get("count", 0))
                    entry["pct_medium"]               = _pct(medium.get("count", 0))
                    entry["pct_slow"]                 = _pct(slow.get("count", 0))
                    entry["oer_fast"]                 = fast.get("oer")
                    entry["oer_medium"]               = medium.get("oer")
                    entry["oer_slow"]                 = slow.get("oer")
                    entry["est_possessions_per_game"] = (
                        round(2400 / avg_dur / 2, 1) if avg_dur and avg_dur > 0 else None
                    )

            result.append(entry)

        _possession_cache[collection_name] = result
        return result
