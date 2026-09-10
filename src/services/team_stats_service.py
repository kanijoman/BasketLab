"""Team statistics service.

Encapsulates the orchestration logic for loading and enriching team statistics
from the database.  Decouples this logic from the PyQt6 UI so it can be reused
by FastAPI endpoints and tested without a display server.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Dict, List, Optional, Any

from cachetools import TTLCache

if TYPE_CHECKING:
    from database import MongoDBHandler

from src.database.team_stats_aggregator import TeamStatsAggregator
from src.utils.team_utils import get_available_teams_from_collection
from utils.collection_utils import is_fbcyl as _is_fbcyl
from src.services._consistency_calculator import (
    build_cv_map,
    add_derived_indexes,
    OWN_FIELD_MAP,
    RIVAL_FIELD_MAP,
    FBCYL_OWN_FIELD_MAP,
    FBCYL_RIVAL_FIELD_MAP,
)

# Backward-compat alias: tests import _add_derived_indexes directly from this module
_add_derived_indexes = add_derived_indexes

# Cache possession stats per collection for 1 hour — play-by-play analysis is expensive
_possession_cache: TTLCache = TTLCache(maxsize=32, ttl=3600)


def _rival_avg_duration_general(
    breakdown: Dict[str, Dict[str, float]],
    avg_duration_by_id: Dict[str, float],
) -> Optional[float]:
    """Weight each faced rival's own season avg_duration by possessions they played against us."""
    weighted_sum = 0.0
    total_weight = 0.0
    for opp_id, data in breakdown.items():
        opp_general = avg_duration_by_id.get(opp_id)
        if opp_general is None:
            continue
        weighted_sum += opp_general * data["possessions"]
        total_weight += data["possessions"]
    return round(weighted_sum / total_weight, 2) if total_weight > 0 else None


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

    def get_teams_with_ids(self, collection_name: str) -> List[Dict]:
        """Return deduplicated [{id, name}] dicts — sponsor-change safe.

        Args:
            collection_name: MongoDB collection name.

        Returns:
            Sorted list of ``{"id": str, "name": str}`` dicts (may be empty).
        """
        return self._db.get_teams_with_ids(collection_name) or []

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

        own_map   = build_cv_map(rows, OWN_FIELD_MAP)
        rival_map = build_cv_map(rows, RIVAL_FIELD_MAP)
        add_derived_indexes(own_map)
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

        try:
            collection = self._db.connection.get_collection(collection_name)
            pipeline   = build_fbcyl_team_per_game_pipeline()
            raw_rows   = list(collection.aggregate(pipeline))
        except Exception:
            return {}

        if not raw_rows:
            return {}

        rows = [enrich_fbcyl_team_row(r) for r in raw_rows]

        own_map   = build_cv_map(rows, FBCYL_OWN_FIELD_MAP)
        rival_map = build_cv_map(rows, FBCYL_RIVAL_FIELD_MAP)
        add_derived_indexes(own_map)
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
        poss_by_team_id: Dict[str, Dict[str, Any]] = {}
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
                poss_by_team_id[str(team_id)] = poss
                total = poss.get("total_possessions", 0) if poss else 0
                if total > 0:
                    avg_dur = poss["avg_duration"]
                    by_dur  = poss.get("possessions_by_duration", {})
                    fast    = by_dur.get("<=8s",  {})
                    medium  = by_dur.get("8-16s", {})
                    slow    = by_dur.get(">16s",  {})
                    
                    # Reconciliation metadata — general OER is untouched (already boxscore-formula from pipeline)
                    recommendation = poss.get("recommendation", "use_playbyplay")
                    phantom_pct = poss.get("phantom_pct", 0)
                    data_quality_score = poss.get("data_quality_score", 100)

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
                    
                    # Add data quality fields
                    entry["data_quality_score"]       = data_quality_score
                    entry["phantom_pct"]              = phantom_pct
                    entry["reconciliation"]           = recommendation
                    entry["boxscore_oer"]             = poss.get("boxscore_oer", 0)

                    # Rival (opponent) possession breakdown
                    entry["rival_pct_fast"]   = poss.get("rival_pct_fast")
                    entry["rival_pct_medium"] = poss.get("rival_pct_medium")
                    entry["rival_pct_slow"]   = poss.get("rival_pct_slow")
                    entry["rival_oer_fast"]   = poss.get("rival_oer_fast")
                    entry["rival_oer_medium"] = poss.get("rival_oer_medium")
                    entry["rival_oer_slow"]   = poss.get("rival_oer_slow")
                    entry["rival_avg_duration"] = poss.get("rival_avg_duration")

            result.append(entry)

        # Pace-impact: compare each team's rivals' pace against us to those same
        # rivals' own season-wide pace (weighted by possessions played against us).
        avg_duration_by_id = {
            r["team_id"]: r["avg_duration"]
            for r in result
            if r.get("team_id") and r.get("avg_duration") is not None
        }
        for entry in result:
            tid = entry.get("team_id")
            poss = poss_by_team_id.get(tid) if tid else None
            breakdown = poss.get("rival_opponent_breakdown") if poss else None
            general = _rival_avg_duration_general(breakdown, avg_duration_by_id) if breakdown else None
            entry["rival_avg_duration_general"] = general
            rival_avg = entry.get("rival_avg_duration")
            entry["rival_pace_differential"] = (
                round(rival_avg - general, 2) if general is not None and rival_avg is not None else None
            )

        _possession_cache[collection_name] = result
        return result
