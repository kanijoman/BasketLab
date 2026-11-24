"""What the Euroleague reader takes from the answers of its public API (#1038, D6a of epic #872), read on the REAL answers of ``tests/fixtures/euroleague``.

Three servers' worth of answers make a game: the calendar line and the box (``api-live.euroleague.net/v2``: the box carries the bio of each player) and the play by play and the shots (``live.euroleague.net``).
An answer whose shape is not the expected one is an ``EuroleaguePageError``, never an empty game.
"""
import copy

import pytest

from euroleague_helpers import fixture, listed, read_game

from src.external.euroleague_page import EuroleaguePageError, parse_game, parse_games, parse_play_by_play, parse_points, parse_seasons, parse_stats


class TestCalendar:
    def test_a_listed_game_says_who_plays_when_and_whether_it_was_played(self):
        game = listed("games_E2025", 1)
        assert (game["season_code"], game["game_code"], game["played"], game["utc_date"]) == ("E2025", 1, True, "2025-09-30T17:45:00Z")
        assert (game["home"]["code"], game["home"]["score"], game["away"]["code"], game["away"]["score"]) == ("IST", 85, "TEL", 78)
        assert game["round"] == "Round 1" and game["phase"] == "RS"

    def test_the_periods_of_an_overtime_game_include_the_extra_one(self):
        game = listed("games_E2025", 397)
        assert game["home"]["periods"] == [20, 22, 20, 18, 10] and len(game["away"]["periods"]) == 5 and sum(game["away"]["periods"]) == game["away"]["score"] == 94

    def test_a_game_not_played_yet_is_listed_as_such(self):
        pending = [g for g in parse_games(fixture("games_E2026")) if not g["played"]]
        assert len(pending) == 1 and pending[0]["home"]["score"] in (0, None)

    @pytest.mark.parametrize("broken", [None, {}, {"data": []}, {"data": [{"gameCode": 1}]}, {"data": "x"}])
    def test_an_answer_that_is_not_a_calendar_is_a_page_error_not_an_empty_season(self, broken):
        with pytest.raises(EuroleaguePageError):
            parse_games(broken)

    def test_the_seasons_of_a_competition_give_their_code_and_the_year_they_start_in(self):
        seasons = parse_seasons(fixture("seasons_J"))
        assert {"code": "JTA25", "year": 2025, "name": "U18 Tournament Abu Dhabi 2025-2026"} in seasons
        assert len([s for s in seasons if s["year"] == 2025]) == 5


class TestBox:
    def test_the_box_of_both_teams_has_each_player_with_his_bio(self):
        game = read_game("E2025_1", "games_E2025", 1)
        home, away = game["teams"]
        assert (home["code"], away["code"]) == ("IST", "TEL") and len(home["players"]) == 12 and len(away["players"]) == 12
        beaubois = next(p for p in home["players"] if p["id"] == "006590")
        assert (beaubois["name"], beaubois["birth"], beaubois["height_cm"], beaubois["nationality"], beaubois["position"]) == ("BEAUBOIS, RODRIGUE", "1988-02-24", 188, "France", "Guard")
        assert beaubois["seconds"] == 0 and beaubois["started"] is False

    def test_a_starter_has_his_minutes_in_seconds(self):
        cordinier = next(p for p in read_game("E2025_1", "games_E2025", 1)["teams"][0]["players"] if p["id"] == "009549")
        assert cordinier["started"] is True and cordinier["seconds"] == 1850 and cordinier["stats"]["points"] >= 0

    def test_the_official_total_includes_what_the_team_itself_did_and_the_own_actions_are_apart(self):
        """The rebounds of a team without player: the total of the team (40) is its players' (36) plus its own (4)."""
        home = read_game("E2025_1", "games_E2025", 1)["teams"][0]
        assert home["totals"]["totalRebounds"] == 40 and home["own"]["totalRebounds"] == 4
        assert sum(p["stats"]["totalRebounds"] for p in home["players"]) == 36

    def test_a_player_the_box_does_not_give_a_birth_for_comes_without_one(self):
        stats = copy.deepcopy(fixture("E2025_1.stats"))
        stats["local"]["players"][0]["player"]["person"]["birthDate"] = None
        game = parse_game(listed("games_E2025", 1), stats, fixture("E2025_1.pbp"), fixture("E2025_1.points"))
        assert game["teams"][0]["players"][0]["birth"] is None

    def test_a_box_without_players_is_a_page_error(self):
        with pytest.raises(EuroleaguePageError):
            parse_stats({"local": {"players": [], "total": {}, "team": {}}, "road": {"players": [], "total": {}, "team": {}}})


