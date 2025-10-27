import pymongo
from pymongo.errors import ConnectionFailure, PyMongoError
from typing import Optional, Dict, List
import re

class MongoDBHandler:
    """A class to handle MongoDB operations for basketball data."""

    def __init__(self, connection_string: str = "mongodb+srv://kanijoman:S0p0rt3s@mycluster.g3slkjv.mongodb.net/"):
        """Initialize MongoDB client."""
        try:
            self.client = pymongo.MongoClient(connection_string)
            self.client.server_info()  # Test connection
            self.db = self.client["FEB"]
        except ConnectionFailure as e:
            print(f"[MongoDBHandler] Failed to connect to MongoDB: {e}")
            self.client = None
            self.db = None

    def is_connected(self) -> bool:
        """Check if MongoDB client is connected."""
        return self.client is not None and self.db is not None

    def document_exists(self, collection_name: str, match_code: int) -> bool:
        """Check if a document with the given match_code exists in the collection."""
        if not self.is_connected():
            print(f"[MongoDBHandler] No connection to MongoDB")
            return False
        try:
            collection = self.db[collection_name]
            return collection.find_one({"_id": match_code}) is not None
        except PyMongoError as e:
            print(f"[MongoDBHandler] Error checking document existence for match {match_code}: {e}")
            return False

    def insert_boxscore(self, collection_name: str, match_code: str, boxscore: Dict) -> bool:
        """Insert a boxscore document into the specified collection."""
        if not self.is_connected():
            print(f"[MongoDBHandler] No connection to MongoDB")
            return False
        try:
            collection = self.db[collection_name]
            boxscore["_id"] = int(match_code)
            collection.insert_one(boxscore)
            return True
        except PyMongoError as e:
            print(f"[MongoDBHandler] Failed to save match {match_code} to MongoDB: {e}")
            return False

    @staticmethod
    def get_collection_name(competition: str, season: str, group: str) -> str:
        """Generate collection name in the format {competicion}_{temporada}_{Grupo}.

        Removes or replaces invalid MongoDB characters and whitespace:
        - Replaces spaces, tabs, newlines with underscores
        - Removes $ and other special MongoDB characters
        - Ensures name doesn't start with 'system.' or contain null character
        """
        # First, replace all whitespace characters with underscore
        safe_competition = re.sub(r'\s+', '_', competition.strip())
        safe_season = re.sub(r'\s+', '_', season.strip())
        safe_group = re.sub(r'\s+', '_', group.strip())

        # Replace invalid MongoDB characters and common problematic characters
        pattern = r'[\\/:*?"<>|.$\x00-\x1F\x7F]'
        safe_competition = re.sub(pattern, '_', safe_competition)
        safe_season = re.sub(pattern, '_', safe_season)
        safe_group = re.sub(pattern, '_', safe_group)

        # Collapse multiple underscores into one
        safe_competition = re.sub(r'_+', '_', safe_competition)
        safe_season = re.sub(r'_+', '_', safe_season)
        safe_group = re.sub(r'_+', '_', safe_group)

        # Remove leading/trailing underscores
        safe_competition = safe_competition.strip('_')
        safe_season = safe_season.strip('_')
        safe_group = safe_group.strip('_')

        collection_name = f"{safe_competition}_{safe_season}_{safe_group}"

        # Ensure the name doesn't start with 'system.'
        if collection_name.lower().startswith('system.'):
            collection_name = 'col_' + collection_name

        return collection_name