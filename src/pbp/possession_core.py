"""Shared possession reconstruction core used by multiple consumers.

Public facade: the implementation lives in ``possession_moves`` (ordering), ``possession_classify``,
``possession_quality`` (per-team quality counts) and ``possession_engine`` (the state machine).
"""
from __future__ import annotations

from typing import Dict, List

from .possession_engine import _PossessionExtractionEngine
from .possession_classify import is_controversial_possession
from .possession_moves import order_possession_moves
from .possession_quality import QUALITY_METRICS, count_quality_pbp_metrics, previous_missed_shot_index

__all__ = [
    "QUALITY_METRICS", "count_quality_pbp_metrics", "extract_possession_rows", "is_controversial_possession",
    "is_tab_evaluated_possession", "order_possession_moves", "previous_missed_shot_index",
]


_ZERO_DURATION_VALID_ENDINGS = frozenset(("violacion", "recuperacion"))


def is_tab_evaluated_possession(row: Dict) -> bool:
    """Return True if the possessions tab includes this row in its OER/pace stats.

    Mirrors PossessionAnalyzer's state machine: drops ownership-correction artifacts
    (otro + 0pts) and possessions with an implausible duration, unless they scored or
    ended in a way that is inherently duration-independent (violación/recuperación).
    """
    duration = int(row.get("Duracion_posesion") or 0)
    points = int(row.get("Puntos_obtenidos") or 0)
    ending_type = str(row.get("Tipo_finalizacion") or "")
    if ending_type == "otro" and points == 0:
        return False
    if 0 < duration <= 90:
        return True
    return duration == 0 and (points > 0 or ending_type in _ZERO_DURATION_VALID_ENDINGS)


def extract_possession_rows(
    game_data: Dict,
    is_fbcyl: bool,
    game_id: str,
    team_info: Dict[str, Dict],
) -> List[Dict]:
    """Return canonical possession rows used by exporter and analyzer."""
    engine = _PossessionExtractionEngine(game_data, is_fbcyl, game_id, team_info)
    return engine.run()
