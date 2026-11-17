"""Helpers of the tests of the external sources (#884): a real FEB game as the canonical document of a source."""
import copy
import json
import sys
from pathlib import Path

from src.market.canonical import source_id

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "src" / "JSON_samples" / "feb_game.json"
sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))


def unwrap(node):
    """The extended JSON of the sample (``{"$numberInt": "3"}``) as plain numbers."""
    if isinstance(node, dict):
        if len(node) == 1 and next(iter(node)) in ("$numberInt", "$numberLong"):
            return int(next(iter(node.values())))
        if len(node) == 1 and next(iter(node)) == "$oid":
            return next(iter(node.values()))
        return {k: unwrap(v) for k, v in node.items()}
    return [unwrap(v) for v in node] if isinstance(node, list) else node


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


class FixtureSource:
    """A source that hands over real FEB games badged as itself: the real sample (play-by-play and box that reconcile) and the 12 games of the fixture league (box only, so they do not reconcile)."""

    def __init__(self, name, docs=None, boom=None):
        import games

        self.name, self.boom, self.asked = name, boom, []
        sample = unwrap(json.loads(SAMPLE.read_text(encoding="utf-8")))
        self.docs = docs if docs is not None else [badged(sample, name), *[badged(g, name) for g in games.build_games()]]

    def fetch(self, entry, since):
        self.asked.append((entry["competition"], since))
        if self.boom:
            raise RuntimeError(self.boom)
        return copy.deepcopy(self.docs)