class TestPlayByPlay:
    def test_the_plays_come_in_order_with_their_period_the_clock_that_remains_and_the_ids_without_padding(self):
        plays = read_game("E2025_1", "games_E2025", 1)["plays"]
        assert [p["number"] for p in plays] == sorted(p["number"] for p in plays)
        shot = next(p for p in plays if p["number"] == 4)
        assert (shot["type"], shot["period"], shot["clock"], shot["team"], shot["player"], shot["dorsal"]) == ("2FGM", 1, "09:39", "IST", "014102", "88")

    def test_the_score_is_the_one_of_the_play_and_a_play_without_it_has_none(self):
        plays = {p["number"]: p for p in read_game("E2025_1", "games_E2025", 1)["plays"]}
        assert (plays[4]["score_home"], plays[4]["score_away"]) == (2, None) and plays[5]["score_home"] is None

    def test_a_play_of_the_team_has_no_player(self):
        rebound = next(p for p in read_game("E2025_1", "games_E2025", 1)["plays"] if p["number"] == 65)
        assert (rebound["type"], rebound["team"], rebound["player"]) == ("O", "TEL", None)

    def test_the_periods_of_an_overtime_game_go_on_after_the_fourth(self):
        plays = read_game("E2025_397", "games_E2025", 397)["plays"]
        assert max(p["period"] for p in plays) == 5 and {p["period"] for p in plays} == {1, 2, 3, 4, 5}
        assert next(p for p in plays if p["number"] == 674)["clock"] == "02:58"

    def test_an_answer_that_is_not_a_play_by_play_is_a_page_error(self):
        with pytest.raises(EuroleaguePageError):
            parse_play_by_play({"Live": False})


class TestShots:
    def test_every_field_goal_has_its_shot_with_the_coordinates_in_centimetres_from_the_hoop(self):
        game = read_game("E2025_1", "games_E2025", 1)
        field_goals = [p for p in game["plays"] if p["type"] in ("2FGM", "2FGA", "3FGM", "3FGA")]
        assert len(game["shots"]) == len(field_goals) == 131
        first = game["shots"][0]
        assert (first["number"], first["made"], first["points"], first["x"], first["y"], first["zone"]) == (4, True, 2, -12, -6, "A")

    def test_the_free_throws_have_no_shot(self):
        assert not any(s["type"].startswith("FT") for s in read_game("E2025_1", "games_E2025", 1)["shots"])

    def test_the_shots_of_an_answer_that_is_not_one_are_a_page_error(self):
        with pytest.raises(EuroleaguePageError):
            parse_points({"Rows": "x"})


class TestAGameAsAWhole:
    def test_the_three_answers_must_be_of_the_same_game(self):
        wrong = fixture("E2025_397.pbp")
        with pytest.raises(EuroleaguePageError):
            parse_game(listed("games_E2025", 1), fixture("E2025_1.stats"), wrong, fixture("E2025_1.points"))

    def test_a_u18_tournament_game_reads_like_a_senior_one(self):
        game = parse_game(listed("games_JTA25", 9), fixture("JTA25_9.stats"), fixture("JTA25_9.pbp"), fixture("JTA25_9.points"))
        assert game["season_code"] == "JTA25" and len(game["teams"][0]["players"]) > 5 and game["plays"]
