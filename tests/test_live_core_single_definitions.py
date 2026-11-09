"""One definition per thing in the engine and its preparation (issue #452, block 1: constants and small helpers).

The audit of #452 found `GAME_SECONDS = 2400` defined in ten modules and the same `_clock` / `_names` helper written in six and three, so a fix had to be made in every copy. These tests keep
them single: they read the sources (the rule is structural, not a behaviour) and fail naming the copies. The helpers have their own behaviour tests.
"""
import ast
import io
import tokenize
from collections import defaultdict
from pathlib import Path

import pytest

from src.live_core import clutch, four_factors, profiles
from src.live_core.clock import GAME_SECONDS, REGULATION_LENGTH, REGULATION_PERIODS, clock_text
from src.live_core.windows import count_text, names_of, player_name

SRC = Path(__file__).resolve().parents[1] / "src"
LIVE_CORE = SRC / "live_core"


def _trees(folder):
    for path in sorted(folder.rglob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8-sig"))


def test_the_length_of_a_game_is_defined_once_and_is_four_quarters():
    defined = [str(path.relative_to(SRC)) for path, tree in _trees(SRC) for node in tree.body
               if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "GAME_SECONDS" for t in node.targets) and isinstance(node.value, ast.Constant)]
    assert defined == [], f"GAME_SECONDS written as a number in: {defined}; import it from live_core.clock"
    assert GAME_SECONDS == REGULATION_LENGTH * REGULATION_PERIODS == 2400


def test_no_two_modules_of_the_engine_define_the_same_small_helper_with_the_same_body():
    seen = defaultdict(list)
    for path, tree in _trees(LIVE_CORE):
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and len(node.body) <= 6:
                body = [b for b in node.body if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))]       # a docstring is not code
                seen[(ast.dump(ast.Module(body=body, type_ignores=[])), ast.unparse(node.args))].append(f"{path.name}:{node.name}")
    twins = [where for where in seen.values() if len({w.split(":")[0] for w in where}) > 1 and not all(w.split(":")[1].startswith("__") for w in where)]
    assert twins == [], f"the same helper in several modules: {twins}"


@pytest.mark.parametrize("seconds, text", [(0, "0:00"), (5, "0:05"), (125, "2:05"), (600, "10:00"), (2400, "40:00")])
def test_the_clock_is_minutes_and_two_digit_seconds(seconds, text):
    assert clock_text(seconds) == text


def test_the_names_of_the_players_are_trimmed_and_by_id():
    snap = {"players": {"p1": {"name": " A. PRIMERA "}, "p2": {"name": "B. SEGUNDA"}}}
    assert names_of(snap) == {"p1": "A. PRIMERA", "p2": "B. SEGUNDA"}
    assert names_of({}) == {}


@pytest.mark.parametrize("count, text", [(0, "0 pérdidas"), (1, "1 pérdida"), (2, "2 pérdidas")])
def test_a_count_is_said_in_singular_only_for_one(count, text):
    assert count_text(count, "pérdida", "pérdidas") == text


def test_the_name_of_a_player_is_trimmed():
    assert player_name({"name": "  A. PRIMERA "}) == "A. PRIMERA"


def test_the_cost_of_a_free_throw_in_a_possession_is_one_constant_not_a_number_written_everywhere():
    """0.44 was a literal in ~60 places (the formulas of possessions, TS% and TOV%) and defined three times in the engine. A change of the convention has to be one change."""
    written = []
    for path in sorted(SRC.rglob("*.py")):
        for token in tokenize.generate_tokens(io.StringIO(path.read_text(encoding="utf-8-sig")).readline):
            if token.type == tokenize.NUMBER and token.string == "0.44":
                written.append(f"{path.relative_to(SRC).as_posix()}:{token.start[0]}")
    assert written == ["live_core/four_factors.py:22"], f"0.44 written as a number outside its definition: {written}"
    assert four_factors.FT_POSSESSION_COST == 0.44
    assert profiles.FT_POSSESSION_COST is clutch.FT_POSSESSION_COST is four_factors.FT_POSSESSION_COST
