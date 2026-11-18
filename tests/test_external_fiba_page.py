"""The public page of a FIBA game as data (#887, D3a): the REAL pages of six games and of an event, captured with ``scripts/capture_fiba_fixtures.py`` (``tests/fixtures/fiba``).

Two U18 EuroBasket 2025 games (the reference one is France-Austria), one U16 women's, a EuroBasket 2025 men's game, and **the EuroBasket 2025 women's Sweden-Spain, which went to overtime (``OT1``)**. The page of an event is
the real example of a page with no data of a game (the generic version the spike #915 saw). The tests check what the page says and what it must be consistent with: the official box adds up to the score, the periods add up
to the final result, and every event belongs to a player of the roster of its team.
"""
import gzip
import json
from pathlib import Path

import pytest

from src.external.fiba_page import FibaPageError, GenericPage, extract_flight, parse_game

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fiba"
GAMES = ["125809", "125803", "125812", "125859", "123004", "123043"]
OVERTIME = "123043"


def flight(name: str) -> str:
    return gzip.decompress((FIXTURES / f"{name}.flight.gz").read_bytes()).decode("utf-8")


@pytest.fixture(scope="module")
def parsed():
    return {name: parse_game(flight(name)) for name in GAMES}


class TestExtractFlight:
    def test_it_joins_and_unescapes_the_data_chunks_of_the_page(self):
        html = '<script>self.__next_f.push([1,"{\\"a\\":1,"])</script><script>self.__next_f.push([1,"\\"b\\":\\"x\\"}"])</script>'
        assert extract_flight(html) == '{"a":1,"b":"x"}'

    @pytest.mark.parametrize("html", ["", "<html><body>nothing</body></html>", None])
    def test_a_page_without_chunks_is_not_a_next_page_with_data(self, html):
        with pytest.raises(FibaPageError):
            extract_flight(html)


class TestTheGame:
    def test_the_reference_game_says_who_played_where_and_when(self, parsed):
        game = parsed["125809"]
        assert (game["game_id"], game["number"], game["status"]) == (125809, "6", "VALID")
        assert (game["start"], game["venue"], game["city"], game["country"]) == ("2025-07-28T21:00:00", "Belgrade Arena", "Belgrade", "Serbia")
        assert (game["round"], game["round_code"]) == ("Group Phase", "GP")
        assert game["competition"] == {"id": 208916, "code": "EMJM-DA", "name": "FIBA U18 EuroBasket", "season": 2025, "age_category": "Under 18", "gender": "Men"}
        home, away = game["teams"]
        assert (home["side"], home["org_id"], home["code"], home["name"], home["score"]) == ("A", 59, "FRA", "France", 95)
        assert (away["side"], away["org_id"], away["code"], away["name"], away["score"]) == ("B", 17, "AUT", "Austria", 56)
        assert [p["score"] for p in home["periods"]] == [24, 25, 24, 22] and [p["score"] for p in away["periods"]] == [18, 14, 10, 14]
        assert game["periods"] == ["Q1", "Q2", "Q3", "Q4"]

    def test_the_official_box_of_a_player_is_there_with_his_roster_data(self, parsed):
        yimga = next(p for p in parsed["125809"]["teams"][0]["players"] if p["person_id"] == 344991)
        assert (yimga["name"], yimga["number"], yimga["position"]) == ("Hugo Yimga", "1", "SF")
        stats = yimga["stats"]
        assert (stats["PTS"], stats["REB"], stats["OR"], stats["DR"], stats["AS"], stats["FG2M"], stats["FG2A"], stats["FTM"], stats["FTA"]) == (13, 10, 2, 8, 2, 6, 9, 1, 2)
        assert (stats["TP"], stats["HasPlayed"], stats["Starter"]) == ("18:45", True, False)

    def test_the_official_totals_of_a_team_include_what_the_team_itself_did(self, parsed):
        totals = parsed["125809"]["teams"][0]["totals"]
        assert (totals["PTS"], totals["AS"], totals["REB"], totals["OR"], totals["DR"], totals["TO"], totals["T_REB"], totals["T_TO"]) == (95, 25, 44, 11, 33, 13, 3, 1)

    def test_the_play_by_play_is_complete_and_grouped_by_period(self, parsed):
        game = parsed["125809"]
        assert len(game["events"]) == 598 and {e["period"] for e in game["events"]} == {"Q1", "Q2", "Q3", "Q4"}
        first, shot = game["events"][0], next(e for e in game["events"] if e["code"] == "P3" and e["made"])
        assert (first["code"], first["period"], first["clock"]) == ("STARTG", "Q1", "10:00")
        assert (shot["points"], shot["team"], shot["player"] is not None) == (3, shot["team"], True)

    def test_an_event_without_a_team_or_player_says_none_not_a_marker_of_the_page(self, parsed):
        starts = [e for e in parsed["125809"]["events"] if e["code"] in ("STARTP", "ENDP")]
        assert starts and all(e["team"] is None and e["player"] is None for e in starts)

    def test_the_events_come_in_the_order_of_the_game(self, parsed):
        game = parsed["125809"]
        keys = [(game["periods"].index(e["period"]), e["order"]) for e in game["events"]]
        assert keys == sorted(keys)

    def test_the_order_is_the_one_of_the_game_even_if_the_page_wrote_the_events_in_another(self):
        """The real pages come in order, so the same real page is written with the events of every period reversed."""
        text = flight("125809")
        at = text.index('"playByPlay":{"items":') + len('"playByPlay":')
        block, end = json.JSONDecoder().raw_decode(text[at:])
        for period in block["items"].values():
            period["items"].reverse()
        assert parse_game(text[:at] + json.dumps(block) + text[at + end:]) == parse_game(text)


