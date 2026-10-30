"""A small FBCYL league as stored in Mongo: the games the FBCYL local-data parity vectors (#327) are built from.

Deterministic variations of the committed FBCYL sample: four teams in a double round robin, some games with ``DERIVED`` (exact possessions),
one tied game (FBCYL keeps unfinished games, so ``tied`` is a result), players with their own oddities (a ghost, one who did not play, a uuid left out in some games) and dates written as FBCYL writes them (``Oct 4, 2025 6:00:00 PM``).
"""
import copy
import json
import random
from itertools import permutations
from pathlib import Path

try:
    from pbp_derived import enrich
except ImportError:                                           # imported as ``local_vectors.games`` (the tests) instead of from this folder
    from local_vectors.pbp_derived import enrich

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "src" / "JSON_samples" / "fbcyl_game.json"
TEAMS = [(34001, "ALFA"), (34002, "BRAVO"), (34003, "CARLOS"), (34004, "DELTA")]
DERIVED_GAMES = {2, 5, 9}
TIED_GAMES = {6}
MONTHS = ["Oct", "Nov", "Dec"]
PLAYERS = 10                                                        # per team and game; the sample game lists 12
GHOST_GAME, GHOST_PLAYER = 4, 8                                      # inscribed, "played" the whole game (timePlayed 40) and did nothing
NO_UUID_GAMES, NO_UUID_PLAYER = {2, 7}, 3                            # FBCYL leaves the uuid out of some appearances: the identity is completed from the name


def _data(rng: random.Random) -> dict:
    p1a, p2a, p3a = rng.randint(8, 24), rng.randint(24, 48), rng.randint(10, 30)
    p1m, p2m, p3m = rng.randint(3, p1a), rng.randint(8, p2a - 6), rng.randint(2, p3a // 2 + 1)
    ro, rd = rng.randint(4, 14), rng.randint(14, 30)
    return {"score": p1m + 2 * p2m + 3 * p3m, "shotsOfOneAttempted": p1a, "shotsOfOneSuccessful": p1m, "shotsOfTwoAttempted": p2a,
            "shotsOfTwoSuccessful": p2m, "shotsOfThreeAttempted": p3a, "shotsOfThreeSuccessful": p3m, "offensiveRebound": ro, "defensiveRebound": rd,
            "rebounds": ro + rd, "assists": rng.randint(5, 20), "steals": rng.randint(2, 12), "lost": rng.randint(6, 20), "block": rng.randint(0, 6),
            "faults": rng.randint(10, 25)}


def _player(rng: random.Random, template: dict, team_id: int, team_name: str, n: int, i: int, minutes: int) -> dict:
    """A player of the sample game made ours: own ids and name, a stat line that adds up and the in/out list the plus-minus is read from."""
    player = copy.deepcopy(template)
    p1a, p2a, p3a = rng.randint(0, 5), rng.randint(0, 8), rng.randint(0, 6)
    p1m, p2m, p3m = rng.randint(0, p1a), rng.randint(0, p2a), rng.randint(0, p3a)
    ro, rd = rng.randint(0, 3), rng.randint(0, 6)
    data = {"score": p1m + 2 * p2m + 3 * p3m, "valoration": rng.randint(-5, 25), "shotsOfOneAttempted": p1a, "shotsOfOneSuccessful": p1m,
            "shotsOfTwoAttempted": p2a, "shotsOfTwoSuccessful": p2m, "shotsOfThreeAttempted": p3a, "shotsOfThreeSuccessful": p3m,
            "offensiveRebound": ro, "defensiveRebound": rd, "rebounds": ro + rd, "assists": rng.randint(0, 6), "steals": rng.randint(0, 3),
            "lost": rng.randint(0, 4), "block": rng.randint(0, 2), "faults": rng.randint(0, 5), "faultReceived": rng.randint(0, 5)}
    if (n, i) == (GHOST_GAME, GHOST_PLAYER):
        data = {k: 0 for k in data}
        minutes = 40
    player["data"].update(data)
    player["periods"] = []
    diff = rng.randint(-10, 10)
    player["inOutsList"] = [{"type": "IN_TYPE" if k % 2 == 0 else "OUT_TYPE", "minuteAbsolut": 5 * k, "pointDiff": diff + rng.randint(-4, 6) * k} for k in range(rng.choice((0, 2, 4)))]
    player["timePlayed"] = minutes
    player["uuid"] = None if (n in NO_UUID_GAMES and i == NO_UUID_PLAYER) else f"{team_id}-{i:02d}"
    player["actorId"] = team_id * 100 + i
    player["name"] = f"JUGADOR{i:02d} {team_name}{i:02d} PEREZ"                  # initial + last two words: one identity per player
    return player


def _players(rng: random.Random, template: list, team_id: int, team_name: str, n: int) -> list:
    return [_player(rng, template[i % len(template)], team_id, team_name, n, i, 0 if i == PLAYERS - 1 else rng.randint(4, 38)) for i in range(PLAYERS)]


def build_games() -> list:
    """The 12 games (documents) of the league, in play order; ``_id`` is a 24-hex string like FBCYL's."""
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    rng = random.Random(329)
    player_rng = random.Random(330)                                  # apart, so that the team figures of the vectors do not move
    games = []
    for n, (home, away) in enumerate(permutations(TEAMS, 2), start=1):
        doc = copy.deepcopy(sample)
        doc["_id"] = f"{n:024x}"
        doc.pop("moves", None)
        doc["stats"].pop("moves", None)
        doc["stats"]["time"] = f"{MONTHS[(n - 1) // 4]} {1 + (n * 3) % 27}, 2025, {rng.choice((6, 7, 8))}:00:00 PM"       # as FBCYL writes it today (#681)
        data = [_data(rng), _data(rng)]
        if n in TIED_GAMES:
            data[1]["score"] = data[0]["score"]
        for team, (team_id, name), values in zip(doc["stats"]["teams"], (home, away), data):
            team["teamIdExtern"], team["name"] = team_id, name
            team["teamIdIntern"] = 1000 * n + team_id % 10             # changes per game, as FBCYL's does
            team["data"].update(values)
            team["players"] = _players(player_rng, sample["stats"]["teams"][0]["players"], team_id, name, n)
        if n in DERIVED_GAMES:
            doc["DERIVED"] = {"v": 6, "TEAM": [{"id": t["teamIdIntern"], "ext_id": t["teamIdExtern"], "possessions": round(60 + rng.random() * 25, 2), "reliable": True}
                                                for t in doc["stats"]["teams"]]}
            doc["DERIVED"]["v"] = enrich(doc["DERIVED"]["TEAM"], n)                  # the pbp figures of #676 on top: the rows only read what was there
        games.append(doc)
    return games
