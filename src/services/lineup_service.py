"""Lineup analysis service.

Wraps repository lineup queries with a clean, framework-agnostic interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Dict, List, Optional

import numpy as np

if TYPE_CHECKING:
    from database import MongoDBHandler

from src.utils.collection_utils import is_fbcyl as _is_fbcyl

# Stats where lower values are better (sort ascending)
REVERSE_STATS = {'drtg', 'tov_pct'}


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
        stat: str = "net_rating",
        date_filter: Optional[Dict] = None,
        include_game_log: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """Return player combinations for a team sorted by the chosen stat.

        Args:
            collection_name: MongoDB collection name.
            team_id: Team identifier (FEB numeric string or FBCYL UUID-like).
            team_name: Human-readable team name.
            combination_size: Number of players per lineup (default 5).
            stat: Stat key to sort by (default ``net_rating``).
            date_filter: Optional date range filter dict.
            include_game_log: Include per-game breakdown in each lineup dict.
            progress_callback: Optional ``(current, total) -> None`` callback.

        Returns:
            List of lineup stat dicts sorted by ``stat``, or empty list on failure.
        """
        fbcyl = _is_fbcyl(collection_name)
        # Always fetch game_log internally to enable IFQ computation.
        results = self._db.get_lineup_analysis(
            collection_name, team_id, team_name,
            combination_size=combination_size,
            date_filter=date_filter,
            is_fbcyl=fbcyl,
            include_game_log=True,
            progress_callback=progress_callback,
        ) or []

        # Re-sort by requested stat (repository always sorts by net_rating)
        reverse = stat not in REVERSE_STATS
        results.sort(key=lambda x: x.get(stat) or 0, reverse=reverse)

        # Normalise field name: repository uses 'player_names', frontend expects 'players'
        for row in results:
            # Compute IFQ = mean(net_rating) / std(net_rating) across game log.
            # Returns None when std is zero or fewer than 3 appearances.
            game_log = row.get('game_log', [])
            nr_values = [g['net_rating'] for g in game_log
                         if g.get('net_rating') is not None]
            if len(nr_values) >= 3:
                arr = np.array(nr_values, dtype=float)
                std = float(np.std(arr))
                mean_nr = float(np.mean(arr))
                row['ifq'] = round(mean_nr / std, 2) if std > 0 else None
            else:
                row['ifq'] = None

            # Strip game_log if the caller did not request it.
            if not include_game_log:
                row.pop('game_log', None)

            if 'players' not in row and 'player_names' in row:
                row['players'] = row['player_names']
            # player_photo_urls is already set by the repository:
            #   FEB  → BOXSCORE.TEAM.PLAYER[].logo  (https://imagenes.feb.es/foto.aspx?c=...)
            #   FBCYL → list of None  (no reliable CDN; frontend uses initials fallback)
            if 'player_photo_urls' not in row:
                row['player_photo_urls'] = [None] * len(row.get('players') or [])

        return results
