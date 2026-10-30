"""A small FEB league as stored in Mongo: the games the local-data parity vectors (#327) are built from.

Deterministic variations of the committed sample game: four teams, a double round robin on 12 dates, some games with ``DERIVED`` (exact
possessions and validated rebounds / turnovers), one with an overtime period and one decided by a single point, so that both the stored
and the box-score possession paths and the home / away / won / lost / date filters have something to tell apart.
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
try:
    from shot_fixtures import add_feb_shots
except ImportError:
    from local_vectors.shot_fixtures import add_feb_shots

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "src" / "JSON_samples" / "feb_game.json"
TEAMS = [("101", "ALPHA"), ("102", "BRAVO"), ("103", "CHARLIE"), ("104", "DELTA")]
DERIVED_GAMES = {2, 5, 9}
OVERTIME_GAMES = {4}


def _unwrap(node):
    if isinstance(node, dict):
        if len(node) == 1:
            key, value = next(iter(node.items()))
            if key == "$numberInt":
                return int(value)
            if key in ("$numberDouble", "$numberLong"):
                return float(value) if key == "$numberDouble" else int(value)
        return {k: _unwrap(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_unwrap(v) for v in node]
    return node


def _total(rng: random.Random, points_hint: int) -> dict:
    p3a, p2a, p1a = rng.randint(14, 32), rng.randint(28, 52), rng.randint(8, 28)
    p3m, p2m, p1m = rng.randint(3, p3a // 2 + 2), rng.randint(10, p2a - 8), rng.randint(4, p1a)
    pts = p1m + 2 * p2m + 3 * p3m + points_hint
    return {"p1m": p1m, "p1a": p1a, "p2m": p2m, "p2a": p2a, "p3m": p3m, "p3a": p3a, "assist": rng.randint(8, 24), "bs": rng.randint(0, 7),
            "st": rng.randint(3, 12), "to": rng.randint(7, 20), "ro": rng.randint(5, 16), "rd": rng.randint(18, 32), "pts": pts}


def _players(rng: random.Random, team_id: str, name: str, game_number: int) -> list:
    """Nine players of the team with their own ids (``<team><nn>``); one did not play, one is written under another name in game 8."""
    players = []
    for i in range(9):
        minutes = 0 if i == 8 and game_number % 3 else rng.randint(240, 2300)
        p1a, p2a, p3a = rng.randint(0, 6), rng.randint(0, 9), rng.randint(0, 6)
        stat = {"p1m": rng.randint(0, p1a), "p1a": p1a, "p2m": rng.randint(0, p2a), "p2a": p2a, "p3m": rng.randint(0, p3a), "p3a": p3a,
                "assist": rng.randint(0, 7), "bs": rng.randint(0, 3), "st": rng.randint(0, 4), "to": rng.randint(0, 5), "ro": rng.randint(0, 4),
                "rd": rng.randint(0, 7), "pf": rng.randint(0, 5), "rf": rng.randint(0, 4), "pllss": rng.randint(-15, 15), "val": rng.randint(-3, 25)}
        stat["pts"] = stat["p1m"] + 2 * stat["p2m"] + 3 * stat["p3m"]
        stat["rt"] = stat["ro"] + stat["rd"]
        label = "RENAMED" if (game_number == 8 and i == 0) else name
        players.append({**{k: str(v) for k, v in stat.items()}, "min": str(minutes), "id": f"{team_id}{i:02d}", "name": f"J{i}. {label}", "no": str(i)})
    return players


def build_games() -> list:
    """The 12 games (documents) of the league, in play order; ``_id`` 9001...9012."""
    sample = _unwrap(json.loads(SAMPLE.read_text(encoding="utf-8")))
    rng = random.Random(327)
    player_rng = random.Random(328)                              # apart, so that the team figures of the vectors do not move
    games = []
    for n, (home, away) in enumerate(permutations(TEAMS, 2), start=1):
        doc = copy.deepcopy(sample)
        doc["_id"] = 9000 + n
        doc["_season"] = "2025-2026"
        doc["HEADER"]["starttime"] = f"{1 + (n * 2) % 27:02d}-{10 + n // 5}-2025 - {rng.choice(('12:30', '18:00', '20:30'))}"
        totals = [_total(rng, 0), _total(rng, 0)]
        if n == 7:                                              # decided by a single point
            totals[1]["pts"] = totals[0]["pts"] - 1
        for team, (team_id, name), total in zip(doc["BOXSCORE"]["TEAM"], (home, away), totals):
            team["id"], team["name"] = team_id, name
            team["TOTAL"].update({k: str(v) for k, v in total.items()}, id=team_id, name=name)
            team["PLAYER"] = _players(player_rng, team_id, name, n)
        for header_team, (team_id, name), total in zip(doc["HEADER"]["TEAM"], (home, away), totals):
            header_team["id"], header_team["name"], header_team["pts"] = team_id, name, str(total["pts"])
        if n in OVERTIME_GAMES:
            doc["HEADER"]["QUARTERS"]["QUARTER"].append({"n": "5", "scoreA": "7", "scoreB": "7"})
        if n in DERIVED_GAMES:
            doc["DERIVED"] = {"v": 6, "TEAM": [
                {"id": team_id, "possessions": round(60 + rng.random() * 25, 2), "orb": t["ro"] - 1, "drb": t["rd"], "tov": t["to"], "reliable": True}
                for (team_id, _), t in zip((home, away), totals)]}
            doc["DERIVED"]["v"] = enrich(doc["DERIVED"]["TEAM"], n)                  # the pbp figures of #676 on top: the rows only read what was there
        add_feb_shots(doc, n)                                                       # the shots of #685 on top: no row reads them
        games.append(doc)
    return games


def for_mongomock(pipeline: list) -> list:
    """The pipeline without its ``$dateFromString`` (mongomock does not implement it): the date filters are applied by choosing the games."""
    cleaned = []
    for stage in pipeline:
        fields = stage.get("$addFields")
        if fields and "parsedDate" in fields:
            stage = {"$addFields": {k: v for k, v in fields.items() if k != "parsedDate"}}
        cleaned.append(stage)
    return cleaned
