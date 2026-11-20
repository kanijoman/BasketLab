"""The pages of a game of ACB as data (#886, D2d of epic #872): the box score (``estadisticas``) and the play by play (``jugadas``) of the match centre, read from the REAL pages of ``tests/fixtures/acb``.

The game is Real Madrid 89 - Unicaja 87 (27/09/2026, game 105383); the play by play of a game of 2019/20 (18665) proves the format is the same four seasons back. What the two pages say is cross-checked with
itself: the points of the players add up to the totals of the team, the totals of the quarters add up to the total of the game, and the last play says the final score.
"""
import gzip
from pathlib import Path

import pytest

from src.external.acb_page import AcbPageError, CutPage, parse_box, parse_game, parse_plays

FIX = Path(__file__).parent / "fixtures" / "acb"


def flight(name: str) -> str:
    return gzip.decompress((FIX / f"{name}.flight.gz").read_bytes()).decode("utf-8")


BOX, PLAYS = flight("105383.estadisticas"), flight("105383.jugadas")


@pytest.fixture(scope="module")
def game():
    return parse_game(BOX, PLAYS)


class TestTheGame:
    def test_it_says_who_played_where_and_when_it_was_played(self, game):
        assert game["match_id"] == 105383 and game["finished"] is True
        assert (game["home"]["team"]["name"], game["away"]["team"]["name"]) == ("Real Madrid", "Unicaja")
        assert (game["home"]["team"]["club_id"], game["away"]["team"]["club_id"]) == (9, 14)
        assert game["arena"] == "Movistar Arena" and game["attendance"] == 8123 and len(game["referees"]) == 3

    def test_each_team_has_its_coach_and_its_players(self, game):
        assert game["home"]["coach"] == "Pedro Martínez" and len(game["home"]["assistants"]) == 3
        for side in ("home", "away"):
            players = game[side]["players"]
            assert len(players) >= 10 and sum(1 for p in players if p["started"]) == 5
            assert all(p["id"] and p["name"] and p["number"] is not None for p in players)

    def test_a_player_has_his_minutes_in_seconds_his_role_and_his_totals(self, game):
        luwawu = next(p for p in game["home"]["players"] if p["id"] == 30003351)
        assert luwawu["seconds"] == 23 * 60 + 56 and luwawu["role"] == "Alero" and luwawu["started"] is True
        assert (luwawu["totals"]["points"], luwawu["totals"]["twoPointersMade"], luwawu["totals"]["threePointersAttempted"]) == (14, 4, 6)

    def test_the_points_of_the_players_add_up_to_the_totals_of_the_team_and_to_the_final_score(self, game):
        for side, score in (("home", 89), ("away", 87)):
            team = game[side]
            assert sum(p["totals"]["points"] for p in team["players"]) == team["totals"]["points"] == score
            assert team["totals"]["twoPointersMade"] * 2 + team["totals"]["threePointersMade"] * 3 + team["totals"]["freeThrowsMade"] == score

    def test_the_four_quarters_add_up_to_the_game(self, game):
        for side in ("home", "away"):
            periods = game[side]["periods"]
            assert sorted(periods) == [1, 2, 3, 4]
            assert sum(periods[q]["points"] for q in periods) == game[side]["totals"]["points"]
            for player in game[side]["players"]:
                assert sum(player["periods"].get(q, {}).get("points", 0) for q in (1, 2, 3, 4)) == player["totals"]["points"]


class TestThePlayByPlay:
    def test_it_is_in_the_order_of_the_game_and_says_the_final_score(self, game):
        plays = game["plays"]
        assert len(plays) == 691 and [p["order"] for p in plays] == sorted(p["order"] for p in plays)
        assert (plays[-1]["score_home"], plays[-1]["score_away"]) == (89, 87)
        assert {p["period"] for p in plays} == {1, 2, 3, 4}

    def test_a_play_has_its_type_its_clock_its_team_and_its_player(self, game):
        play = next(p for p in game["plays"] if p["player_name"] == "Amine Noua" and p["type"] == 98)
        assert (play["home"], play["player_id"]) == (False, 30001137) and play["team_id"] == game["away"]["team"]["id"] and play["period"] in (1, 2, 3, 4)
        assert 0 <= play["minute"] <= 10 and 0 <= play["second"] < 60

    def test_the_score_never_goes_back_and_it_moves_by_the_points_of_the_play(self, game):
        home = away = 0
        for p in game["plays"]:
            if p["score_home"] is None:
                continue
            assert p["score_home"] >= home and p["score_away"] >= away and (p["score_home"] - home) + (p["score_away"] - away) <= 3
            home, away = p["score_home"], p["score_away"]

    def test_the_home_flag_is_the_one_of_the_team_that_plays(self, game):
        for p in game["plays"]:
            if p["team_id"] is not None:
                assert p["home"] == (p["team_id"] == game["home"]["team"]["id"])

    def test_the_game_of_2019_20_has_the_same_format(self):
        plays = parse_plays(flight("18665.jugadas"))
        assert len(plays) == 535 and plays[0]["order"] < plays[-1]["order"] and {p["period"] for p in plays} >= {1, 2, 3, 4}
        assert plays[-1]["score_home"] is not None and plays[-1]["score_away"] is not None


class TestWhatTheReaderRefuses:
    def test_a_page_without_its_data_is_cut_and_a_page_in_another_format_is_a_format_error(self):
        with pytest.raises(CutPage):
            parse_box("{}")
        with pytest.raises(CutPage):
            parse_plays("{}")
        with pytest.raises(AcbPageError, match="format"):
            parse_box('{"initialStatistics":{"matchFinished":true,"teamBoxscores":[]}}')
        with pytest.raises(AcbPageError, match="format"):
            parse_plays('"plays":[{"unexpected":1}]')

    def test_the_two_pages_of_different_games_are_not_mixed(self):
        with pytest.raises(AcbPageError, match="same game"):
            parse_game(BOX, flight("18665.jugadas"))
