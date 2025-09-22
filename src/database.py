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
        """Generate collection name in the format {competicion}_{temporada}_{Grupo}."""
        safe_group = re.sub(r'[\\/:*?"<>|]', '_', group)
        safe_competition = competition.replace('.', '_')
        safe_season = season.replace('/', '_')
        return f"{safe_competition}_{safe_season}_{safe_group}"