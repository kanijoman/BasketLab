"""Player statistics service.

Encapsulates player stats loading, IN/OUT analysis, and pair analysis,
decoupled from the PyQt6 UI layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from database import MongoDBHandler


class PlayerStatsService:
    """High-level service for player statistics.

    Responsibilities
    ----------------
    - Load raw player stats from the database (with optional filters).
    - Orchestrate IN/OUT analysis requests (delegates to repository).
    - Orchestrate two-player together-on-court analysis.
    - Expose individual stat retrieval with a teammate context.

    This class contains no PyQt6 imports.

    Example
    -------
    ::

        from database import MongoDBHandler
        from services import PlayerStatsService

        handler = MongoDBHandler()
        svc = PlayerStatsService(handler)
        players = svc.load_season_data("FEB_LF2_2025_A")
    """

    def __init__(self, db_handler: "MongoDBHandler") -> None:
        self._db = db_handler

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_season_data(
        self,
        collection_name: str,
        date_filter: Optional[Dict] = None,
        venue_filter: Optional[bool] = None,
        result_filter: Optional[str] = None,
    ) -> List[Dict]:
        """Load aggregated player stats for a collection.

        Args:
            collection_name: MongoDB collection name.
            date_filter: Optional MongoDB date range dict.
            venue_filter: ``True`` = home only, ``False`` = away only.
            result_filter: ``"won"``, ``"lost"``, or ``None``.

        Returns:
            List of player stat dicts (may be empty).
        """
        return self._db.get_player_stats(
            collection_name, date_filter, venue_filter, result_filter
        ) or []

    def get_in_out_analysis(
        self,
        collection_name: str,
        player_id: str,
        date_filter: Optional[Dict] = None,
        debug: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> Dict:
        """Return IN/OUT on-court impact analysis for a player.

        Args:
            collection_name: MongoDB collection name.
            player_id: Player identifier (FEB int-string or FBCYL UUID).
            date_filter: Optional date range filter.
            debug: If ``True``, saves per-game raw outputs.
            progress_callback: Optional ``(current, total) -> None`` callback.

        Returns:
            Dict with in/out stats, or empty dict on failure.
        """
        return self._db.get_player_in_out_stats(
            collection_name, player_id, date_filter,
            debug=debug, progress_callback=progress_callback
        ) or {}

    def get_players_together(
        self,
        collection_name: str,
        player1_id: str,
        player2_id: str,
        date_filter: Optional[Dict] = None,
        debug: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> Dict:
        """Return stats when two players are simultaneously on court.

        Args:
            collection_name: MongoDB collection name.
            player1_id: First player identifier.
            player2_id: Second player identifier.
            date_filter: Optional date range filter.
            debug: If ``True``, saves per-game raw outputs.
            progress_callback: Optional progress callback.

        Returns:
            Dict with combined stats, or empty dict on failure.
        """
        return self._db.get_two_players_together_stats(
            collection_name, player1_id, player2_id, date_filter,
            debug=debug, progress_callback=progress_callback
        ) or {}

    def get_player_with_teammate(
        self,
        collection_name: str,
        main_player_id: str,
        teammate_id: str,
        date_filter: Optional[Dict] = None,
        debug: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> Dict:
        """Return individual stats of ``main_player`` when playing with ``teammate``.

        Args:
            collection_name: MongoDB collection name.
            main_player_id: The player whose stats are returned.
            teammate_id: The teammate who must also be on court.
            date_filter: Optional date range filter.
            debug: Debug mode flag.
            progress_callback: Optional progress callback.

        Returns:
            Dict of individual stats, or empty dict on failure.
        """
        return self._db.get_player_individual_stats_with_teammate(
            collection_name, main_player_id, teammate_id, date_filter,
            debug=debug, progress_callback=progress_callback
        ) or {}
