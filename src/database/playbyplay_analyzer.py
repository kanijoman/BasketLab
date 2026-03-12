"""Compatibility re-export module for play-by-play analysis classes.

The three classes were split into dedicated modules for maintainability:

- database.playbyplay_core     -> PlayByPlayAnalyzer
- database.inout_calculator    -> InOutStatsCalculator
- database.possession_analyzer -> PossessionAnalyzer

All existing imports that target *this* module continue to work unchanged.
"""

from .playbyplay_core import PlayByPlayAnalyzer
from .inout_calculator import InOutStatsCalculator
from .possession_analyzer import PossessionAnalyzer

__all__ = [
    "PlayByPlayAnalyzer",
    "InOutStatsCalculator",
    "PossessionAnalyzer",
]
