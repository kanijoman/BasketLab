"""Games-fetch repository mixin.

Extracted from repository.py (FASE OOM / deuda técnica).
Provides methods that retrieve full game documents from MongoDB.
"""

from typing import Dict, Iterable, List, Optional
from pymongo.errors import PyMongoError

from utils.collection_utils import is_fbcyl as _is_fbcyl

# ---------------------------------------------------------------------------
# Field projections for play-by-play queries
# ---------------------------------------------------------------------------
# Only fetch the fields actually consumed by PlayByPlayAnalyzer and
# InOutStatsCalculator. This avoids loading large BOXSCORE totals, shot-chart
# data, etc. into memory and is the primary defence against OOM errors when
# processing a full season of games.

_FEB_PBP_PROJECTION: Dict = {
    "HEADER.TEAM": 1,           # team ID mapping (PlayByPlayAnalyzer._get_team_mapping)
    "BOXSCORE.TEAM.id": 1,      # team ID lookup
    "BOXSCORE.TEAM.PLAYER.id": 1,   # player identity
    "BOXSCORE.TEAM.PLAYER.min": 1,  # minutes played check
    "PLAYBYPLAY.LINES": 1,      # play-by-play actions (core of analysis)
}

_FBCYL_PBP_PROJECTION: Dict = {
    "stats.teams.teamIdIntern": 1,       # team ID (game-scoped)
    "stats.teams.teamIdExtern": 1,       # team ID (stable)
    "stats.teams.players.uuid": 1,       # stable player identity
    "stats.teams.players.actorId": 1,    # game-scoped player reference
    "stats.teams.players.name": 1,       # name for normalised lookup
    "stats.teams.players.timePlayed": 1, # minutes played check
    "stats.teams.players.data": 1,       # phantom-guard detection
    "moves": 1,                          # play-by-play actions
}


