"""FBCYL: the +/- on court computed from the moves matches the box score's (issue #378).

The box (``inOutsList``) says the minute of each substitution (``minuteAbsolut``, whole minutes) and ``pointDiff``: the score difference AT THE
SUBSTITUTION (the ``score`` of its move), so the box +/- is exact. The analyzer used to place the substitutions at ``minuteAbsolut * 60`` and
the +/- was off by 2.5 points on average (the issue measured 2.9; exact in 2 of 23 players of the sample game). The moves have the
seconds (``Entra al campo`` / ``Sale del campo``) and, for the ties of a clock second, their order: who was on court for a move is decided
by the position of the move between the player's substitutions.
"""
import json
from pathlib import Path

import pytest

from src.database.inout_calculator import InOutStatsCalculator
from src.pbp.playbyplay_core import PlayByPlayAnalyzer

SAMPLE = Path(__file__).resolve().parents[1] / "src/JSON_samples/fbcyl_game.json"


def _number_long(d):
    return int(d["$numberLong"]) if "$numberLong" in d else d


@pytest.fixture(scope="module")
def game():
    return json.loads(SAMPLE.read_text(encoding="utf-8"), object_hook=_number_long)


def box_plus_minus(player, final_diff):
    """Sum of ``pointDiff(OUT) - pointDiff(IN)`` per stay; a player who ends on court counts up to the final score, a starter from 0."""
    events, total, start = player["inOutsList"], 0, None
    if events and events[0]["type"] == "OUT_TYPE":
        start = 0
    for e in events:
        if e["type"] == "IN_TYPE":
            start = e["pointDiff"]
        elif start is not None:
            total, start = total + e["pointDiff"] - start, None
    return total + (final_diff - start if start is not None else 0)


def players_with_box(game):
    stats = game["stats"]
    last = stats["score"][-1]
    for team in stats["teams"]:
        final = (last["local"] - last["visit"]) * (1 if team["teamIdIntern"] == stats["localId"] else -1)
        for p in team["players"]:
            if isinstance(p["actorId"], int) and p.get("inOutsList"):
                yield team, p, final


def test_the_plus_minus_on_court_matches_the_box_of_every_player_regression(game):
    """Before #378: 2 of the 23 players exact, mean error 2.5 points (whole-minute substitutions)."""
    analyzer = PlayByPlayAnalyzer(game, is_fbcyl=True)
    calc = InOutStatsCalculator(analyzer)
    wrong = []
    for team, p, final in players_with_box(game):
        license_id = analyzer._fbcyl_actor_to_license[p["actorId"]]
        on = calc.calculate_in_out_stats(license_id, str(team["teamIdIntern"]))["in"]
        if on["points_for"] - on["points_against"] != box_plus_minus(p, final):
            wrong.append((p["name"], on["points_for"] - on["points_against"], box_plus_minus(p, final)))
    assert wrong == []


def test_the_substitutions_have_the_seconds_of_the_moves_not_the_whole_minute(game):
    """MARIA GONZALEZ GARCIA enters in the 1st period with 4:35 left (elapsed 5:25 = 325 s; the box says minute 6 = 360 s) and leaves with 2:05."""
    analyzer = PlayByPlayAnalyzer(game, is_fbcyl=True)
    license_id = analyzer._fbcyl_actor_to_license[607091]
    first = analyzer.get_player_court_segments(license_id)[0]
    assert first == (325, 475)


def test_a_game_without_substitution_moves_keeps_using_the_box_minutes():
    """The old fixtures (and a feed that lacks the moves) still give a timeline: the box's ``inOutsList``."""
    game = {"moves": [], "stats": {"teams": [{"teamIdIntern": 1, "players": [
        {"actorId": 7, "inOutsList": [{"type": "IN_TYPE", "minuteAbsolut": 5, "pointDiff": 0}, {"type": "OUT_TYPE", "minuteAbsolut": 9, "pointDiff": 3}]}]},
        {"teamIdIntern": 2, "players": []}]}}
    assert PlayByPlayAnalyzer(game, is_fbcyl=True).get_player_court_segments("7") == [(300, 540)]
