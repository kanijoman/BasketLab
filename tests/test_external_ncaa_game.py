"""What the reader takes from a REAL game of ESPN (#888, D4): the box of each player, the teams with the conference they played in THAT day, and the play by play.

The fixtures are the games as ESPN serves them (``summary``): a normal men's game (two halves), a normal women's one (four quarters), an overtime of each, a visitor that is not Division I, and one whose
play by play came empty with a complete box (Wyoming at San Diego State). The scoreboard of a day tells which games are over and who plays them.
"""
import pytest

from ncaa_helpers import fixture

from src.external.ncaa_page import NcaaPageError, parse_scoreboard, parse_summary

MENS, WOMENS = "game_mens_401829197", "game_womens_401825641"


class TestTheScoreboardOfADay:
    def test_each_finished_game_has_its_two_teams_with_the_conference_they_play_in(self):
        games = parse_scoreboard(fixture("scoreboard_mens_20260115"))
        washington = next(g for g in games if g["game_id"] == "401829197")
        home = next(t for t in washington["teams"] if t["home"])
        assert (home["id"], home["name"], home["conference_id"]) == ("265", "Washington State Cougars", "29") and washington["finished"] is True
        assert len(games) == 49 and all(len(g["teams"]) == 2 for g in games)

    def test_a_team_that_is_not_division_i_has_no_conference_and_the_one_that_hosts_it_has_its_own(self):
        """15/11/2026, early season: 9 of the 82 games have a visitor that is not Division I (RIT at Buffalo is one)."""
        games = parse_scoreboard(fixture("scoreboard_mens_20251115"))
        buffalo = next(g for g in games if g["game_id"] == "401823428")
        assert {t["name"]: t["conference_id"] for t in buffalo["teams"]} == {"Buffalo Bulls": "14", "RIT Tigers": None}
        assert sum(1 for g in games for t in g["teams"] if t["conference_id"] is None) == 9 and all(any(t["conference_id"] for t in g["teams"]) for g in games)

    def test_a_game_that_is_not_over_is_not_finished(self):
        data = fixture("scoreboard_mens_20260115")
        data["events"][0]["status"]["type"]["name"] = "STATUS_IN_PROGRESS"
        assert parse_scoreboard(data)[0]["finished"] is False

    @pytest.mark.parametrize("bad", [{}, {"events": "x"}, [], "text"])
    def test_an_answer_that_is_not_a_scoreboard_is_an_error(self, bad):
        with pytest.raises(NcaaPageError):
            parse_scoreboard(bad)


class TestAGame:
    def test_the_two_teams_have_their_score_their_periods_and_the_conference_of_the_day(self):
        game = parse_summary(fixture(MENS))
        home, away = (next(t for t in game["teams"] if t["home"] is flag) for flag in (True, False))
        assert (home["id"], home["score"], home["periods"]) == ("265", 65, [33, 32]) and (away["id"], away["score"], away["periods"]) == ("2250", 86, [43, 43])
        assert home["conference_id"] == away["conference_id"] == "29" and home["division1"] is True
        assert game["game_id"] == "401829197" and game["date"] == "2026-01-16T03:15Z" and game["finished"] is True

    def test_a_visitor_that_is_not_division_i_has_no_conference_and_says_so(self):
        game = parse_summary(fixture("game_mens_nond1_401823428"))
        rit = next(t for t in game["teams"] if t["id"] == "178")
        buffalo = next(t for t in game["teams"] if t["id"] == "2084")
        assert (rit["conference_id"], rit["division1"]) == (None, False) and (buffalo["conference_id"], buffalo["division1"]) == ("14", True)

    def test_the_men_play_two_halves_the_women_four_quarters_and_an_overtime_is_one_more(self):
        lengths = {name: [len(t["periods"]) for t in parse_summary(fixture(name))["teams"]]
                   for name in (MENS, "game_mens_ot_401812120", WOMENS, "game_womens_ot_401827769")}
        assert lengths == {MENS: [2, 2], "game_mens_ot_401812120": [3, 3], WOMENS: [4, 4], "game_womens_ot_401827769": [5, 5]}

    def test_a_player_has_the_official_numbers_of_the_box(self):
        players = {p["id"]: p for p in parse_summary(fixture(MENS))["players"]["265"] + parse_summary(fixture(MENS))["players"]["2250"]}
        ike = players["4703396"]
        assert (ike["name"], ike["jersey"], ike["starter"], ike["dnp"]) == ("Graham Ike", "15", True, False)
        assert ike["stats"] == {"minutes": 36, "pts": 23, "fgm": 11, "fga": 15, "tpm": 0, "tpa": 0, "ftm": 1, "fta": 1, "reb": 11, "ast": 5, "tov": 2, "stl": 2, "blk": 0, "orb": 6, "drb": 5, "pf": 1}

    def test_a_player_who_did_not_play_has_no_numbers_and_is_marked(self):
        game = parse_summary(fixture(WOMENS))
        benched = [p for team in game["players"].values() for p in team if p["dnp"]]
        assert benched and all(p["stats"] is None for p in benched)

    def test_the_play_by_play_has_what_the_converter_needs(self):
        game = parse_summary(fixture(MENS))
        assert len(game["plays"]) == 458
        miss = next(p for p in game["plays"] if p["text"] == "Ace Glass misses 25-foot three point jumper")
        assert (miss["team_id"], miss["athlete_id"], miss["shooting"], miss["scoring"], miss["points_attempted"], miss["period"], miss["clock"]) == ("265", "5313054", True, False, 3, 1, "19:44")
        assert (miss["x"], miss["y"]) == (7, 17)
        team_event = next(p for p in game["plays"] if p["text"] == "Gonzaga Deadball Team Rebound.")
        assert team_event["athlete_id"] is None and team_event["team_id"] == "2250"

    def test_a_game_whose_play_by_play_came_empty_is_read_with_its_complete_box_and_no_plays(self):
        game = parse_summary(fixture("game_womens_noplays_401830444"))
        assert game["plays"] == [] and sorted(t["score"] for t in game["teams"]) == [51, 70]
        assert sum(p["stats"]["pts"] for p in game["players"]["21"] if p["stats"]) == 70

    def test_the_team_totals_keep_what_the_team_itself_did(self):
        totals = parse_summary(fixture(MENS))["totals"]["2250"]
        assert (totals["totalRebounds"], totals["teamTurnovers"], totals["totalTurnovers"]) == ("43", "0", "8")

    @pytest.mark.parametrize("bad", [{}, {"boxscore": {}}, {"boxscore": {"teams": [], "players": []}, "header": {}}, [], "text"])
    def test_an_answer_that_is_not_a_game_is_an_error(self, bad):
        with pytest.raises(NcaaPageError):
            parse_summary(bad)
