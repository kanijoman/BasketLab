"""A small FBCYL league as stored in Mongo: the games the FBCYL local-data parity vectors (#327) are built from.

Deterministic variations of the committed FBCYL sample: four teams in a double round robin, some games with ``DERIVED`` (exact possessions),
one tied game (FBCYL keeps unfinished games, so ``tied`` is a result) and dates written as FBCYL writes them (``Oct 4, 2025 6:00:00 PM``).
"""
import copy
import json
import random
from itertools import permutations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "src" / "JSON_samples" / "fbcyl_game.json"
TEAMS = [(34001, "ALFA"), (34002, "BRAVO"), (34003, "CARLOS"), (34004, "DELTA")]
DERIVED_GAMES = {2, 5, 9}
TIED_GAMES = {6}
MONTHS = ["Oct", "Nov", "Dec"]


def _data(rng: random.Random) -> dict:
    p1a, p2a, p3a = rng.randint(8, 24), rng.randint(24, 48), rng.randint(10, 30)
    p1m, p2m, p3m = rng.randint(3, p1a), rng.randint(8, p2a - 6), rng.randint(2, p3a // 2 + 1)
    ro, rd = rng.randint(4, 14), rng.randint(14, 30)
    return {"score": p1m + 2 * p2m + 3 * p3m, "shotsOfOneAttempted": p1a, "shotsOfOneSuccessful": p1m, "shotsOfTwoAttempted": p2a,
            "shotsOfTwoSuccessful": p2m, "shotsOfThreeAttempted": p3a, "shotsOfThreeSuccessful": p3m, "offensiveRebound": ro, "defensiveRebound": rd,
            "rebounds": ro + rd, "assists": rng.randint(5, 20), "steals": rng.randint(2, 12), "lost": rng.randint(6, 20), "block": rng.randint(0, 6),
            "faults": rng.randint(10, 25)}


def build_games() -> list:
    """The 12 games (documents) of the league, in play order; ``_id`` is a 24-hex string like FBCYL's."""
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    rng = random.Random(329)
    games = []
    for n, (home, away) in enumerate(permutations(TEAMS, 2), start=1):
        doc = copy.deepcopy(sample)
        doc["_id"] = f"{n:024x}"
        doc.pop("moves", None)
        doc["stats"].pop("moves", None)
        doc["stats"]["time"] = f"{MONTHS[(n - 1) // 4]} {1 + (n * 3) % 27}, 2025 {rng.choice((6, 7, 8))}:00:00 PM"
        data = [_data(rng), _data(rng)]
        if n in TIED_GAMES:
            data[1]["score"] = data[0]["score"]
        for team, (team_id, name), values in zip(doc["stats"]["teams"], (home, away), data):
            team["teamIdExtern"], team["name"] = team_id, name
            team["teamIdIntern"] = 1000 * n + team_id % 10             # changes per game, as FBCYL's does
            team["data"].update(values)
            team["players"] = []
        if n in DERIVED_GAMES:
            doc["DERIVED"] = {"v": 6, "TEAM": [{"id": t["teamIdIntern"], "ext_id": t["teamIdExtern"], "possessions": round(60 + rng.random() * 25, 2), "reliable": True}
                                                for t in doc["stats"]["teams"]]}
        games.append(doc)
    return games
