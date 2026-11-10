"""Regression of #839: the rotation analysis of a FBCYL team knows who started and how many stints each player had.

The analysis keys a FBCYL player by what the box gives (``stats.teams[].players[]`` has no ``licenseId``: the ``uuid``), while the starting lineup and the timeline of
substitutions come from the moves and are keyed by the **licence id** (``actorId`` → ``licenseId``). The two never met: nobody was a starter (the «starting five» was the
five with most minutes) and every player had ONE stint as long as all her minutes, the fallback for a player with no substitutions. Same family as #818.
"""
import gzip
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.database.lineup_extractor import LineupExtractor
from src.database.playbyplay_analyzer import PlayByPlayAnalyzer
from src.services.rotation_service import RotationService

GAME = Path(__file__).parent / "fixtures" / "fbcyl_game_ok.json.gz"


@pytest.fixture(scope="module")
def game():
    with gzip.open(GAME, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def analysis_of(game, team_index):
    team = game["stats"]["teams"][team_index]
    db = MagicMock()
    db.get_games_for_team.return_value = [game]
    return team, RotationService(db).get_rotation_analysis("FBCYL_X", str(team["teamIdExtern"]), "Team")


def uuid_of_licence(game, analyzer):
    """``{licence id: key of the player in the analysis}``, from the box and the moves (what the test knows independently of the service)."""
    return {analyzer._fbcyl_actor_to_license[p["actorId"]]: str(p["uuid"]) for team in game["stats"]["teams"] for p in team["players"]
            if p.get("actorId") in analyzer._fbcyl_actor_to_license}


@pytest.mark.parametrize("team_index", [0, 1])
def test_the_five_who_open_the_game_are_the_starters(game, team_index):
    analyzer = PlayByPlayAnalyzer(game, is_fbcyl=True)
    team, result = analysis_of(game, team_index)
    expected = {uuid_of_licence(game, analyzer)[licence] for licence in LineupExtractor(analyzer).detect_starting_lineup(str(team["teamIdIntern"]))}
    assert len(expected) == 5
    assert set(result["starting_five_ids"]) == expected
    assert result["starting_five_games_count"] == 1                                    # the five started together in the only game
    by_player = {p["player_id"]: p for p in result["players"] + result["marginal_players"]}
    assert {pid for pid, p in by_player.items() if p["is_starter"]} == expected
    assert all(by_player[pid]["starter_games"] == 1 for pid in expected)


@pytest.mark.parametrize("team_index", [0, 1])
def test_the_stints_of_a_player_are_those_of_her_substitutions(game, team_index):
    analyzer = PlayByPlayAnalyzer(game, is_fbcyl=True)
    timeline = analyzer.parse_substitutions()
    keys = uuid_of_licence(game, analyzer)
    _, result = analysis_of(game, team_index)
    expected = {keys[licence]: sum(1 for _, on in events if on) for licence, events in timeline.items() if licence in keys}
    checked = 0
    for player in result["players"] + result["marginal_players"]:
        stints = expected.get(player["player_id"])
        if stints:
            assert player["total_pbp_stints"] == stints, player["player_id"]
            checked += 1
    assert checked >= 5
    assert any(p["total_pbp_stints"] > 1 for p in result["players"])                   # a team that substitutes has players with more than one stint
