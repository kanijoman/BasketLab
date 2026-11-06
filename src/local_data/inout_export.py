"""The IN/OUT analysis of every player of a competition, for the web (#678, #711).

``GET /players/{collection}/inout/{player_id}`` plays every game of the competition for the player it is asked about (about a second each); it takes no filter, so the answer
is computed once at publication, for each player of the page's list, with the endpoint's own function: the figures cannot differ. A player is known by the id the analysis looks
for: FEB's ``player_id``, FBCYL's ``uuid`` (the ``player_uuid`` of the rows, completed over the season). FBCYL's table lists a player by the ``actorId`` of one game, which changes
from game to game, so the page asks with ``player_uuid`` (#711) and that is what is published.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from src.database.aggregation import AggregationPipelineBuilder
from src.local_data.export import _rows, fbcyl_player_rows
from src.local_data.payload_format import FORMAT
from src.utils.collection_utils import is_fbcyl


def export_inout(handler: Any, name: str) -> Dict[str, Any]:
    """``{player_id, analysis}`` of every player of ``name`` in the order of the player rows (``player_id`` is the uuid in FBCYL); ``analysis`` is ``{}`` for a player the endpoint cannot analyse."""
    from src.services.inout_service import inout_analysis

    fbcyl = is_fbcyl(name)
    players, seen = [], set()
    collection = handler.connection.client["BASKETBALL"][name]
    rows = fbcyl_player_rows(collection) if fbcyl else _rows(collection, AggregationPipelineBuilder.build_season_player_rows_pipeline())
    key = "player_uuid" if fbcyl else "player_id"
    for row in rows:
        player_id = str(row.get(key))
        if row.get(key) is None or player_id in seen:
            continue
        seen.add(player_id)
        analysis = inout_analysis(handler, name, player_id) or {}
        players.append({"player_id": player_id, "analysis": json.loads(json.dumps(analysis, default=str))})
    return {"format": FORMAT, "collection": name, "league": "fbcyl" if fbcyl else "feb", "players": players}
