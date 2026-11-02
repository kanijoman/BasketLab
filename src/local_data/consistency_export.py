"""The per-game variability of every player of a competition, for the web (#709).

``GET /players/{collection}/consistency`` gives, for each player and each stat (26 in FEB, 18 in FBCYL), the mean, the standard deviation, the coefficient of variation and the number of
games over the games he played (three at least). It takes no filter, so the answer is computed once at publication with the endpoint's own service function and the browser reads it:
its per-game figures come out of the per-game pipelines of each league (the shares of the team among them), not out of what the rows of the contract hold.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from src.local_data.export import FORMAT
from src.utils.collection_utils import is_fbcyl


def export_consistency(handler: Any, name: str) -> Dict[str, Any]:
    """``{player id: {stat: {mean, std, cv, n}}}`` as the endpoint answers it (``{}`` when it cannot: no games, or an unreachable database)."""
    from src.services.player_stats_service import PlayerStatsService

    players = PlayerStatsService(handler).get_consistency(name)
    return {"format": FORMAT, "collection": name, "league": "fbcyl" if is_fbcyl(name) else "feb", "players": json.loads(json.dumps(players, default=str))}
