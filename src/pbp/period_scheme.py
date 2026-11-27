"""The periods of a game (#1131): the canonical documents of the external sources say them in ``HEADER.PERIODS`` (NCAA men play two halves of 20 minutes); FEB and FBCYL
have none and play four quarters of ten (FBCYL's own lengths are read by its adapter)."""
from __future__ import annotations

from typing import Any, Dict

from src.live_core.clock import FEB_SCHEME, Scheme


def scheme_of(game_doc: Dict[str, Any]) -> Scheme:
    """The regulation of the game of ``game_doc``: ``HEADER.PERIODS`` (``{"regulation": n, "minutes": m}``) when it says one, else four quarters of ten."""
    periods = (game_doc.get("HEADER") or {}).get("PERIODS")
    if isinstance(periods, dict):
        try:
            regulation, minutes = int(periods["regulation"]), int(periods["minutes"])
        except (KeyError, TypeError, ValueError):
            return FEB_SCHEME
        if regulation > 0 and minutes > 0:
            return Scheme(regulation, minutes)
    return FEB_SCHEME
