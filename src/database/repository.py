"""Repository for basketball data operations."""

from typing import Dict, List, Optional, FrozenSet
from pymongo.errors import PyMongoError

from .connection import MongoDBConnection
from .aggregation import AggregationPipelineBuilder
from .aggregation.fbcyl_pipeline import FBCYLPipelineBuilder

from utils.collection_utils import is_fbcyl as _is_fbcyl

from .repository_inout import InOutRepositoryMixin
from .repository_possession import PossessionRepositoryMixin
from .repository_lineup import LineupRepositoryMixin


class BasketballRepository(InOutRepositoryMixin, PossessionRepositoryMixin, LineupRepositoryMixin):
    """Repository for basketball data CRUD operations."""

    def __init__(self, connection: MongoDBConnection):
        """
        Initialize repository with a MongoDB connection.

        Args:
            connection: MongoDBConnection instance
        """
        self.connection = connection

    def document_exists(self, collection_name: str, match_code) -> bool:
        """
        Check if a document with the given match_code exists in the collection.

        Args:
            collection_name: Name of the collection
            match_code: Match identifier (int for FEB, str UUID for FBCYL)

        Returns:
            True if document exists, False otherwise
        """
        if not self.connection.is_connected():
            return False

        try:
            collection = self.connection.get_collection(collection_name)
            # Convert to int if it's a numeric string, otherwise use as-is (UUID)
            doc_id = int(match_code) if isinstance(match_code, str) and match_code.isdigit() else match_code
            return collection.find_one({"_id": doc_id}) is not None
        except PyMongoError as e:
            return False

    def insert_boxscore(self, collection_name: str, match_code: str, boxscore: Dict) -> bool:
        """
        Insert a boxscore document if it doesn't already exist in the collection.

        Args:
            collection_name: Name of the collection
            match_code: Match identifier
            boxscore: Boxscore data dictionary

        Returns:
            True if successful, False otherwise
        """
        if not self.connection.is_connected():
            return False

        # Check if document already exists
        if self.document_exists(collection_name, int(match_code)):
            # Document exists, silently skip it
            return True

        try:
            collection = self.connection.get_collection(collection_name)
            boxscore["_id"] = int(match_code)
            collection.insert_one(boxscore)
            return True
        except PyMongoError as e:
            return False

    def insert_fbcyl_match(self, collection_name: str, match_uuid: str, match_data: Dict) -> bool:
        """
        Insert a FBCYL match document with complete data (moves + stats).

        Args:
            collection_name: Name of the collection
            match_uuid: Match UUID (24-character hex string)
            match_data: Dictionary with 'uuid', 'moves', and 'stats' keys

        Returns:
            True if successful, False otherwise
        """
        if not self.connection.is_connected():
            return False

        # Check if document already exists
        if self.document_exists(collection_name, match_uuid):
            return True

        try:
            collection = self.connection.get_collection(collection_name)
            # Use UUID as the document _id
            match_data["_id"] = match_uuid
            collection.insert_one(match_data)
            return True
        except PyMongoError as e:
            return False

    def get_team_stats(self, collection_name: str, date_filter: Dict = None, venue_filter: bool = None, result_filter: str = None) -> List[Dict]:
        """
        Get aggregated team statistics from all matches in the collection.

        Returns a list of dictionaries containing each team's season statistics including:
        - Total games played (home and away)
        - Total points scored and received
        - Field goal statistics (2PT, 3PT, FT)
        - Rebounds, assists, steals, etc.
        - Advanced metrics (Four Factors, efficiency ratings, etc.)

        Args:
            collection_name: Name of the collection
            date_filter: Optional MongoDB date filter (e.g., {"$gte": datetime(2024, 1, 1)})
            venue_filter: Optional boolean to filter by venue (True=home, False=away, None=all)
            result_filter: Optional string to filter by result ('won', 'lost', None=all)

        Returns:
            List of team statistics dictionaries
        """
        if not self.connection.is_connected():
            return []

        try:
            collection = self.connection.get_collection(collection_name)

            # Detect if this is a FBCYL collection by checking collection name or document structure
            is_fbcyl = _is_fbcyl(collection_name)

            if is_fbcyl:
                pipeline = FBCYLPipelineBuilder.build_team_stats_pipeline(date_filter, venue_filter, result_filter)
            else:
                pipeline = AggregationPipelineBuilder.build_team_stats_pipeline(date_filter, venue_filter, result_filter)

            result = list(collection.aggregate(pipeline))

            if not result and is_fbcyl:
                # Debug: Check if collection has data
                doc_count = collection.count_documents({})
                print(f"[Repository] FBCYL collection {collection_name} has {doc_count} documents")
                if doc_count > 0:
                    sample = collection.find_one()
                    print(f"[Repository] Sample document keys: {list(sample.keys()) if sample else 'None'}")
                    if sample and 'stats' in sample:
                        print(f"[Repository] Sample stats keys: {list(sample['stats'].keys())}")
                        if 'teams' in sample['stats']:
                            print(f"[Repository] Number of teams in sample: {len(sample['stats']['teams'])}")
                            if sample['stats']['teams']:
                                print(f"[Repository] First team keys: {list(sample['stats']['teams'][0].keys())}")

                    # Try a simple aggregation to see what's happening
                    print(f"[Repository] Testing simple aggregation...")
                    simple_result = list(collection.aggregate([
                        {"$limit": 1},
                        {"$project": {"teams": "$stats.teams"}}
                    ]))
                    print(f"[Repository] Simple aggregation result: {len(simple_result)} docs")

            return result
        except PyMongoError as e:
            print(f"[Repository] Error in get_team_stats: {e}")
            import traceback
            traceback.print_exc()
            return []
        except Exception as e:
            print(f"[Repository] Unexpected error in get_team_stats: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_opponent_stats(self, collection_name: str, date_filter: Dict = None, venue_filter: bool = None, result_filter: str = None) -> List[Dict]:
        """
        Get aggregated opponent statistics grouped by team.

        This shows what each team's opponents have done against them across all matches.
        Useful for defensive analysis and understanding the strength of opposition faced.

        Args:
            collection_name: Name of the collection
            date_filter: Optional MongoDB date filter (e.g., {"$gte": datetime(2024, 1, 1)})
            venue_filter: Optional boolean to filter by venue (True=home, False=away, None=all)
            result_filter: Optional string to filter by result ('won', 'lost', None=all)

        Returns:
            List of opponent statistics dictionaries grouped by team
        """
        if not self.connection.is_connected():
            return []

        try:
            collection = self.connection.get_collection(collection_name)

            # Detect if this is a FBCYL collection
            is_fbcyl = _is_fbcyl(collection_name)

            if is_fbcyl:
                pipeline = FBCYLPipelineBuilder.build_opponent_stats_pipeline(date_filter, venue_filter, result_filter)
            else:
                pipeline = AggregationPipelineBuilder.build_opponent_stats_pipeline(date_filter, venue_filter, result_filter)

            return list(collection.aggregate(pipeline))
        except PyMongoError as e:
            return []

    def get_last_match(self, collection_name: str, team_name: str) -> Dict:
        """
        Get the last match document for a specific team.

        Args:
            collection_name: Name of the collection
            team_name: Name of the team to find

        Returns:
            Last match document or empty dict if not found
        """
        if not self.connection.is_connected():
            return {}

        try:
            collection = self.connection.get_collection(collection_name)
            is_fbcyl = _is_fbcyl(collection_name)

            if is_fbcyl:
                # FBCYL format: stats.teams[].name and stats.startDate
                pipeline = [
                    {
                        "$addFields": {
                            "parsedDate": {
                                "$dateFromString": {
                                    "dateString": "$stats.startDate",
                                    "format": "%Y-%m-%dT%H:%M:%S.%LZ",
                                    "onError": None,
                                    "onNull": None
                                }
                            }
                        }
                    },
                    {
                        "$match": {
                            "stats.teams.name": team_name
                        }
                    },
                    {"$sort": {"parsedDate": -1}},
                    {"$limit": 1}
                ]
            else:
                # FEB format: HEADER.TEAM.name and HEADER.starttime
                pipeline = [
                    {
                        "$addFields": {
                            "parsedDate": {
                                "$dateFromString": {
                                    "dateString": "$HEADER.starttime",
                                    "format": "%d-%m-%Y - %H:%M",
                                    "onError": None,
                                    "onNull": None
                                }
                            }
                        }
                    },
                    {
                        "$match": {
                            "HEADER.TEAM.name": team_name
                        }
                    },
                    {"$sort": {"parsedDate": -1}},
                    {"$limit": 1}
                ]

            result = list(collection.aggregate(pipeline))
            return result[0] if result else {}
        except PyMongoError as e:
            return {}

    def get_all_teams(self, collection_name: str) -> List[str]:
        """
        Get list of all unique team names in the collection.
        Supports both FEB and FBCYL data formats.

        Args:
            collection_name: Name of the collection

        Returns:
            Sorted list of team names
        """
        if not self.connection.is_connected():
            return []

        try:
            collection = self.connection.get_collection(collection_name)

            # Detect if this is a FBCYL collection
            is_fbcyl = _is_fbcyl(collection_name)

            if is_fbcyl:
                # FBCYL format: teams.name
                teams = collection.distinct("teams.name")
            else:
                # FEB format: HEADER.TEAM.name
                teams = collection.distinct("HEADER.TEAM.name")

            return sorted(teams)
        except PyMongoError as e:
            return []

    def get_teams_with_ids(self, collection_name: str) -> List[Dict]:
        """Return a deduplicated list of teams as ``{"id": str, "name": str}`` dicts.

        Uses an aggregation pipeline that groups by the stable team ID, so a team
        that changed sponsor mid-season appears only once with its most-recent name.
        Supports both FEB (``HEADER.TEAM.id``) and FBCYL (``stats.teams.teamIdExtern``).

        Args:
            collection_name: MongoDB collection name.

        Returns:
            Sorted list of ``{"id": str, "name": str}`` dicts, or ``[]`` on error.
        """
        if not self.connection.is_connected():
            return []

        try:
            collection = self.connection.get_collection(collection_name)
            is_fbcyl = _is_fbcyl(collection_name)

            if is_fbcyl:
                pipeline = [
                    {"$unwind": "$stats.teams"},
                    {"$group": {
                        "_id": "$stats.teams.teamIdExtern",
                        "name": {"$last": "$stats.teams.name"},
                    }},
                    {"$project": {"_id": 0, "id": {"$toString": "$_id"}, "name": 1}},
                    {"$sort": {"name": 1}},
                ]
            else:
                pipeline = [
                    {"$unwind": "$HEADER.TEAM"},
                    {"$group": {
                        "_id": "$HEADER.TEAM.id",
                        "name": {"$last": "$HEADER.TEAM.name"},
                    }},
                    {"$project": {"_id": 0, "id": {"$toString": "$_id"}, "name": 1}},
                    {"$sort": {"name": 1}},
                ]

            return list(collection.aggregate(pipeline))
        except Exception:
            return []

    def get_player_stats(self, collection_name: str, date_filter: Dict = None, venue_filter: bool = None, result_filter: str = None, team_filter: str = None) -> List[Dict]:
        """
        Get aggregated player statistics from all matches in the collection.

        Returns a list of dictionaries containing each player's season statistics including:
        - Total games played
        - Total minutes played
        - Total points, assists, rebounds, etc.
        - Shooting percentages
        - Per-game averages

        Args:
            collection_name: Name of the collection
            date_filter: Optional MongoDB date filter dict with datetime object
            venue_filter: Optional boolean to filter by venue (True=home, False=away, None=all)
            result_filter: Optional string to filter by result ('won', 'lost', None=all)
            team_filter: Optional team name to restrict to a single team before player unwind

        Returns:
            List of player statistics dictionaries
        """
        if not self.connection.is_connected():
            return []

        try:
            collection = self.connection.get_collection(collection_name)

            # Detect if this is a FBCYL collection
            is_fbcyl = _is_fbcyl(collection_name)

            if is_fbcyl:
                pipeline = FBCYLPipelineBuilder.build_player_stats_pipeline(date_filter, venue_filter, result_filter, team_filter=team_filter)
            else:
                pipeline = AggregationPipelineBuilder.build_player_stats_pipeline(date_filter, venue_filter, result_filter, team_filter=team_filter)

            return list(collection.aggregate(pipeline))
        except PyMongoError as e:
            return []

    def get_aggregated_team_stats(self, collection_name: str, team_name: str) -> Dict:
        """
        Get aggregated statistics for a specific team across all their games.

        Args:
            collection_name: Name of the collection
            team_name: Name of the team

        Returns:
            Dictionary with aggregated team statistics
        """
        if not self.connection.is_connected():
            return {}

        try:
            collection = self.connection.get_collection(collection_name)
            team_stats = self.get_team_stats(collection_name)

            for team in team_stats:
                if team.get('team_name') == team_name:
                    return team

            return {}
        except PyMongoError as e:
            return {}

    def get_aggregated_opponent_stats(self, collection_name: str, team_name: str) -> Dict:
        """
        Get aggregated opponent statistics for a specific team.

        Args:
            collection_name: Name of the collection
            team_name: Name of the team

        Returns:
            Dictionary with aggregated opponent statistics
        """
        if not self.connection.is_connected():
            return {}

        try:
            collection = self.connection.get_collection(collection_name)
            opp_stats = self.get_opponent_stats(collection_name)

            for opp in opp_stats:
                if opp.get('team_name') == team_name:
                    return opp

            return {}
        except PyMongoError as e:
            return {}

    def get_league_stats(self, collection_name: str) -> Dict:
        """
        Get league-wide aggregated statistics.

        Args:
            collection_name: Name of the collection

        Returns:
            Dictionary with league-wide statistics
        """
        if not self.connection.is_connected():
            return {}

        try:
            collection = self.connection.get_collection(collection_name)

            # Aggregate all team statistics to get league totals
            pipeline = [
                {
                    "$addFields": {
                        "teams": [
                            {
                                "pts": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pts", 0]}},
                                "fga": {"$add": [
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p1a", 0]}},
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p2a", 0]}},
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p3a", 0]}}
                                ]},
                                "fgm": {"$add": [
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p2m", 0]}},
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p3m", 0]}}
                                ]},
                                "ftm": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p1m", 0]}},
                                "fta": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p1a", 0]}},
                                "orb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.ro", 0]}},
                                "drb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.rd", 0]}},
                                "trb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.rt", 0]}},
                                "ast": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.assist", 0]}},
                                "tov": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.to", 0]}},
                                "pf": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pf", 0]}},
                                "3pa": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p3a", 0]}}
                            },
                            {
                                "pts": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pts", 1]}},
                                "fga": {"$add": [
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p1a", 1]}},
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p2a", 1]}},
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p3a", 1]}}
                                ]},
                                "fgm": {"$add": [
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p2m", 1]}},
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p3m", 1]}}
                                ]},
                                "ftm": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p1m", 1]}},
                                "fta": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p1a", 1]}},
                                "orb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.ro", 1]}},
                                "drb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.rd", 1]}},
                                "trb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.rt", 1]}},
                                "ast": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.assist", 1]}},
                                "tov": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.to", 1]}},
                                "pf": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pf", 1]}},
                                "3pa": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p3a", 1]}}
                            }
                        ]
                    }
                },
                {
                    "$unwind": "$teams"
                },
                {
                    "$group": {
                        "_id": None,
                        "total_games": {"$sum": 1},  # Count number of games (team-games, not actual games)
                        "total_pts": {"$sum": "$teams.pts"},
                        "total_fga": {"$sum": "$teams.fga"},
                        "total_fgm": {"$sum": "$teams.fgm"},
                        "total_ftm": {"$sum": "$teams.ftm"},
                        "total_fta": {"$sum": "$teams.fta"},
                        "total_orb": {"$sum": "$teams.orb"},
                        "total_drb": {"$sum": "$teams.drb"},
                        "total_trb": {"$sum": "$teams.trb"},
                        "total_ast": {"$sum": "$teams.ast"},
                        "total_tov": {"$sum": "$teams.tov"},
                        "total_pf": {"$sum": "$teams.pf"},
                        "total_3pa": {"$sum": "$teams.3pa"}
                    }
                },
                {
                    "$addFields": {
                        # Calculate total possessions using the formula:
                        # Poss = FGA + 0.4*FTA - 1.07*ORB_pct*(FGA-FGM) + TOV
                        # Simplified here as: FGA + 0.4*FTA - 0.4*ORB + TOV
                        "total_possessions": {
                            "$add": [
                                "$total_fga",
                                {"$multiply": [0.4, "$total_fta"]},
                                {"$multiply": [-0.4, "$total_orb"]},
                                "$total_tov"
                            ]
                        }
                    }
                }
            ]

            result = list(collection.aggregate(pipeline))
            return result[0] if result else {}
        except PyMongoError as e:
            return {}

    def get_games_with_playbyplay(self, collection_name: str, date_filter: Dict = None) -> List[Dict]:
        """
        Get all game documents that contain PLAYBYPLAY data.

        Args:
            collection_name: Name of the collection
            date_filter: Optional MongoDB date filter dict with datetime object

        Returns:
            List of game documents with PLAYBYPLAY data
        """
        if not self.connection.is_connected():
            return []

        try:
            collection = self.connection.get_collection(collection_name)
            
            # Ensure indexes exist for optimal performance
            self.connection.ensure_indexes(collection_name)

            # Detect if this is a FBCYL collection
            is_fbcyl = _is_fbcyl(collection_name)

            if is_fbcyl:
                # FBCYL: Check for 'moves' field
                match_filter = {"moves": {"$exists": True, "$ne": None}}

                if date_filter:
                    # FBCYL uses stats.time field
                    pipeline = [
                        {
                            "$addFields": {
                                "parsedDate": {
                                    "$dateFromString": {
                                        "dateString": "$stats.time",
                                        "format": "%b %d, %Y %I:%M:%S %p",
                                        "onError": None,
                                        "onNull": None
                                    }
                                }
                            }
                        },
                        {
                            "$match": {
                                "parsedDate": date_filter,
                                "moves": {"$exists": True, "$ne": None}
                            }
                        }
                    ]
                    return list(collection.aggregate(pipeline))
                else:
                    return list(collection.find(match_filter))
            else:
                # FEB: Check for PLAYBYPLAY.LINES
                match_filter = {"PLAYBYPLAY.LINES": {"$exists": True, "$ne": None}}

                if date_filter:
                    # Add date parsing to the pipeline
                    pipeline = [
                        {
                            "$addFields": {
                                "parsedDate": {
                                    "$dateFromString": {
                                        "dateString": "$HEADER.starttime",
                                        "format": "%d-%m-%Y - %H:%M",
                                        "onError": None,
                                        "onNull": None
                                    }
                                }
                            }
                        },
                        {
                            "$match": {
                                "parsedDate": date_filter,
                                "PLAYBYPLAY.LINES": {"$exists": True, "$ne": None}
                            }
                        }
                    ]
                    return list(collection.aggregate(pipeline))
                else:
                    return list(collection.find(match_filter))

        except PyMongoError as e:
            return []

    def get_games_for_team(self, collection_name: str, team_id: str, 
                           only_with_playbyplay: bool = False) -> List[Dict]:
        """
        Get all games for a specific team.

        Args:
            collection_name: Name of the collection
            team_id: Team ID
            only_with_playbyplay: If True, only return games with play-by-play data

        Returns:
            List of game documents where the team participated
        """
        if not self.connection.is_connected():
            return []

        try:
            collection = self.connection.get_collection(collection_name)
            
            # Ensure indexes exist for optimal performance
            self.connection.ensure_indexes(collection_name)
            
            is_fbcyl = _is_fbcyl(collection_name)

            if is_fbcyl:
                # FBCYL: Check in stats.teams array
                match_filter = {
                    "$or": [
                        {"stats.teams.teamIdIntern": team_id},
                        {"stats.teams.teamIdIntern": int(team_id) if team_id.isdigit() else team_id},
                        {"stats.teams.teamIdExtern": team_id},
                        {"stats.teams.teamIdExtern": int(team_id) if team_id.isdigit() else team_id}
                    ]
                }
                
                # Add play-by-play filter if requested
                if only_with_playbyplay:
                    match_filter["moves"] = {"$exists": True, "$ne": None}
            else:
                # FEB: Check in HEADER.TEAM array
                match_filter = {
                    "HEADER.TEAM.id": team_id
                }
                
                # Add play-by-play filter if requested
                if only_with_playbyplay:
                    match_filter["PLAYBYPLAY.LINES"] = {"$exists": True, "$ne": None}

            return list(collection.find(match_filter))

        except PyMongoError as e:
            return []

