"""The parity vectors of the evolution of ONE team on the device (#708) are kept honest: any change in ``EvolutionService.get_team_evolution`` or in its pipelines shows up as a diff.

``python tests/local_vectors/generate.py`` regenerates ``team_evolution_feb.json`` and ``team_evolution_fbcyl.json``; the web (``frontend/src/localdata/evolution.test.ts``) must answer every case
from the rows of the contract.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import generate  # noqa: E402

LEAGUES = [("feb", "TEAM_EVOLUTION_OUT", "build_team_evolution_vectors"), ("fbcyl", "TEAM_EVOLUTION_FBCYL_OUT", "build_fbcyl_team_evolution_vectors")]


@pytest.mark.parametrize("kind, path, build", LEAGUES)
def test_the_stored_team_evolution_vectors_are_the_current_reference(kind, path, build):
    stored = json.loads(getattr(generate, path).read_text(encoding="utf-8"))
    assert json.loads(json.dumps(getattr(generate, build)(), sort_keys=True)) == stored


@pytest.mark.parametrize("kind, path, build", LEAGUES)
def test_the_team_evolution_vectors_cover_what_the_browser_has_to_get_right(kind, path, build):
    cases = json.loads(getattr(generate, path).read_text(encoding="utf-8"))["cases"]
    assert {c["window"] for c in cases} == {2, 5, 15} and len({c["team_id"] for c in cases}) >= 4
    points = [p for c in cases for p in c["points"]]
    assert all(set(p) == {"game_number", "game_date", "opponent", "value", "rolling_avg", "cumulative_avg", "won"} for p in points)
    assert {p["won"] for p in points} == {True, False} and all(p["opponent"] for p in points)


def test_won_in_fbcyl_is_the_comparison_of_the_scores_because_its_documents_carry_no_is_winner_regression():
    """Bug it prevents: ``_evolution_fbcyl`` read ``stats.teams.isWinner``, a field real FBCYL documents do not have (it is ``None`` in all of them), so every game of every team came out
    as not won. A game is won by the team with more points, the way the rows of the contract say it."""
    vectors = json.loads(generate.TEAM_EVOLUTION_FBCYL_OUT.read_text(encoding="utf-8"))["cases"]
    rows = json.loads((Path(generate.__file__).parent / "team_stats_fbcyl.json").read_text(encoding="utf-8"))["rows"]
    checked = 0
    for case in (c for c in vectors if c["stat"] == "points" and c["window"] == 5):
        games = [r for r in rows if str(r["team_id"]) == case["team_id"]]
        assert sorted(p["won"] for p in case["points"]) == sorted(r["points"] > r["opponent_points"] for r in games)
        checked += len(games)
    assert checked > 0
