"""The shots of a competition for the web (#685): one row per shot with its team and its player, so that the browser counts the zones and draws the shots.

The same shots and in the same order as the shot endpoints read them (``feb_zones.iter_shots_feb`` and ``fbcyl_zones.iter_shot_dicts_fbcyl`` over the collection in natural
order): filtering the rows by team or by player gives what ``GET /shots/{collection}/raw`` answers for that filter, which is what the parity tests check. FEB's player is the
dorsal of the shot resolved to the player id of its game (``None`` when no player has that dorsal: the shot counts for the team and the league, for no player).
"""
from __future__ import annotations

from typing import Any, Dict

from src.local_data.payload_format import FORMAT
from src.shotcharts.owned_shots import iter_owned_shots
from src.utils.collection_utils import is_fbcyl

COLUMNS = ("team_id", "player_id", "x", "y", "made", "zone")


def export_shots(collection: Any, name: str) -> Dict[str, Any]:
    """The payload of one competition: its shots as rows of ``COLUMNS`` and how many games they come from."""
    fbcyl = is_fbcyl(name)
    rows = [list(row) for row in iter_owned_shots(collection, fbcyl)]
    games = collection.count_documents({"stats.teams": {"$exists": True}} if fbcyl else {"SHOTCHART.SHOTS": {"$exists": True}})
    return {"format": FORMAT, "collection": name, "league": "fbcyl" if fbcyl else "feb", "games": games, "columns": list(COLUMNS), "shots": rows}
