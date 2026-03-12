"""MongoDB index creation and management for performance optimization."""

from typing import Dict, List
import pymongo

from utils.collection_utils import is_fbcyl as _is_fbcyl


class IndexManager:
    """Manages MongoDB indexes for optimal query performance."""

    def __init__(self, connection):
        """
        Initialize index manager.

        Args:
            connection: MongoDBConnection instance
        """
        self.connection = connection

    def ensure_indexes(self, collection_name: str) -> bool:
        """
        Create indexes for a collection if they don't exist.
        
        This method is safe to call multiple times - MongoDB will skip
        index creation if it already exists.

        Args:
            collection_name: Name of the collection

        Returns:
            True if successful, False otherwise
        """
        if not self.connection.is_connected():
            print(f"[IndexManager] Cannot create indexes - not connected to MongoDB")
            return False

        try:
            collection = self.connection.get_collection(collection_name)
            is_fbcyl = _is_fbcyl(collection_name)

            if is_fbcyl:
                return self._ensure_fbcyl_indexes(collection)
            else:
                return self._ensure_feb_indexes(collection)

        except Exception as e:
            print(f"[IndexManager] Error ensuring indexes for {collection_name}: {e}")
            return False

    def _ensure_fbcyl_indexes(self, collection) -> bool:
        """
        Create indexes for FBCYL collections.

        Indexes:
        1. moves: For finding games with play-by-play data
        2. stats.time: For date filtering
        3. stats.teams.players.uuid: For finding player games
        4. stats.teams.teamIdIntern: For team queries
        """
        try:
            # Index 1: Check if moves exist (for play-by-play queries)
            collection.create_index(
                [("moves", pymongo.ASCENDING)],
                name="moves_1",
                background=True
            )

            # Index 2: Date field for filtering (compound with moves)
            collection.create_index(
                [("stats.time", pymongo.ASCENDING), ("moves", pymongo.ASCENDING)],
                name="stats_time_1_moves_1",
                background=True
            )

            # Index 3: Player UUID for player-specific queries
            collection.create_index(
                [("stats.teams.players.uuid", pymongo.ASCENDING)],
                name="player_uuid_1",
                background=True
            )

            # Index 4: Team ID for team queries
            collection.create_index(
                [("stats.teams.teamIdIntern", pymongo.ASCENDING)],
                name="team_id_intern_1",
                background=True
            )

            # Index 5: External team ID (backup identifier)
            collection.create_index(
                [("stats.teams.teamIdExtern", pymongo.ASCENDING)],
                name="team_id_extern_1",
                background=True
            )

            print(f"[IndexManager] Successfully ensured FBCYL indexes")
            return True

        except Exception as e:
            print(f"[IndexManager] Error creating FBCYL indexes: {e}")
            return False

    def _ensure_feb_indexes(self, collection) -> bool:
        """
        Create indexes for FEB collections.

        Indexes:
        1. PLAYBYPLAY.LINES: For finding games with play-by-play data
        2. HEADER.date: For date filtering
        3. BOXSCORE.TEAM.PLAYER.id: For player queries
        4. HEADER.TEAM.id: For team queries
        """
        try:
            # Index 1: Check if PLAYBYPLAY exists
            collection.create_index(
                [("PLAYBYPLAY.LINES", pymongo.ASCENDING)],
                name="playbyplay_lines_1",
                background=True
            )

            # Index 2: Date field for filtering (compound with PLAYBYPLAY)
            collection.create_index(
                [("HEADER.date", pymongo.ASCENDING), ("PLAYBYPLAY.LINES", pymongo.ASCENDING)],
                name="header_date_1_playbyplay_1",
                background=True
            )

            # Index 3: Player IDs for player-specific queries
            collection.create_index(
                [("BOXSCORE.TEAM.PLAYER.id", pymongo.ASCENDING)],
                name="player_id_1",
                background=True
            )

            # Index 4: Team IDs for team queries
            collection.create_index(
                [("HEADER.TEAM.id", pymongo.ASCENDING)],
                name="team_id_1",
                background=True
            )

            return True

        except Exception as e:
            print(f"[IndexManager] Error creating FEB indexes: {e}")
            return False

    def list_indexes(self, collection_name: str) -> List[Dict]:
        """
        List all indexes on a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            List of index information dictionaries
        """
        if not self.connection.is_connected():
            return []

        try:
            collection = self.connection.get_collection(collection_name)
            return list(collection.list_indexes())
        except Exception as e:
            print(f"[IndexManager] Error listing indexes: {e}")
            return []

    def drop_index(self, collection_name: str, index_name: str) -> bool:
        """
        Drop a specific index from a collection.

        Args:
            collection_name: Name of the collection
            index_name: Name of the index to drop

        Returns:
            True if successful, False otherwise
        """
        if not self.connection.is_connected():
            return False

        try:
            collection = self.connection.get_collection(collection_name)
            collection.drop_index(index_name)
            print(f"[IndexManager] Dropped index {index_name} from {collection_name}")
            return True
        except Exception as e:
            print(f"[IndexManager] Error dropping index: {e}")
            return False

    def get_index_stats(self, collection_name: str) -> Dict:
        """
        Get statistics about index usage.

        Args:
            collection_name: Name of the collection

        Returns:
            Dictionary with index statistics
        """
        if not self.connection.is_connected():
            return {}

        try:
            collection = self.connection.get_collection(collection_name)
            stats = collection.aggregate([{"$indexStats": {}}])
            return list(stats)
        except Exception as e:
            print(f"[IndexManager] Error getting index stats: {e}")
            return {}
