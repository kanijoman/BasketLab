"""Repository for the HISTORICAL collection — cross-season analytics."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo.errors import PyMongoError

COLLECTION_NAME = "HISTORICAL"


class HistoricalRepository:
    """Read/write access to the HISTORICAL collection.

    One document per team-per-match, pre-computed with derived stats and
    differentials so predictive model queries are pure ``$match`` + ``$group``
    without runtime computation.
    """

    def __init__(self, connection):
        self._conn = connection

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _col(self):
        return self._conn.get_collection(COLLECTION_NAME)

    def _ensure_indexes(self) -> None:
        """Create indexes the first time data is written (idempotent)."""
        col = self._col()
        col.create_index(
            [("league", 1), ("competition", 1), ("season", 1)],
            background=True,
            name="idx_league_competition_season",
        )
        col.create_index(
            [("team_id", 1), ("season", 1)],
            background=True,
            name="idx_team_season",
        )
        col.create_index(
            [("match_id", 1), ("team_id", 1)],
            unique=True,
            background=True,
            name="idx_match_team_unique",
        )
        col.create_index("date", background=True, name="idx_date")

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def upsert_match_team(self, doc: Dict[str, Any]) -> bool:
        """Insert or replace a team-per-match document.

        Uses ``(match_id, team_id)`` as the natural key so re-ingesting a
        season is idempotent — existing documents are updated, not duplicated.

        Args:
            doc: Fully-formed document including derived stats.

        Returns:
            True on success, False on connection or DB error.
        """
        if not self._conn.is_connected():
            return False
        try:
            self._ensure_indexes()
            col = self._col()
            col.update_one(
                {"match_id": doc["match_id"], "team_id": doc["team_id"]},
                {"$set": doc},
                upsert=True,
            )
            return True
        except PyMongoError:
            return False

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_seasons_for_elasticity(
        self,
        leagues: Optional[List[str]] = None,
        competitions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Return all team-per-match documents for the requested scope.

        Args:
            leagues:      Filter by league ("FEB", "FBCYL"). None = all.
            competitions: Filter by competition label ("LF2", etc.). None = all.

        Returns:
            List of documents (dicts) ready for use as a ML dataset.
        """
        if not self._conn.is_connected():
            return []
        try:
            filt: Dict[str, Any] = {}
            if leagues:
                filt["league"] = {"$in": leagues}
            if competitions:
                filt["competition"] = {"$in": competitions}
            return list(self._col().find(filt, {"_id": 0}))
        except PyMongoError:
            return []

    def get_team_profile(
        self, team_id: str, season: str
    ) -> Optional[Dict[str, Any]]:
        """Aggregate season-level identity stats for a team.

        Returns a single dict with means of style variables used for Modelo B
        (3PA rate, pace, STL%) computed from all matches in that season.

        Args:
            team_id: Team identifier string.
            season:  Normalised season label ("2024-25").

        Returns:
            Aggregated profile dict or None if no data found.
        """
        if not self._conn.is_connected():
            return None
        try:
            pipeline = [
                {"$match": {"team_id": team_id, "season": season}},
                {
                    "$group": {
                        "_id": None,
                        "n": {"$sum": 1},
                        "avg_ortg": {"$avg": "$ortg"},
                        "avg_drtg": {"$avg": "$drtg"},
                        "avg_pace": {"$avg": "$pace"},
                        "avg_efg_pct": {"$avg": "$efg_pct"},
                        "avg_tov_rate": {"$avg": "$tov_rate"},
                        "avg_oreb_pct": {"$avg": "$oreb_pct"},
                        "avg_ftr": {"$avg": "$ftr"},
                        "avg_fg3a_rate": {"$avg": "$fg3a_rate"},
                    }
                },
            ]
            results = list(self._col().aggregate(pipeline))
            if not results:
                return None
            profile = results[0]
            # Guard: mongomock may return a result with all-None values when empty
            if profile.get("n", 0) == 0:
                return None
            profile = results[0]
            profile.pop("_id", None)
            profile["team_id"] = team_id
            profile["season"] = season
            return profile
        except PyMongoError:
            return None

    def get_team_history(
        self, team_id: str, season: str
    ) -> List[Dict[str, Any]]:
        """Return all match documents for a team in a season, sorted by date.

        Args:
            team_id: Team identifier string.
            season:  Normalised season label ("2024-25").

        Returns:
            List of HISTORICAL documents, sorted chronologically.
        """
        if not self._conn.is_connected():
            return []
        try:
            docs = list(self._col().find(
                {"team_id": team_id, "season": season},
                {"_id": 0},
            ))
            docs.sort(key=lambda d: d.get("date") or datetime.min)
            return docs
        except PyMongoError:
            return []

    def list_seasons(self) -> List[str]:
        """Return distinct season labels in HISTORICAL, sorted descending."""
        if not self._conn.is_connected():
            return []
        try:
            seasons = self._col().distinct("season")
            return sorted(seasons, reverse=True)
        except PyMongoError:
            return []

    def list_teams(self, season: Optional[str] = None) -> List[Dict[str, str]]:
        """Return distinct (team_id, team_name) pairs from HISTORICAL.

        Args:
            season: Optional filter; when provided, only teams with at least
                    one match in that season are returned.

        Returns:
            List of ``{team_id, team_name}`` dicts, sorted by team_name.
        """
        if not self._conn.is_connected():
            return []
        try:
            filt: Dict[str, Any] = {}
            if season:
                filt["season"] = season
            pipeline = [
                {"$match": filt},
                {"$group": {"_id": "$team_id", "team_name": {"$first": "$team_name"}}},
                {"$project": {"_id": 0, "team_id": "$_id", "team_name": 1}},
                {"$sort": {"team_name": 1}},
            ]
            return list(self._col().aggregate(pipeline))
        except PyMongoError:
            return []

    def get_summary(self) -> List[Dict[str, Any]]:
        """Return counts grouped by league / competition / season / group.

        Used by the Admin UI to show what is already in HISTORICAL without
        depending on the per-season collection names.

        Returns:
            List of ``{league, competition, season, group, match_count}`` dicts.
        """
        if not self._conn.is_connected():
            return []
        try:
            pipeline = [
                {
                    "$group": {
                        "_id": {
                            "league": "$league",
                            "competition": "$competition",
                            "season": "$season",
                            "group": "$group",
                        },
                        # Each match produces 2 documents (home + away), so divide.
                        "team_match_docs": {"$sum": 1},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "league": "$_id.league",
                        "competition": "$_id.competition",
                        "season": "$_id.season",
                        "group": "$_id.group",
                        "match_count": {"$divide": ["$team_match_docs", 2]},
                    }
                },
                {"$sort": {"league": 1, "competition": 1, "season": -1}},
            ]
            return list(self._col().aggregate(pipeline))
        except PyMongoError:
            return []