class GamesRepositoryMixin:
    """Mixin providing game-document retrieval methods."""

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_team_match_filter(
        team_id: str,
        is_fbcyl: bool,
        only_with_playbyplay: bool,
    ) -> Dict:
        """Build the MongoDB match filter for a specific team's games.

        Args:
            team_id: Team identifier string.
            is_fbcyl: True for FBCYL collections, False for FEB.
            only_with_playbyplay: When True, restrict to games that contain PBP data.

        Returns:
            MongoDB filter dict.
        """
        if is_fbcyl:
            int_id = int(team_id) if team_id.isdigit() else team_id
            match_filter: Dict = {
                "$or": [
                    {"stats.teams.teamIdIntern": team_id},
                    {"stats.teams.teamIdIntern": int_id},
                    {"stats.teams.teamIdExtern": team_id},
                    {"stats.teams.teamIdExtern": int_id},
                ]
            }
            if only_with_playbyplay:
                match_filter["moves"] = {"$exists": True, "$ne": None}
        else:
            match_filter = {"HEADER.TEAM.id": team_id}
            if only_with_playbyplay:
                match_filter["PLAYBYPLAY.LINES"] = {"$exists": True, "$ne": None}

        return match_filter

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_games_for_team(
        self,
        collection_name: str,
        team_id: str,
        only_with_playbyplay: bool = False,
        projection: Optional[Dict] = None,
        date_filter: Optional[Dict] = None,
    ) -> List[Dict]:
        """Return all games where *team_id* participated.

        Args:
            collection_name: MongoDB collection name.
            team_id: Team identifier.
            only_with_playbyplay: When True, only return games containing PBP data.
            projection: Optional MongoDB projection dict.  When provided, only
                the specified fields are returned — useful to cap memory usage
                when callers only need a subset of the document (e.g. possession
                analysis needs PBP lines + team header, not box-score).
            date_filter: Optional MongoDB date range dict (e.g. ``{"$gte": <ISODate>}``).
                When provided an aggregation pipeline is used to parse the stored
                date string and apply the filter inside MongoDB, avoiding Python-side
                filtering which was unreliable for FEB's DD-MM-YYYY string format.

        Returns:
            List of game documents (possibly projected).
        """
        if not self.connection.is_connected():
            return []

        try:
            collection = self.connection.get_collection(collection_name)
            self.connection.ensure_indexes(collection_name)
            is_fbcyl = _is_fbcyl(collection_name)
            match_filter = self._build_team_match_filter(team_id, is_fbcyl, only_with_playbyplay)

            if date_filter is not None:
                return self._games_for_team_with_date_filter(
                    collection, match_filter, date_filter, is_fbcyl, projection
                )

            return list(collection.find(match_filter, projection))
        except PyMongoError:
            return []

    def get_games_with_playbyplay(
        self,
        collection_name: str,
        date_filter: Dict = None,
    ) -> Iterable[Dict]:
        """Return a lazy cursor of game documents that contain play-by-play data.

        Returns a pymongo cursor (not a materialised list) so callers can
        iterate one document at a time without loading the full result set into
        memory.  Each document is projected to only the fields required by
        PlayByPlayAnalyzer and InOutStatsCalculator (see _FEB_PBP_PROJECTION /
        _FBCYL_PBP_PROJECTION).

        Args:
            collection_name: MongoDB collection name.
            date_filter: Optional MongoDB date range dict applied to the game date.

        Returns:
            Iterable of projected game documents (pymongo Cursor or CommandCursor).
        """
        if not self.connection.is_connected():
            return []

        try:
            collection = self.connection.get_collection(collection_name)
            self.connection.ensure_indexes(collection_name)
            is_fbcyl = _is_fbcyl(collection_name)

            if is_fbcyl:
                return self._games_with_playbyplay_fbcyl(collection, date_filter)
            return self._games_with_playbyplay_feb(collection, date_filter)

        except PyMongoError:
            return []

    def count_games_with_playbyplay(
        self,
        collection_name: str,
        date_filter: Dict = None,
    ) -> int:
        """Return the number of games with play-by-play data without loading docs.

        Uses count_documents() to get the total count so callers can size
        progress bars without materialising the cursor.

        Args:
            collection_name: MongoDB collection name.
            date_filter: Optional MongoDB date range dict.

        Returns:
            Integer count of matching game documents.
        """
        if not self.connection.is_connected():
            return 0

        try:
            collection = self.connection.get_collection(collection_name)
            is_fbcyl = _is_fbcyl(collection_name)
            match_filter = (
                {"moves": {"$exists": True, "$ne": None}}
                if is_fbcyl
                else {"PLAYBYPLAY.LINES": {"$exists": True, "$ne": None}}
            )
            return collection.count_documents(match_filter)
        except PyMongoError:
            return 0

    def get_last_match(self, collection_name: str, team_name: str) -> Dict:
        """Return the most recent game document for *team_name*.

        Args:
            collection_name: MongoDB collection name.
            team_name: Team name string (FEB or FBCYL).

        Returns:
            Most recent game document, or empty dict when not found.
        """
        if not self.connection.is_connected():
            return {}

        try:
            collection = self.connection.get_collection(collection_name)
            is_fbcyl = _is_fbcyl(collection_name)
            pipeline = (
                self._last_match_pipeline_fbcyl(team_name)
                if is_fbcyl
                else self._last_match_pipeline_feb(team_name)
            )
            result = list(collection.aggregate(pipeline))
            return result[0] if result else {}
        except PyMongoError:
            return {}

    # ------------------------------------------------------------------
    # Internal implementation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _games_with_playbyplay_feb(collection, date_filter: Optional[Dict]) -> Iterable[Dict]:
        if date_filter:
            pipeline = [
                {
                    "$addFields": {
                        "parsedDate": {
                            "$dateFromString": {
                                "dateString": "$HEADER.starttime",
                                "format": "%d-%m-%Y - %H:%M",
                                "onError": None,
                                "onNull": None,
                            }
                        }
                    }
                },
                {
                    "$match": {
                        "parsedDate": date_filter,
                        "PLAYBYPLAY.LINES": {"$exists": True, "$ne": None},
                    }
                },
                {"$project": _FEB_PBP_PROJECTION},
            ]
            return collection.aggregate(pipeline)
        return collection.find(
            {"PLAYBYPLAY.LINES": {"$exists": True, "$ne": None}},
            _FEB_PBP_PROJECTION,
        )

    @staticmethod
    def _games_with_playbyplay_fbcyl(collection, date_filter: Optional[Dict]) -> Iterable[Dict]:
        if date_filter:
            pipeline = [
                {
                    "$addFields": {
                        "parsedDate": {
                            "$dateFromString": {
                                "dateString": "$stats.time",
                                "format": "%b %d, %Y %I:%M:%S %p",
                                "onError": None,
                                "onNull": None,
                            }
                        }
                    }
                },
                {
                    "$match": {
                        "parsedDate": date_filter,
                        "moves": {"$exists": True, "$ne": None},
                    }
                },
                {"$project": _FBCYL_PBP_PROJECTION},
            ]
            return collection.aggregate(pipeline)
        return collection.find(
            {"moves": {"$exists": True, "$ne": None}},
            _FBCYL_PBP_PROJECTION,
        )

    @staticmethod
    def _last_match_pipeline_feb(team_name: str) -> List[Dict]:
        return [
            {
                "$addFields": {
                    "parsedDate": {
                        "$dateFromString": {
                            "dateString": "$HEADER.starttime",
                            "format": "%d-%m-%Y - %H:%M",
                            "onError": None,
                            "onNull": None,
                        }
                    }
                }
            },
            {"$match": {"HEADER.TEAM.name": team_name}},
            {"$sort": {"parsedDate": -1}},
            {"$limit": 1},
        ]

    @staticmethod
    def _last_match_pipeline_fbcyl(team_name: str) -> List[Dict]:
        return [
            {
                "$addFields": {
                    "parsedDate": {
                        "$dateFromString": {
                            "dateString": "$stats.startDate",
                            "format": "%Y-%m-%dT%H:%M:%S.%LZ",
                            "onError": None,
                            "onNull": None,
                        }
                    }
                }
            },
            {"$match": {"stats.teams.name": team_name}},
            {"$sort": {"parsedDate": -1}},
            {"$limit": 1},
        ]

    @staticmethod
    def _games_for_team_with_date_filter(
        collection,
        team_match_filter: Dict,
        date_filter: Dict,
        is_fbcyl: bool,
        projection: Optional[Dict],
    ) -> List[Dict]:
        """Use an aggregation pipeline to filter a team's games by date in MongoDB.

        FEB dates are stored as DD-MM-YYYY strings which cannot be compared
        lexicographically with ISO dates.  This helper parses them inside
        MongoDB using ``$dateFromString`` so that the comparison is always
        correct.
        """
        if is_fbcyl:
            date_field = "$stats.time"
            date_format = "%b %d, %Y %I:%M:%S %p"
        else:
            date_field = "$HEADER.starttime"
            date_format = "%d-%m-%Y - %H:%M"

        pipeline: List[Dict] = [
            {"$match": team_match_filter},
            {
                "$addFields": {
                    "_parsedDate": {
                        "$dateFromString": {
                            "dateString": date_field,
                            "format": date_format,
                            "onError": None,
                            "onNull": None,
                        }
                    }
                }
            },
            {"$match": {"_parsedDate": date_filter}},
        ]
        if projection:
            pipeline.append({"$project": projection})

        return list(collection.aggregate(pipeline))
