"""Regression of #828: the starting five of a rotation analysis does not depend on the hash seed of the process.

``RotationService`` took the five most frequent starters with ``Counter.most_common(5)`` over players inserted by walking a ``set``, and listed them with
``list(set)``: when two players tie for the last place the five depended on ``PYTHONHASHSEED`` and so did the order, and a rebuild of the published ``rotations``
rewrote them with another five. The tie is broken by a fixed rule: games as a starter (desc), total minutes (desc), player id; the five come in that order.

The analysis is run in a process per seed (the seed is fixed for the life of a process) over games with a tie built like the real ones: ``4`` and ``5`` start together
in the first game and nobody else has their count.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (1, 2, 3, 4, 5, 6)

SCRIPT = r'''
import json, sys
from unittest.mock import MagicMock
sys.path.insert(0, ".")
sys.path.insert(0, "src")
sys.path.insert(0, "tests")
from services.rotation_service import RotationService
from test_rotation_service import _feb_game

MINUTES = {"1": "36:00", "2": "34:00", "3": "32:00", "4": "20:00", "5": "30:00", "6": "28:00", "7": "10:00", "8": "10:00", "9": "10:00"}


def game(starters):
    bench = [p for p in MINUTES if p not in starters]
    return _feb_game("T1", [{"id": p, "name": "Player" + p, "minutes": MINUTES[p]} for p in starters + bench])


# starters: 1, 2, 3 three times; 6 twice; 4 and 5 (a tie with 7 and 8) once, both in the first game
games = [game(["1", "2", "3", "4", "5"]), game(["1", "2", "3", "6", "7"]), game(["1", "2", "3", "6", "8"])]
db = MagicMock()
db.get_games_for_team.return_value = games
result = RotationService(db).get_rotation_analysis("FEB_X", "T1", "Team A")
print(json.dumps({k: result[k] for k in ("starting_five_ids", "starting_five_names", "pct_minutes_starting_five", "starting_five_games_count")}
                 | {"starters": sorted(p["player_id"] for p in result["players"] + result["marginal_players"] if p["is_starter"]),
                    "players": [(p["player_id"], p["is_starter"], p["starter_games"]) for p in result["players"]]}))
'''


def run(seed):
    done = subprocess.run([sys.executable, "-c", SCRIPT], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env={**__import__("os").environ, "PYTHONHASHSEED": str(seed)})
    assert done.returncode == 0, done.stderr[-800:]
    return json.loads(done.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def outputs():
    return {seed: run(seed) for seed in SEEDS}


def test_the_analysis_is_the_same_whatever_the_hash_seed(outputs):
    first = outputs[SEEDS[0]]
    assert all(outputs[seed] == first for seed in SEEDS), {seed: outputs[seed]["starting_five_ids"] for seed in SEEDS}


def test_the_tie_for_the_last_place_goes_to_more_minutes_and_the_five_come_in_the_rule_order(outputs):
    # 1, 2, 3 started 3 games, 6 started 2; of the ones with 1 game (4, 5, 7, 8) player 5 has the most minutes
    assert outputs[SEEDS[0]]["starting_five_ids"] == ["1", "2", "3", "6", "5"]
    assert outputs[SEEDS[0]]["starting_five_names"] == ["Player1", "Player2", "Player3", "Player6", "Player5"]


def test_the_starter_marks_and_counts_follow_the_same_five(outputs):
    result = outputs[SEEDS[0]]
    assert result["starters"] == ["1", "2", "3", "5", "6"]
    assert dict((p, count) for p, _, count in result["players"])["5"] == 1
