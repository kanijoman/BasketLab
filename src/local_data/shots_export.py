"""The shots of a competition for the web (#685): one row per shot with its team and its player, so that the browser counts the zones and draws the shots.

The same shots and in the same order as the shot endpoints read them (``feb_zones.iter_shots_feb`` and ``fbcyl_zones.iter_shot_dicts_fbcyl`` over the collection in natural
order): filtering the rows by team or by player gives what ``GET /shots/{collection}/raw`` answers for that filter, which is what the parity tests check. FEB's player is the
dorsal of the shot resolved to the player id of its game (``None`` when no player has that dorsal: the shot counts for the team and the league, for no player).
"""
from __future__ import annotations

from typing import Any, Dict, List

from src.local_data.export import FORMAT
from src.shotcharts.fbcyl_zones import _SHOT_KEYS
from src.shotcharts.feb_zones import build_dorsal_to_id_map, classify_zone, feb_to_fiba
from src.utils.collection_utils import is_fbcyl

COLUMNS = ("team_id", "player_id", "x", "y", "made", "zone")


def _feb_rows(collection: Any) -> List[List[Any]]:
    rows: List[List[Any]] = []
    for doc in collection.find({"SHOTCHART.SHOTS": {"$exists": True}}, {"SHOTCHART.SHOTS": 1, "SHOTCHART.TEAM": 1, "HEADER.TEAM": 1}):
        header = [str((t or {}).get("id", "")) for t in doc.get("HEADER", {}).get("TEAM", [])]
        shotchart = doc.get("SHOTCHART", {})
        dorsals = build_dorsal_to_id_map(shotchart)
        for shot in shotchart.get("SHOTS", []):
            try:
                slot = int(shot.get("team"))
            except (TypeError, ValueError):
                continue
            if slot not in (0, 1) or slot >= len(header):
                continue
            x, y = feb_to_fiba(float(shot.get("x", 0)), float(shot.get("y", 0)), slot)
            player = dorsals.get((slot, str(shot.get("player", ""))))
            rows.append([header[slot], player or None, x, y, int(shot.get("m", 0)) == 1, classify_zone(x, y)])
    return rows


def _fbcyl_rows(collection: Any) -> List[List[Any]]:
    rows: List[List[Any]] = []
    for doc in collection.find({}, {"stats.teams": 1, "_id": 0}):
        for team in (doc.get("stats") or {}).get("teams", []):
            for player in team.get("players", []):
                data = player.get("data") or {}
                uuid = player.get("uuid")
                for key, made in _SHOT_KEYS:
                    for point in data.get(key) or []:
                        if isinstance(point, dict) and "xnormalize" in point and "ynormalize" in point:
                            x, y = feb_to_fiba(float(point["xnormalize"]), float(point["ynormalize"]), 0)       # FBCYL folds every team into one half court
                            rows.append([str(team.get("teamIdExtern", "")), None if uuid is None else str(uuid), x, y, made, classify_zone(x, y)])
    return rows


def export_shots(collection: Any, name: str) -> Dict[str, Any]:
    """The payload of one competition: its shots as rows of ``COLUMNS`` and how many games they come from."""
    fbcyl = is_fbcyl(name)
    rows = _fbcyl_rows(collection) if fbcyl else _feb_rows(collection)
    games = collection.count_documents({"stats.teams": {"$exists": True}} if fbcyl else {"SHOTCHART.SHOTS": {"$exists": True}})
    return {"format": FORMAT, "collection": name, "league": "fbcyl" if fbcyl else "feb", "games": games, "columns": list(COLUMNS), "shots": rows}
