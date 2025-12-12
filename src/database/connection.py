"""MongoDB connection management."""

import pymongo
from pymongo.errors import ConnectionFailure
from .db_config import get_mongodb_connection_string


class MongoDBConnection:
    """Manages MongoDB connection."""

    def __init__(self, connection_string: str = None):
        """
        Initialize MongoDB client.

        Args:
            connection_string: MongoDB connection URI (optional, uses config if not provided)
        """
        if connection_string is None:
            connection_string = get_mongodb_connection_string()

        try:
            self.client = pymongo.MongoClient(connection_string)
            self.client.server_info()  # Test connection
            self.db = self.client["FEB"]
            self._connected = True
        except ConnectionFailure as e:
            print(f"[MongoDBConnection] Failed to connect to MongoDB: {e}")
            self.client = None
            self.db = None
            self._connected = False

    def is_connected(self) -> bool:
        """
        Check if MongoDB client is connected.

        Returns:
            True if connected, False otherwise
        """
        return self._connected and self.client is not None and self.db is not None

    def get_database(self):
        """
        Get the database instance.

        Returns:
            MongoDB database instance or None if not connected
        """
        return self.db if self.is_connected() else None

    def get_collection(self, collection_name: str):
        """
        Get a collection from the database.

        Args:
            collection_name: Name of the collection

        Returns:
            MongoDB collection instance or None if not connected
        """
        if not self.is_connected():
            print(f"[MongoDBConnection] No connection to MongoDB")
            return None
        return self.db[collection_name]

    def close(self):
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            self._connected = False
