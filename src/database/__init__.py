"""Database package for basketball statistics."""

from .connection import MongoDBConnection
from .repository import BasketballRepository
from .utils import get_collection_name


class MongoDBHandler:
    """
    Main database handler class for backward compatibility.
    Delegates operations to MongoDBConnection and BasketballRepository.
    """

    def __init__(self, connection_string: str = None):
        """
        Initialize MongoDB handler.

        Args:
            connection_string: MongoDB connection URI (optional, uses config if not provided)
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

    def insert_fbcyl_match(self, collection_name: str, match_uuid: str, match_data: dict) -> bool:
        """Insert a FBCYL match document with complete data (moves + stats)."""
        return self.repository.insert_fbcyl_match(collection_name, match_uuid, match_data)

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

    def get_player_stats(self, collection_name: str, date_filter: dict = None, venue_filter: bool = None, result_filter: str = None) -> list:
        """Get aggregated player statistics."""
        return self.repository.get_player_stats(collection_name, date_filter, venue_filter, result_filter)

    def get_aggregated_team_stats(self, collection_name: str, team_name: str) -> dict:
        """Get aggregated team statistics for advanced calculations."""
        return self.repository.get_aggregated_team_stats(collection_name, team_name)

    def get_aggregated_opponent_stats(self, collection_name: str, team_name: str) -> dict:
        """Get aggregated opponent statistics for advanced calculations."""
        return self.repository.get_aggregated_opponent_stats(collection_name, team_name)

    def get_league_stats(self, collection_name: str) -> dict:
        """Get league-wide statistics for advanced calculations."""
        return self.repository.get_league_stats(collection_name)

    def get_player_in_out_stats(self, collection_name: str, player_id: str,
                                 date_filter: dict = None, debug: bool = False,
                                 progress_callback=None) -> dict:
        """Get IN/OUT statistics for a specific player. Pass `debug=True` to save per-game raw outputs."""
        return self.repository.get_player_in_out_stats(collection_name, player_id, date_filter,
                                                       debug=debug, progress_callback=progress_callback)

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
