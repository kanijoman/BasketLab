"""Team statistics service.

Encapsulates the orchestration logic for loading and enriching team statistics
from the database.  Decouples this logic from the PyQt6 UI so it can be reused
by FastAPI endpoints and tested without a display server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Any

if TYPE_CHECKING:
    from database import MongoDBHandler

from src.database.team_stats_aggregator import TeamStatsAggregator


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
        aggregator = TeamStatsAggregator(self._db.connection, collection_name)
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
