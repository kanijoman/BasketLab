"""MongoDB aggregation pipeline builder -- backward-compatible facade.

The concrete class AggregationPipelineBuilder inherits all pipeline builders
from TeamStatsPipelineMixin (team/opponent stats + shared helpers) and
PlayerStatsPipelineMixin (player stats + FBCYL timeline).
All existing call sites are unchanged.
"""

from typing import List, Dict, Optional  # noqa: F401 -- re-exported for consumers
from .basic_stats import get_shooting_percentages, get_per_game_stats, get_possessions_calculation  # noqa: F401
from .advanced_stats import get_all_advanced_stats  # noqa: F401

from .pipeline_team_stats import TeamStatsPipelineMixin
from .pipeline_player_stats import PlayerStatsPipelineMixin


class AggregationPipelineBuilder(TeamStatsPipelineMixin, PlayerStatsPipelineMixin):
    """Builds MongoDB aggregation pipeline for basketball statistics.

    Combines team stats, opponent stats, player stats and FBCYL timeline builders.
    Backwards-compatible: all existing call sites continue to work unchanged.
    """