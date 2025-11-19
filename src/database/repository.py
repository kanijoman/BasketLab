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

    def get_team_stats(self, collection_name: str, date_filter: Dict = None) -> List[Dict]:
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

        Returns:
            List of team statistics dictionaries
        """
        if not self.connection.is_connected():
            print("[BasketballRepository] No connection to MongoDB")
            return []

        try:
            collection = self.connection.get_collection(collection_name)
            pipeline = AggregationPipelineBuilder.build_team_stats_pipeline(date_filter)
            return list(collection.aggregate(pipeline))
        except PyMongoError as e:
            print(f"[BasketballRepository] Error getting team stats: {e}")
            return []

    def get_opponent_stats(self, collection_name: str, date_filter: Dict = None) -> List[Dict]:
        """
        Get aggregated opponent statistics grouped by team.

        This shows what each team's opponents have done against them across all matches.
        Useful for defensive analysis and understanding the strength of opposition faced.

        Args:
            collection_name: Name of the collection
            date_filter: Optional MongoDB date filter (e.g., {"$gte": datetime(2024, 1, 1)})

        Returns:
            List of opponent statistics dictionaries grouped by team
        """
        if not self.connection.is_connected():
            print("[BasketballRepository] No connection to MongoDB")
            return []

        try:
            collection = self.connection.get_collection(collection_name)
            pipeline = AggregationPipelineBuilder.build_opponent_stats_pipeline(date_filter)
            return list(collection.aggregate(pipeline))
        except PyMongoError as e:
            print(f"[BasketballRepository] Error getting opponent stats: {e}")
            return []
