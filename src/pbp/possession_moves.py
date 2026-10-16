"""Move ordering and access shared by the possession modules (FEB and FBCYL)."""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

from .event_helpers import (
    get_timestamp,
)


_NEUTRAL = frozenset(("subst", "foul", "timeout", "assist"))


def order_possession_moves(moves: List[Dict], is_fbcyl: bool) -> List[Dict]:
    """Return deterministic chronological order for possession reconstruction."""

    def _sort_key(move: Dict) -> Tuple[int, int, int]:
        ts = get_timestamp(move, is_fbcyl)
        event_number = int(move.get("num") or 0) if not is_fbcyl else 0
        ft_points = 0
        if not is_fbcyl:
            text = str(move.get("text") or "")
            if "TIRO DE 1" in text.upper() or "TIRO LIBRE" in text.upper():
                match = re.search(r"Puntos:\s*(\d+)", text)
                if match:
                    ft_points = int(match.group(1))
        return ts, event_number, ft_points

    return sorted(moves, key=_sort_key)


def _get_moves(game_data: Dict, is_fbcyl: bool) -> List[Dict]:
    if is_fbcyl:
        return game_data.get("moves", [])
    return game_data.get("PLAYBYPLAY", {}).get("LINES", [])
