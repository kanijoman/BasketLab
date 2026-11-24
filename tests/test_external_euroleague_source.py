"""The Euroleague source (#1038, D6a): what the daily refresh of the external sources registers for ``euroleague``.

For each competition of the catalogue (the EuroLeague, the EuroCup or the U18 Next Generation Tournament, and a season) it reads the calendar, takes the PLAYED games the archive does not have yet and asks for each
(three requests) to hand over the canonical document. A game that has been played never changes, so what is in ``known`` is not asked again. The client is a fake that serves the REAL answers of
``tests/fixtures/euroleague``: the games it has the three answers of (a EuroLeague one, one with an overtime, a EuroCup one and a U18 one) and a 404 for the rest of the calendar.
"""
import pytest

from euroleague_helpers import fixture, listed, read_game

from src.external import registry
from src.external.euroleague_client import EuroleagueBudgetExhausted, EuroleagueFetchError, EuroleagueNotFound
from src.external.euroleague_page import EuroleaguePageError, parse_games, parse_seasons
from src.external.euroleague_source import EuroleagueSource
from src.market.canonical import validate_game

CALENDARS = {"E2025": "games_E2025", "E2026": "games_E2026", "U2025": "games_U2025", "JTA25": "games_JTA25"}
GAMES = {("E2025", 1): ("E2025_1", "games_E2025"), ("E2025", 397): ("E2025_397", "games_E2025"), ("U2025", 195): ("U2025_195", "games_U2025"), ("JTA25", 9): ("JTA25_9", "games_JTA25")}


class FakeClient:
    """The API as the tests have it: calendars of four seasons, the games above whole and a 404 for any other played game."""

    def __init__(self, budget=None, broken=None, missing=()):
        self.budget, self.broken, self.missing, self.requests = budget, broken, set(missing), []

    def _spend(self, what):
        if self.budget is not None and len(self.requests) >= self.budget:
            raise EuroleagueBudgetExhausted("spent")
        self.requests.append(what)

    def seasons(self, competition):
        self._spend(("seasons", competition))
        return parse_seasons(fixture("seasons_J")) if competition == "J" else parse_seasons(fixture("seasons_E"))

    def games(self, competition, season):
        self._spend(("games", season))
        if season not in CALENDARS:
            raise EuroleagueNotFound(season)
        return parse_games(fixture(CALENDARS[season]))

    def game(self, competition, line):
        key = (line["season_code"], line["game_code"])
        self._spend(("game", *key))
        if key in self.missing or key not in GAMES:
            raise EuroleagueNotFound(str(key))
        if self.broken:
            raise self.broken
        return read_game(GAMES[key][0], GAMES[key][1], line["game_code"])


def entry(code="E", season="2025", name=None):
    names = {"E": "EuroLeague", "U": "EuroCup", "J": "U18 Next Generation"}
    return {"competition": name or names[code], "season_label": f"{season}/{int(season) + 1}", "season_value": season, "league": "euroleague", "division": names[code], "gender": "M",
            "euroleague": {"competition": code}}


def ids(docs):
    return [d["_id"] for d in docs]


