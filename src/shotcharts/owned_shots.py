"""Every shot of a competition with its team and its player, in one pass over the games (issues #685, #760).

The rows are the ones ``local_data.shots_export`` publishes for the web (it uses this module), so the server and the browser count the same shots: ``(team_id, player_id | None, x, y,
made, zone)``. FEB's player is the dorsal of the shot resolved to the player id of its game (``None`` when no player has that dorsal: the shot counts for the team and the league,
for no player); FBCYL's is the ``uuid``. Games are read one at a time.
"""
from __future__ import annotations

from typing import Any, Iterator, Optional, Tuple

from src.shotcharts.fbcyl_zones import _SHOT_KEYS
from src.shotcharts.feb_zones import build_dorsal_to_id_map, classify_zone, feb_to_fiba

OwnedShot = Tuple[str, Optional[str], float, float, bool, str]


def iter_owned_shots_feb(collection: Any) -> Iterator[OwnedShot]:
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
            yield header[slot], player or None, x, y, int(shot.get("m", 0)) == 1, classify_zone(x, y)


def iter_owned_shots_fbcyl(collection: Any) -> Iterator[OwnedShot]:
    for doc in collection.find({}, {"stats.teams": 1, "_id": 0}):
        for team in (doc.get("stats") or {}).get("teams", []):
            for player in team.get("players", []):
                data = player.get("data") or {}
                uuid = player.get("uuid")
                for key, made in _SHOT_KEYS:
                    for point in data.get(key) or []:
                        if isinstance(point, dict) and "xnormalize" in point and "ynormalize" in point:
                            x, y = feb_to_fiba(float(point["xnormalize"]), float(point["ynormalize"]), 0)       # FBCYL folds every team into one half court
                            yield str(team.get("teamIdExtern", "")), None if uuid is None else str(uuid), x, y, made, classify_zone(x, y)


def iter_owned_shots(collection: Any, fbcyl: bool) -> Iterator[OwnedShot]:
    return iter_owned_shots_fbcyl(collection) if fbcyl else iter_owned_shots_feb(collection)
