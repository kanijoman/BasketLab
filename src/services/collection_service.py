"""Collection metadata service.

Provides a single entry point for resolving collection names and retrieving
metadata about what data is available in a MongoDB collection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from database import MongoDBHandler

from src.database.utils import get_collection_name
from src.utils.collection_utils import is_fbcyl as _is_fbcyl


class CollectionService:
    """Service for collection name resolution and metadata.

    Example
    -------
    ::

        from database import MongoDBHandler
        from services import CollectionService

        handler = MongoDBHandler()
        svc = CollectionService(handler)
        name = svc.resolve_name("FEB", "LF2 2025", "A")
        teams = svc.get_teams(name)
    """

    def __init__(self, db_handler: "MongoDBHandler") -> None:
        self._db = db_handler

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def resolve_name(competition: str, season: str, group: str) -> str:
        """Generate a safe MongoDB collection name.

        Delegates to :func:`database.utils.get_collection_name`.

        Args:
            competition: Competition name (e.g. ``"FEB"``).
            season: Season identifier (e.g. ``"LF2_2025"``).
            group: Group label (e.g. ``"A"``).

        Returns:
            Safe collection name string.
        """
        return get_collection_name(competition, season, group)

    @staticmethod
    def format_is_fbcyl(collection_name: str) -> bool:
        """Return ``True`` if the collection belongs to the FBCYL league.

        Thin wrapper around :func:`src.utils.collection_utils.is_fbcyl`.
        """
        return _is_fbcyl(collection_name)

    def get_teams(self, collection_name: str) -> List[str]:
        """Return sorted list of team names in the collection.

        Args:
            collection_name: MongoDB collection name.

        Returns:
            Sorted list of name strings.
        """
        return self._db.get_all_teams(collection_name) or []

    def collection_has_data(self, collection_name: str) -> bool:
        """Return ``True`` if the collection contains at least one document.

        Args:
            collection_name: MongoDB collection name.

        Returns:
            ``True`` if data exists, ``False`` on empty collection or DB error.
        """
        if not self._db.is_connected():
            return False
        try:
            collection = self._db.connection.get_collection(collection_name)
            return collection is not None and collection.count_documents({}, limit=1) > 0
        except Exception:
            return False
