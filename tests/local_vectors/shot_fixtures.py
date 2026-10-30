"""Shots for the fixture leagues (#685): FEB's ``SHOTCHART`` and FBCYL's per-player shot coordinates.

Deterministic (the numbers come from the game's number) and added on top of the games, which no season row, player row or ``DERIVED`` reads. They have what the shot
tables meet in real data: a dorsal that no player has (a shot that counts for the team and the league but for no player), a shot of a team slot that does not exist (the
server skips it) and shots in every zone of both halves of the court.
"""
import random
from typing import Any, Dict

UNKNOWN_DORSAL = "99"


def _coordinates(rng: random.Random) -> Dict[str, float]:
    return {"x": round(rng.uniform(1, 99), 2), "y": round(rng.uniform(1, 99), 2)}


def add_feb_shots(doc: Dict[str, Any], n: int) -> None:
    """``SHOTCHART`` of FEB game ``n``: the shots (team slot and dorsal as strings, as the scraper stores them) and the dorsal -> player id map per team."""
    rng = random.Random(8100 + n)
    teams = [{"PLAYER": [{"no": f"{i:02d}", "id": p["id"]} for i, p in enumerate(team["PLAYER"])]} for team in doc["BOXSCORE"]["TEAM"]]
    shots = []
    for _ in range(24):
        slot = rng.randint(0, 1)
        dorsal = UNKNOWN_DORSAL if rng.random() < 0.08 else str(rng.randint(0, 8))
        shots.append({"team": str(slot), "player": dorsal, "m": str(rng.randint(0, 1)), **{k: str(v) for k, v in _coordinates(rng).items()}})
    shots.append({"team": "2", "player": "1", "m": "1", "x": "50", "y": "50"})              # a slot that does not exist: skipped
    shots.append({"team": None, "player": "1", "m": "0", "x": "50", "y": "50"})             # no slot at all: skipped
    doc["SHOTCHART"] = {"SHOTS": shots, "TEAM": teams}


_SHOT_KEYS = ("shootingOfTwoSuccessfulPoint", "shootingOfTwoFailedPoint", "shootingOfThreeSuccessfulPoint", "shootingOfThreeFailedPoint")


def add_fbcyl_shots(doc: Dict[str, Any], n: int) -> None:
    """The coordinates of the shots of each FBCYL player of game ``n`` (``data.shootingOf…Point``, ``xnormalize`` / ``ynormalize`` in percent of the court)."""
    rng = random.Random(8200 + n)
    for team in doc["stats"]["teams"]:
        for player in team.get("players", []):
            data = player.setdefault("data", {})
            for key in _SHOT_KEYS:
                data[key] = [{"xnormalize": c["x"], "ynormalize": c["y"]} for c in (_coordinates(rng) for _ in range(rng.randint(0, 3)))]
            if rng.random() < 0.1:
                data[_SHOT_KEYS[0]].append({"idShot": 1})                                    # a shot with no coordinates: not drawn
