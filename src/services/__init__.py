"""Services package — business logic layer between UI/API and the database layer.

Provides clean, framework-agnostic services that can be consumed by:
  - The PyQt6 desktop UI (current)
  - A FastAPI REST layer (planned)

Usage
-----
::

    from database import MongoDBHandler
    from services import TeamStatsService, PlayerStatsService

    handler = MongoDBHandler()
    svc = TeamStatsService(handler)
    data = svc.load_season_data("FEB_LF2_2025_A")
"""

from .team_stats_service import TeamStatsService
from .player_stats_service import PlayerStatsService
from .lineup_service import LineupService
from .collection_service import CollectionService

__all__ = [
    "TeamStatsService",
    "PlayerStatsService",
    "LineupService",
    "CollectionService",
]
