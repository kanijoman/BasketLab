"""Collection metadata service.

Provides a single entry point for resolving collection names and retrieving
metadata about what data is available in a MongoDB collection.
"""

from __future__ import annotations

import re
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

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    # Collections whose names start with these prefixes are never basketball data
    _SKIP_PREFIXES = re.compile(r'^system\.', re.IGNORECASE)
    # Names to skip entirely
    _SKIP_NAMES: frozenset = frozenset({'test', 'admin', 'local', 'config'})
    # FBCYL collections are prefixed with FBCYL_; everything else is FEB
    _FBCYL_PREFIX = re.compile(r'^FBCYL_', re.IGNORECASE)
    # Used to extract a 4-digit year component for season parsing
    _YEAR_RE = re.compile(r'^\d{4}$')
    # Valid group suffix: single letter or 1-2 alphanumeric chars
    _GROUP_RE = re.compile(r'^[A-Z0-9]{1,2}$', re.IGNORECASE)

    def _parse_components(self, name: str, league: str) -> Dict[str, str]:
        """Best-effort parsing of competition/season/group from a collection name.

        FBCYL names look like ``FBCYL_{competition}_{season}``.
        FEB names are sanitised slugs like ``L_F_-2_2025_2026_Liga_Regular_A``.
        """
        if league == 'FBCYL':
            # Strip FBCYL_ prefix and take next token as competition
            rest = re.sub(r'^FBCYL_', '', name, flags=re.IGNORECASE)
            parts = rest.split('_', 1)
            return {
                'competition': parts[0] if parts else rest,
                'season': parts[1].replace('_', ' ') if len(parts) > 1 else '',
                'group': '',
            }

        # FEB: find first 4-digit year to split competition | season[+group]
        parts = name.split('_')
        year_idx = next(
            (i for i, p in enumerate(parts) if self._YEAR_RE.match(p)), None
        )
        if year_idx is None:
            return {'competition': name, 'season': '', 'group': ''}

        competition = '_'.join(parts[:year_idx])
        remainder = parts[year_idx:]

        # If last token looks like a group label (A, B, C, …) peel it off
        if len(remainder) > 1 and self._GROUP_RE.match(remainder[-1]):
            group = remainder[-1]
            season = '_'.join(remainder[:-1])
        else:
            group = ''
            season = '_'.join(remainder)

        return {'competition': competition, 'season': season, 'group': group}

    def list_available(self) -> List[Dict]:
        """Return metadata for every basketball collection in the database.

        Lists all MongoDB collection names and excludes system / test entries.
        Collections whose names start with ``FBCYL_`` are tagged as the FBCYL
        league; all others are assumed to be FEB data.

        Returns:
            List of dicts sorted by league → season desc → competition,
            each containing::

                {
                    "name":        str,
                    "league":      str,   # "FEB" | "FBCYL"
                    "competition": str,
                    "season":      str,
                    "group":       str,
                    "game_count":  int,
                }
        """
        if not self._db.is_connected():
            return []

        try:
            db = self._db.connection.get_database()
            all_names = db.list_collection_names()
        except Exception:
            return []

        results: List[Dict] = []
        for name in all_names:
            # Skip system/test collections
            if self._SKIP_PREFIXES.match(name) or name in self._SKIP_NAMES:
                continue

            league = 'FBCYL' if self._FBCYL_PREFIX.match(name) else 'FEB'
            components = self._parse_components(name, league)

            try:
                col = self._db.connection.get_collection(name)
                game_count = col.count_documents({}, limit=5000) if col is not None else 0
            except Exception:
                game_count = 0

            results.append({
                'name': name,
                'league': league,
                'competition': components['competition'],
                'season': components['season'],
                'group': components['group'],
                'game_count': game_count,
            })

        # Sort: league asc, season desc (lexicographic with '-' prefix), competition asc, group asc
        results.sort(key=lambda x: (
            x['league'],
            '-' + x['season'],
            x['competition'],
            x['group'],
        ))
        return results

    def drop_collection(self, collection_name: str) -> None:
        """Permanently drop a basketball collection from MongoDB.

        Guards against dropping system collections or the skip-list names.

        Args:
            collection_name: Any basketball collection name.

        Raises:
            ValueError: If the name looks like a system/reserved collection.
            RuntimeError: If the database is not connected.
        """
        if not collection_name or self._SKIP_PREFIXES.match(collection_name) \
                or collection_name in self._SKIP_NAMES:
            raise ValueError(
                f"Refusing to drop '{collection_name}': "
                "reserved or system collection."
            )
        if not self._db.is_connected():
            raise RuntimeError("Database not connected.")
        self._db.connection.get_database().drop_collection(collection_name)