class TestWhichGamesCome:
    def test_the_played_games_with_their_answers_come_as_canonical_documents(self):
        docs = list(EuroleagueSource(FakeClient()).fetch(entry(), None, frozenset()))
        assert sorted(ids(docs)) == ["euroleague:E2025_1", "euroleague:E2025_397"]
        assert all(validate_game(d, "M") == [] and d["_league"] == "euroleague" and d["_season"] == "2025" for d in docs)

    def test_the_games_the_archive_already_has_are_not_asked_for_again(self):
        client = FakeClient()
        docs = list(EuroleagueSource(client).fetch(entry(), None, frozenset({"euroleague:E2025_1"})))
        assert ids(docs) == ["euroleague:E2025_397"] and ("game", "E2025", 1) not in client.requests

    def test_a_game_not_played_yet_is_not_asked_for(self):
        client = FakeClient()
        list(EuroleagueSource(client).fetch(entry(season="2026"), None, frozenset()))
        assert ("game", "E2026", 379) not in client.requests and {r[2] for r in client.requests if r[0] == "game"} == {129, 128}          # the two played ones, not the pending

    def test_the_date_it_is_given_does_not_matter_a_played_game_never_changes(self):
        a = ids(EuroleagueSource(FakeClient()).fetch(entry(), None, frozenset()))
        b = ids(EuroleagueSource(FakeClient()).fetch(entry(), "2026-05-01", frozenset()))
        assert a == b

    def test_the_eurocup_reads_its_own_competition(self):
        docs = list(EuroleagueSource(FakeClient()).fetch(entry("U"), None, frozenset()))
        assert ids(docs) == ["euroleague:U2025_195"] and docs[0]["HEADER"]["competition"] == "EuroCup"

    def test_the_u18_tournaments_of_a_season_are_all_read_each_with_its_own_calendar(self):
        client = FakeClient()
        docs = list(EuroleagueSource(client).fetch(entry("J"), None, frozenset()))
        assert "euroleague:JTA25_9" in ids(docs) and {r[1] for r in client.requests if r[0] == "games"} == {"JTA25", "JTBO25", "JTU25", "JTF425", "JTB25"}

    def test_the_games_of_two_tournaments_with_the_same_code_are_two_documents(self):
        """The game code of a tournament starts again at 1: the id carries the season code of the tournament."""
        a, b = ({"season_code": "JTA25", "game_code": 1}, {"season_code": "JTB25", "game_code": 1})
        assert EuroleagueSource.game_id(a) != EuroleagueSource.game_id(b) and EuroleagueSource.game_id(a) == "euroleague:JTA25_1"


class TestWhenThingsGoWrong:
    def test_when_the_budget_is_spent_it_stops_keeps_what_it_had_and_says_the_run_is_not_complete_once(self):
        client = FakeClient(budget=3)                              # the calendar and one game
        s = EuroleagueSource(client)
        found = list(s.fetch(entry(), None, frozenset())) + list(s.fetch(entry("U"), None, frozenset())) + list(s.fetch(entry("J"), None, frozenset()))
        assert len(found) == 1 and s.complete is False and [n for n in s.notes if n.startswith("budget")] == ["budget: spent"]

    def test_a_game_that_is_not_there_is_said_and_the_others_still_come(self):
        s = EuroleagueSource(FakeClient(missing=[("E2025", 1)]))
        assert ids(s.fetch(entry(), None, frozenset())) == ["euroleague:E2025_397"] and any("E2025_1" in n and "not found" in n for n in s.notes) and s.complete is True

    def test_a_game_that_fails_to_be_had_is_said_and_asked_again_the_next_run(self):
        s = EuroleagueSource(FakeClient(broken=EuroleagueFetchError("HTTP 403")))
        assert list(s.fetch(entry(), None, frozenset())) == [] and any("E2025_1" in n and "403" in n for n in s.notes)

    def test_if_no_game_could_be_read_because_of_its_format_the_run_fails_instead_of_a_quiet_empty_archive(self):
        s = EuroleagueSource(FakeClient(broken=EuroleaguePageError("the keys changed")))
        with pytest.raises(EuroleaguePageError):
            list(s.fetch(entry(), None, frozenset()))

    def test_a_season_the_api_does_not_have_gives_nothing_and_says_so(self):
        s = EuroleagueSource(FakeClient())
        assert list(s.fetch(entry(season="2024"), None, frozenset())) == [] and any("E2024" in n for n in s.notes)


def test_the_source_is_registered_as_euroleague_and_the_registry_accepts_it():
    from src.external import sources

    registry.SOURCES.pop("euroleague", None)
    try:
        assert type(sources.default_source("euroleague", 50)).__name__ == "EuroleagueSource"
        sources.register_defaults("euroleague", 50)
        assert registry.SOURCES["euroleague"].name == "euroleague"
    finally:
        registry.SOURCES.pop("euroleague", None)
