"""The games of a FIBA event, from the real page of the event (#887, D3b): ``tests/fixtures/fiba`` has the page of the U18 EuroBasket 2025 (56 games, all played) and that of the FIBA Basketball World Cup 2027
European Qualifiers captured on 18/11/2026, **with games still to play** (168 games: 120 finished and 48 scheduled). Which ones are finished is read from the page: ``statusCode`` ``VALID`` and the last period
``E``; a scheduled one is ``INIT`` and has no period status. Only a finished game has a play-by-play to read.
"""
import gzip
from pathlib import Path

import pytest

from src.external.fiba_page import FibaPageError, GenericPage, parse_event_games

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fiba"


def flight(name: str) -> str:
    return gzip.decompress((FIXTURES / f"{name}.flight.gz").read_bytes()).decode("utf-8")


@pytest.fixture(scope="module")
def played():
    return parse_event_games(flight("fiba-u18-eurobasket-2025"))


@pytest.fixture(scope="module")
def running():
    return parse_event_games(flight("fiba-basketball-world-cup-2027-european-qualifiers"))


def test_an_event_that_has_been_played_lists_its_games_all_finished(played):
    assert len(played) == 56 and all(g["finished"] for g in played)
    assert len({g["game_id"] for g in played}) == 56


def test_a_game_says_who_played_when_and_what_the_score_was(played):
    game = next(g for g in played if g["game_id"] == 125807)
    assert game["slug"] == "125807-ISR-BUL" and game["number"] == "1"
    assert game["start"] == "2025-07-26T21:00:00" and game["start_utc"] == "2025-07-26T19:00:00"
    assert [(t["code"], t["name"], t["org_id"]) for t in game["teams"]] == [("ISR", "Israel", 82), ("BUL", "Bulgaria", 30)]
    assert game["score"] == (80, 67)


def test_the_slug_of_a_game_is_the_one_of_its_page(played):
    assert next(g for g in played if g["game_id"] == 125809)["slug"] == "125809-FRA-AUT"
    assert all(g["slug"] == f"{g['game_id']}-{g['teams'][0]['code']}-{g['teams'][1]['code']}" for g in played)


def test_the_games_come_in_the_order_they_are_played_ties_by_their_id(played):
    keys = [(g["start_utc"], g["game_id"]) for g in played]
    assert keys == sorted(keys)


def test_an_event_in_progress_tells_the_finished_games_from_the_ones_to_play(running):
    assert len(running) == 168
    assert (sum(g["finished"] for g in running), sum(not g["finished"] for g in running)) == (120, 48)


def test_a_game_to_play_has_no_score_and_a_finished_one_does(running):
    assert all(g["score"] is None for g in running if not g["finished"])
    assert all(g["score"] is not None and min(g["score"]) > 0 for g in running if g["finished"])


@pytest.mark.parametrize("text", ["", "{}", '{"unrelated": [1, 2]}'])
def test_text_with_no_games_in_it_is_the_page_with_no_data_and_the_client_asks_again(text):
    with pytest.raises(GenericPage):
        parse_event_games(text)


def test_a_list_that_is_cut_is_a_format_error_not_half_an_event():
    text = flight("fiba-u18-eurobasket-2025")
    with pytest.raises(FibaPageError):
        parse_event_games(text[: text.index('"games":[{"gameId"') + 200])


def test_the_page_of_a_game_is_not_the_page_of_an_event_and_asking_again_would_not_change_it():
    """A game's page also mentions other games, so it has to be told apart: it is a wrong address, not a page with no data."""
    with pytest.raises(FibaPageError) as error:
        parse_event_games(flight("125809"))
    assert not isinstance(error.value, GenericPage)


def test_parsing_twice_gives_the_same_list(played):
    assert parse_event_games(flight("fiba-u18-eurobasket-2025")) == played


class TestAPageThatExistsWithoutRealGames:
    """The page of ``fiba-u19-basketball-world-cup-2026`` (captured 18/11/2026) exists and lists 20 games that are only a ``gameId``: no teams, no date, no status. The U19 World Cup is played in odd years; the site
    keeps the shell of the event. Such a game is not finished and has no page to ask for, and an event that has nothing else is an event with no games yet."""

    @pytest.fixture(scope="class")
    def shell(self):
        return parse_event_games(flight("fiba-u19-basketball-world-cup-2026"))

    def test_the_games_are_listed_but_have_no_teams_no_slug_and_are_not_finished(self, shell):
        assert len(shell) == 20 and all(g["teams"] == [] and g["slug"] is None and g["finished"] is False and g["score"] is None for g in shell)
        assert len({g["game_id"] for g in shell}) == 20

    def test_the_order_is_stable_when_nothing_has_a_date(self, shell):
        assert [g["game_id"] for g in shell] == sorted(g["game_id"] for g in shell)

    def test_none_of_them_is_a_game_to_ask_for(self, shell):
        assert [g for g in shell if g["finished"] and g["slug"]] == []
