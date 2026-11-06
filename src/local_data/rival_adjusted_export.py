"""The rival-adjusted figures of every team of a competition, for the web (#710).

``GET /teams/{collection}/rival-adjusted`` adjusts eight stats of each team for the quality of the rivals it met (leave-one-out context of the league, proportional or, for the net
rating, additive; five paired games at least). It takes no filter and pairs the two rows of a game by their crossed scoreline rather than by match id, so the answer is computed once at
publication with the endpoint's own service function and the browser reads it: about 2 KB compressed per competition.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from src.local_data.payload_format import FORMAT
from src.utils.collection_utils import is_fbcyl


def export_rival_adjusted(handler: Any, name: str) -> Dict[str, Any]:
    """``{team name: {stat: {raw_avg, adj_avg, adj, sos, n}}}`` as the endpoint answers it (``{}`` when it cannot: no games, or an unreachable database)."""
    from src.services.rival_adjusted_service import RivalAdjustedService

    teams = RivalAdjustedService(handler).get_rival_adjusted_stats(name)
    return {"format": FORMAT, "collection": name, "league": "fbcyl" if is_fbcyl(name) else "feb", "teams": json.loads(json.dumps(teams, default=str))}
