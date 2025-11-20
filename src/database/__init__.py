"""Database package for basketball statistics."""

from .connection import MongoDBConnection
from .repository import BasketballRepository
from .utils import get_collection_name


class MongoDBHandler:
    """
    Main database handler class for backward compatibility.
    Delegates operations to MongoDBConnection and BasketballRepository.
    """

    def __init__(self, connection_string: str = "mongodb+srv://kanijoman:S0p0rt3s@mycluster.g3slkjv.mongodb.net/"):
        """
        Initialize MongoDB handler.

        Args:
            connection_string: MongoDB connection URI
        """
        self.connection = MongoDBConnection(connection_string)
        self.repository = BasketballRepository(self.connection)

    def is_connected(self) -> bool:
        """Check if MongoDB client is connected."""
        return self.connection.is_connected()

    def document_exists(self, collection_name: str, match_code: int) -> bool:
        """Check if a document exists in the collection."""
        return self.repository.document_exists(collection_name, match_code)

    def insert_boxscore(self, collection_name: str, match_code: str, boxscore: dict) -> bool:
        """Insert a boxscore document."""
        return self.repository.insert_boxscore(collection_name, match_code, boxscore)

    def get_team_stats(self, collection_name: str, date_filter: dict = None, venue_filter: bool = None, result_filter: str = None) -> list:
        """Get aggregated team statistics."""
        return self.repository.get_team_stats(collection_name, date_filter, venue_filter, result_filter)

    def get_opponent_stats(self, collection_name: str, date_filter: dict = None, venue_filter: bool = None, result_filter: str = None) -> list:
        """Get opponent statistics grouped by team."""
        return self.repository.get_opponent_stats(collection_name, date_filter, venue_filter, result_filter)

    def get_last_match(self, collection_name: str, team_name: str) -> dict:
        """Get the last match document for a specific team."""
        return self.repository.get_last_match(collection_name, team_name)

    def get_all_teams(self, collection_name: str) -> list:
        """Get list of all unique team names in the collection."""
        return self.repository.get_all_teams(collection_name)

    def get_player_stats(self, collection_name: str) -> list:
        """Get aggregated player statistics."""
        return self.repository.get_player_stats(collection_name)

    @staticmethod
    def get_collection_name(competition: str, season: str, group: str) -> str:
        """Generate safe collection name."""
        return get_collection_name(competition, season, group)


__all__ = [
    'MongoDBHandler',
    'MongoDBConnection',
    'BasketballRepository',
    'get_collection_name'
]
