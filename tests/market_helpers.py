"""Helpers of the tests of the external sources (#884): a real FEB game as the canonical document of a source."""
import copy

from src.market.canonical import source_id


def badged(game: dict, source: str) -> dict:
    """A real FEB game as the canonical document of ``source``: the same game with the source in ``_league`` and in every id (header, box and play-by-play)."""
    doc = copy.deepcopy(game)
    doc["_league"], doc["_id"] = source, source_id(source, game["_id"])
    for team in doc["HEADER"]["TEAM"]:
        team["id"] = source_id(source, team["id"])
    for team in doc["BOXSCORE"]["TEAM"]:
        team["id"] = source_id(source, team["id"])
        for player in team["PLAYER"]:
            player["id"] = source_id(source, player["id"])
    for line in (doc.get("PLAYBYPLAY") or {}).get("LINES") or []:
        for key in ("idTeam", "idPlayer"):
            if line.get(key) not in (None, ""):
                line[key] = source_id(source, line[key])
    return doc
