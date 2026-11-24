"""Helpers of the tests of the Euroleague source (#1038, D6a): the real answers of its public API of ``tests/fixtures/euroleague`` served as the site serves them."""
import gzip
import json
from pathlib import Path
from typing import Any, Dict

from ncaa_helpers import Clock, Site  # noqa: F401  (the same fake time and fake site: they know nothing of ESPN)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "euroleague"


def fixture(name: str) -> Dict[str, Any]:
    return json.loads(gzip.decompress((FIXTURES / f"{name}.json.gz").read_bytes()))


def text(name: str) -> str:
    return json.dumps(fixture(name))


def listed(season_file: str, game_code: int) -> Dict[str, Any]:
    """The line of the calendar of a game, as ``euroleague_page.parse_games`` reads it."""
    from src.external.euroleague_page import parse_games

    return next(g for g in parse_games(fixture(season_file)) if g["game_code"] == game_code)


def read_game(name: str, season_file: str, game_code: int) -> Dict[str, Any]:
    """A whole game as ``euroleague_page.parse_game`` reads the three answers of the fixtures ``<name>.stats``, ``.pbp`` and ``.points``."""
    from src.external.euroleague_page import parse_game

    return parse_game(listed(season_file, game_code), fixture(f"{name}.stats"), fixture(f"{name}.pbp"), fixture(f"{name}.points"))
