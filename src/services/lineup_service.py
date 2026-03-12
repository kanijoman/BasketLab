"""Lineup analysis service.

Wraps repository lineup queries with a clean, framework-agnostic interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from database import MongoDBHandler

from src.utils.collection_utils import is_fbcyl as _is_fbcyl


class LineupService:
    """High-level service for lineup (player combination) analysis.

    Example
    -------
    ::

        from database import MongoDBHandler
        from services import LineupService

        handler = MongoDBHandler()
        svc = LineupService(handler)
        lineups = svc.get_lineup_analysis("FEB_LF2_2025_A", "123", "Team A")
    """

    def __init__(self, db_handler: "MongoDBHandler") -> None:
        self._db = db_handler

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_lineup_analysis(
        self,
        collection_name: str,
        team_id: str,
        team_name: str,
        combination_size: int = 5,
        date_filter: Optional[Dict] = None,
        progress_callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """Return best/worst player combinations for a team.

        Args:
            collection_name: MongoDB collection name.
            team_id: Team identifier (FEB numeric string or FBCYL UUID-like).
            team_name: Human-readable team name.
            combination_size: Number of players per lineup (default 5).
            date_filter: Optional date range filter.
            progress_callback: Optional ``(current, total) -> None`` callback.

        Returns:
            List of lineup stat dicts sorted by net rating (desc), or
            empty list on failure.
        """
        fbcyl = _is_fbcyl(collection_name)
        return self._db.get_lineup_analysis(
            collection_name, team_id, team_name,
            combination_size=combination_size,
            date_filter=date_filter,
            is_fbcyl=fbcyl,
            progress_callback=progress_callback,
        ) or []
