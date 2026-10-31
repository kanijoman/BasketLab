"""The IN/OUT analysis of every player of a FEB competition, for the web (#678).

``GET /players/{collection}/inout/{player_id}`` plays every game of the competition for the player it is asked about (about a second each); it takes no filter, so the answer
is computed once at publication, for each player of the page's list, with the endpoint's own function: the figures cannot differ. FBCYL is left to the API: its table
lists a player by the ``actorId`` of one game while the analysis looks for the ``uuid``, so what the page would ask for is not what a publication could answer.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from src.database.aggregation import AggregationPipelineBuilder
from src.local_data.export import FORMAT, _rows
from src.utils.collection_utils import is_fbcyl


def export_inout(handler: Any, name: str) -> Dict[str, Any]:
    """``{player_id, analysis}`` of every player of ``name`` (``[]`` for FBCYL), in the order of the player rows; ``analysis`` is ``{}`` for a player the endpoint cannot analyse."""
    from src.api.routers.players import get_inout_analysis

    fbcyl = is_fbcyl(name)
    players, seen = [], set()
    rows = [] if fbcyl else _rows(handler.connection.client["BASKETBALL"][name], AggregationPipelineBuilder.build_season_player_rows_pipeline())
    for row in rows:
        player_id = str(row.get("player_id"))
        if row.get("player_id") is None or player_id in seen:
            continue
        seen.add(player_id)
        analysis = get_inout_analysis(name, player_id, handler) or {}
        players.append({"player_id": player_id, "analysis": json.loads(json.dumps(analysis, default=str))})
    return {"format": FORMAT, "collection": name, "league": "fbcyl" if fbcyl else "feb", "players": players}
