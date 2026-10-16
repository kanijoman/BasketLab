"""The possession tracker on real games (#350): 16 of LF Challenge 2026-27, 24 historical ones and 6 FBCYL.

``tests/fixtures/pbp_possessions.json.gz`` holds the reduced pbp (no substitutions) of each game, the official points
and the tracker output when it was written. Invariants must hold for every game; the quality figures are a
characterization: they change only with a deliberate change of the tracker (regenerate the fixture then).
"""
import gzip
import json
import statistics
from pathlib import Path

import pytest

from src.live_core.events import parse_line
from src.live_core.events_fbcyl import parse_moves
from src.live_core.possessions import track

_FIXTURE = Path(__file__).parent / "fixtures" / "pbp_possessions.json.gz"


def _games():
    with gzip.open(_FIXTURE, "rt", encoding="utf-8") as fh:
        return json.load(fh)["games"]


GAMES = _games()
_IDS = [f"{g['group']}-{g['game']}" for g in GAMES]


def _track(game):
    if game.get("format") == "fbcyl":
        events = parse_moves(game["lines"])
    else:
        events = [e for e in (parse_line(line) for line in game["lines"]) if e is not None]
    return track(events, game["teams"])


@pytest.mark.parametrize("game", GAMES, ids=_IDS)
def test_points_of_the_possessions_add_up_to_the_official_score(game):
    possessions, quality = _track(game)

    scored = [sum(p.points for p in possessions if p.team_id == team) + quality.technical_points.get(team, 0)
              for team in game["teams"]]
    if game.get("format") == "fbcyl":      # the final score does not say which team is which: compare as a pair
        scored = sorted(scored)
    assert scored == game["points"], f"possessions {scored} vs official {game['points']}"


@pytest.mark.parametrize("game", GAMES, ids=_IDS)
def test_possessions_are_well_formed(game):
    possessions, _ = _track(game)

    assert possessions
    for p in possessions:
        assert p.team_id in game["teams"] and p.end_elapsed >= p.start_elapsed and p.points >= 0
        assert p.second_chance_points <= p.points
        assert p.counted == (p.outcome not in ("inferred", "period_end"))
        assert sum(p.points_by_player.values()) <= p.points


@pytest.mark.parametrize("game", GAMES, ids=_IDS)
def test_quality_of_each_game_does_not_change(game):
    _, quality = _track(game)
    expected = game["expected"]

    assert [quality.counted.get(t, 0) for t in game["teams"]] == expected["counted"]
    assert (quality.breaks_raw, quality.breaks, quality.repaired_rebounds, quality.inferred, quality.level) == (
        expected["breaks_raw"], expected["breaks"], expected["repaired_rebounds"], expected["inferred"], expected["level"])


def test_complete_games_alternate_and_the_levels_separate_good_from_bad_data():
    by_level = {}
    for game in GAMES:
        _, quality = _track(game)
        by_level.setdefault(quality.level, []).append(quality.difference)

    assert statistics.mean(by_level["ok"]) <= 1.6                       # complete pbp: the teams use the same possessions +-1
    assert statistics.mean(by_level["unreliable"]) > statistics.mean(by_level["ok"])
    assert {"ok", "doubtful", "unreliable"} <= set(by_level)


def test_repairing_rebounds_never_makes_the_alternation_worse():
    raw = repaired = 0
    for game in GAMES:
        _, quality = _track(game)
        raw += quality.breaks_raw
        repaired += quality.breaks

    assert repaired <= raw
