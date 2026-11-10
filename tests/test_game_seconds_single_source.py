"""The length of a game (2400 s) is written once: ``live_core.clock.GAME_SECONDS`` (issue #452, block 1 and its follow-up).

The literal was repeated in ten modules of the engine, in the PBP analyzer, the lineups and the season figures; a rate «per 40» that did not follow the constant
was one more place to fix. The modules of the live engine (``live_core``) are the ones the tablet runs: they change with the release of the app, so their literals are
listed here until then and the list can only shrink.
"""
import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
LENGTH = 2400
# Waiting for the Friday release of the app (the live engine is bundled with it); the checkpoints of the canary are minutes of a replay, not the length.
ALLOWED = {"live_core/boxscore.py", "live_core/lineups.py", "live_prep/canary.py"}


def literals():
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC).as_posix()
        if relative == "live_core/clock.py" or relative.startswith("api/"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig", errors="replace"))):
            if isinstance(node, ast.Constant) and not isinstance(node.value, bool) and isinstance(node.value, (int, float)) and node.value == LENGTH:
                yield relative, node.lineno


def test_no_module_writes_the_length_of_a_game_but_the_ones_waiting_for_the_release():
    found = [f"{path}:{line}" for path, line in literals() if path not in ALLOWED]
    assert not found, f"use live_core.clock.GAME_SECONDS instead of the literal {LENGTH}: {found}"


def test_every_module_of_the_waiting_list_still_has_the_literal():
    still = {path for path, _ in literals()}
    assert ALLOWED <= still, f"remove from ALLOWED: {sorted(ALLOWED - still)}"
