"""``LineupExtractor.get_lineup_at_timestamp`` is deterministic when more than 5 players have a court segment open at the sampling instant (issue #539).

The segments are inclusive, so at a substitution the player who leaves (his segment ends there) and the one who enters (his starts there) are both «on court»: 6 players.
The extractor kept ``set(list(on_court)[:5])``, whose order depends on the hash seed of the process, so the minutes and points of a lineup on the web changed from one
restart of the server to the next (found chasing a test that failed in 1 % of the runs: PYTHONHASHSEED 242, 412, 435, 456…).
"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from src.database.lineup_extractor import LineupExtractor


ROOT = Path(__file__).resolve().parents[1]


class FakeAnalyzer:
    is_fbcyl = False
    game_data = {}

    def __init__(self, segments):
        self._segments = segments

    def parse_substitutions(self):
        return []

    def get_player_court_segments(self, player_id):
        return self._segments[player_id]


def extractor(segments):
    ex = LineupExtractor(FakeAnalyzer(segments))
    ex._get_team_players = lambda team_id: set(segments)
    return ex


# five players from the start; at second 100 one of them leaves and another enters (both «on court» at second 100)
SUBSTITUTION = {"p1": [(0, 300)], "p2": [(0, 300)], "p3": [(0, 300)], "p4": [(0, 300)], "p5": [(0, 100)], "p6": [(100, 300)]}


def test_with_six_players_on_court_the_five_that_were_already_there_stay():
    assert extractor(SUBSTITUTION).get_lineup_at_timestamp("T", 100) == {"p1", "p2", "p3", "p4", "p5"}


def test_before_and_after_the_substitution_the_lineup_is_the_obvious_one():
    ex = extractor(SUBSTITUTION)
    assert ex.get_lineup_at_timestamp("T", 95) == {"p1", "p2", "p3", "p4", "p5"}
    assert ex.get_lineup_at_timestamp("T", 105) == {"p1", "p2", "p3", "p4", "p6"}


def test_a_tie_is_broken_by_the_id_not_by_the_hash_of_the_process_regression():
    """Ten players with the same start: any five would do, but it must be the same five in every process."""
    tied = {f"p{i:02d}": [(0, 300)] for i in range(10)}
    assert extractor(tied).get_lineup_at_timestamp("T", 50) == {f"p{i:02d}" for i in range(5)}


def test_the_same_answer_in_processes_with_different_hash_seeds():
    code = textwrap.dedent("""
        from tests.test_lineup_extractor_deterministic import extractor
        tied = {f"player-{i}": [(0, 300)] for i in range(12)}
        print(sorted(extractor(tied).get_lineup_at_timestamp("T", 50)))
    """)
    answers = set()
    for seed in ("1", "2", "3", "242", "412"):
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": os.pathsep.join([str(ROOT), str(ROOT / "src")])})
        assert out.returncode == 0, out.stderr[-400:]
        answers.add(out.stdout.strip())
    assert len(answers) == 1