class TestOvertime:
    def test_an_overtime_is_a_period_named_ot1_with_its_own_score_and_events(self, parsed):
        game = parsed[OVERTIME]
        assert game["periods"] == ["Q1", "Q2", "Q3", "Q4", "OT1"]
        assert all(len(team["periods"]) == 5 and team["periods"][4]["period"] == "OT1" for team in game["teams"])
        assert any(e["period"] == "OT1" for e in game["events"])
        assert game["competition"]["gender"] == "Women" and game["competition"]["name"] == "FIBA Women's EuroBasket"


@pytest.mark.parametrize("name", GAMES)
class TestWhatTheRealPagesAreConsistentWith:
    def test_the_box_of_the_players_adds_up_to_the_score(self, parsed, name):
        for team in parsed[name]["teams"]:
            assert sum(p["stats"]["PTS"] for p in team["players"]) == team["score"] == team["totals"]["PTS"]

    def test_the_periods_add_up_to_the_final_result(self, parsed, name):
        for team in parsed[name]["teams"]:
            assert sum(p["score"] for p in team["periods"]) == team["score"]

    def test_the_score_of_the_last_event_is_the_final_one(self, parsed, name):
        game = parsed[name]
        last = game["events"][-1]
        assert (last["score_a"], last["score_b"]) == (game["teams"][0]["score"], game["teams"][1]["score"])

    def test_every_event_belongs_to_a_player_of_the_roster_of_its_team(self, parsed, name):
        game = parsed[name]
        roster = {team["org_id"]: {p["person_id"] for p in team["players"]} for team in game["teams"]}
        for event in game["events"]:
            if event["player"] is not None:
                assert event["team"] in roster and event["player"] in roster[event["team"]], event

    def test_the_shots_of_the_play_by_play_make_the_points_of_the_score(self, parsed, name):
        game = parsed[name]
        for team in game["teams"]:
            made = sum(e["points"] for e in game["events"] if e["code"] in ("P2", "P3", "FT") and e["made"] and e["team"] == team["org_id"])
            assert made == team["score"]

    def test_the_roster_has_names_and_numbers(self, parsed, name):
        for team in parsed[name]["teams"]:
            assert team["players"] and all(p["name"].strip() and p["number"] is not None for p in team["players"])


class TestWhatIsNotAGame:
    def test_the_page_of_an_event_has_no_game_data_and_the_client_has_to_ask_again(self):
        with pytest.raises(GenericPage):
            parse_game(flight("fiba-u18-eurobasket-2025"))

    @pytest.mark.parametrize("text", ["", "{}", '{"unrelated": [1, 2, 3]}'])
    def test_text_with_no_game_in_it_is_the_same_case(self, text):
        with pytest.raises(GenericPage):
            parse_game(text)

    def test_a_game_whose_data_is_cut_is_a_format_error_not_a_silent_half_game(self):
        text = flight("125809")
        with pytest.raises(FibaPageError):
            parse_game(text[: text.index('"gameDetails":') + 40])

    def test_a_generic_page_is_a_fibapageerror_too_so_one_handler_catches_both(self):
        assert issubclass(GenericPage, FibaPageError)


def test_parsing_twice_gives_the_same_and_does_not_depend_on_what_was_parsed_before():
    first = parse_game(flight("125809"))
    parse_game(flight("123043"))
    assert parse_game(flight("125809")) == first
