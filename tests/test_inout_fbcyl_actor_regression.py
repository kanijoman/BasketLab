"""Regression of #818: the FBCYL IN/OUT left the «with the player on court» side at zero.

The timeline of substitutions of a FBCYL game is keyed by the licence id of each player (the stable identity the lineups use), but the IN/OUT of a player
asks for the ``actorId`` of the game, which the moves and the box give: the key was not found, nobody was ever on court and the whole game went to «out».
"""
import pytest

from src.database.inout_calculator import InOutStatsCalculator
from src.database.playbyplay_analyzer import PlayByPlayAnalyzer
from tests import inout_repo_corpus as corpus


@pytest.fixture(scope="module")
def game():
    return corpus.fbcyl_game()


@pytest.fixture(scope="module")
def starter(game):
    """(actorId, licenseId, team id) of a player of the game who entered the court."""
    move = next(m for m in game["moves"] if str(m.get("move", "")).lower().startswith("entra al campo"))
    return move["actorId"], str(move["licenseId"]), move["idTeam"]


def test_the_court_segments_of_a_player_are_the_same_by_actor_id_and_by_licence_id(game, starter):
    actor, licence, _ = starter
    analyzer = PlayByPlayAnalyzer(game, is_fbcyl=True)
    assert analyzer.get_player_court_segments(licence)                      # the licence key works
    assert analyzer.get_player_court_segments(actor) == analyzer.get_player_court_segments(licence)
    assert analyzer.get_player_court_segments(str(actor)) == analyzer.get_player_court_segments(licence)
    assert analyzer.get_player_move_spans(actor) == analyzer.get_player_move_spans(licence)
    assert analyzer.calculate_time_played(actor) == analyzer.calculate_time_played(licence) > 0


def test_the_in_side_of_a_player_asked_by_actor_id_has_minutes_and_plays(game, starter):
    actor, licence, team = starter
    calculator = InOutStatsCalculator(PlayByPlayAnalyzer(game, is_fbcyl=True))
    by_actor, by_licence = calculator.calculate_in_out_stats(actor, str(team)), calculator.calculate_in_out_stats(licence, str(team))
    assert by_actor["in"]["minutes"] > 0
    assert by_actor == by_licence
    assert by_actor["in"]["fga_2"] + by_actor["in"]["fga_3"] > 0              # shots of the team while the player was on court


def test_the_repository_gives_the_in_side_of_every_player_who_played(game):
    played = [p for p in corpus.fbcyl_players(game) if (p.get("timePlayed") or 0) > 0]
    assert played
    for player in played:
        result = corpus._run([game], corpus.FBCYL_COLLECTION, player["uuid"])["result"]
        assert result["in"]["minutes"] > 0, f"{player['name']} has no minutes on court"
        assert result["in"]["minutes"] + result["out"]["minutes"] == pytest.approx(40)
