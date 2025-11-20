"""Repository for basketball data operations."""

from typing import Dict, List
from pymongo.errors import PyMongoError

from .connection import MongoDBConnection
from .aggregation import AggregationPipelineBuilder


class BasketballRepository:
    """Repository for basketball data CRUD operations."""

    def __init__(self, connection: MongoDBConnection):
        """
        Initialize repository with a MongoDB connection.

        Args:
            connection: MongoDBConnection instance
        """
        self.connection = connection

    def document_exists(self, collection_name: str, match_code: int) -> bool:
        """
        Check if a document with the given match_code exists in the collection.

        Args:
            collection_name: Name of the collection
            match_code: Match identifier

        Returns:
            True if document exists, False otherwise
        """
        if not self.connection.is_connected():
            print(f"[BasketballRepository] No connection to MongoDB")
            return False

        try:
            collection = self.connection.get_collection(collection_name)
            return collection.find_one({"_id": match_code}) is not None
        except PyMongoError as e:
            print(f"[BasketballRepository] Error checking document existence for match {match_code}: {e}")
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
            print(f"[BasketballRepository] No connection to MongoDB")
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
            print(f"[BasketballRepository] Failed to save match {match_code} to MongoDB: {e}")
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
            print("[BasketballRepository] No connection to MongoDB")
            return []

        try:
            collection = self.connection.get_collection(collection_name)
            pipeline = AggregationPipelineBuilder.build_team_stats_pipeline(date_filter, venue_filter, result_filter)
            return list(collection.aggregate(pipeline))
        except PyMongoError as e:
            print(f"[BasketballRepository] Error getting team stats: {e}")
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
            print("[BasketballRepository] No connection to MongoDB")
            return []

        try:
            collection = self.connection.get_collection(collection_name)
            pipeline = AggregationPipelineBuilder.build_opponent_stats_pipeline(date_filter, venue_filter, result_filter)
            return list(collection.aggregate(pipeline))
        except PyMongoError as e:
            print(f"[BasketballRepository] Error getting opponent stats: {e}")
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
            print("[BasketballRepository] No connection to MongoDB")
            return {}

        try:
            collection = self.connection.get_collection(collection_name)

            # First, add parsed date field and filter by team
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
            print(f"[BasketballRepository] Error getting last match: {e}")
            return {}

    def get_all_teams(self, collection_name: str) -> List[str]:
        """
        Get list of all unique team names in the collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Sorted list of team names
        """
        if not self.connection.is_connected():
            print("[BasketballRepository] No connection to MongoDB")
            return []

        try:
            collection = self.connection.get_collection(collection_name)
            teams = collection.distinct("HEADER.TEAM.name")
            return sorted(teams)
        except PyMongoError as e:
            print(f"[BasketballRepository] Error getting teams: {e}")
            return []

    def get_player_stats(self, collection_name: str, date_filter: Dict = None, venue_filter: bool = None, result_filter: str = None) -> List[Dict]:
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

        Returns:
            List of player statistics dictionaries
        """
        if not self.connection.is_connected():
            print("[BasketballRepository] No connection to MongoDB")
            return []

        try:
            collection = self.connection.get_collection(collection_name)
            pipeline = AggregationPipelineBuilder.build_player_stats_pipeline(date_filter, venue_filter, result_filter)
            return list(collection.aggregate(pipeline))
        except PyMongoError as e:
            print(f"[BasketballRepository] Error getting player stats: {e}")
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
            print("[BasketballRepository] No connection to MongoDB")
            return {}

        try:
            collection = self.connection.get_collection(collection_name)
            team_stats = self.get_team_stats(collection_name)

            for team in team_stats:
                if team.get('team_name') == team_name:
                    return team

            return {}
        except PyMongoError as e:
            print(f"[BasketballRepository] Error getting aggregated team stats: {e}")
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
            print("[BasketballRepository] No connection to MongoDB")
            return {}

        try:
            collection = self.connection.get_collection(collection_name)
            opp_stats = self.get_opponent_stats(collection_name)

            for opp in opp_stats:
                if opp.get('team_name') == team_name:
                    return opp

            return {}
        except PyMongoError as e:
            print(f"[BasketballRepository] Error getting aggregated opponent stats: {e}")
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
            print("[BasketballRepository] No connection to MongoDB")
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
            print(f"[BasketballRepository] Error getting league stats: {e}")
            return {}
