"""The NCAA source (#888, D4): what the daily refresh of the external sources registers for ``ncaa``.

For each competition of the catalogue (a conference, a season and a sex) it reads the scoreboards of the days of the season, takes the finished games THAT BELONG to its conference, asks for each
one and hands over the canonical document. A game between two conferences is stored ONCE, in the competition of the HOME team (the away team's when the home one is not Division I): the decision of
23/11/2026. The game is kept complete, with its Division I teams and its other ones flagged.

The client is a fake that serves the REAL answers of ``tests/fixtures/ncaa`` (the scoreboards cut to the games the fixtures have the summary of, and an empty day anywhere else).
"""
from datetime import date

import pytest

from ncaa_helpers import fixture

from src.external import registry
from src.external.ncaa_client import NcaaBudgetExhausted, NcaaFetchError, NcaaNotFound
from src.external.ncaa_page import NcaaPageError, parse_scoreboard, parse_summary
from src.external.ncaa_source import NcaaSource
from src.market.canonical import validate_game

GAMES = {"M": {"20260115": ["game_mens_401829197", "game_mens_ot_401812120"], "20251115": ["game_mens_nond1_401823428"]},
         "F": {"20260115": ["game_womens_401825641", "game_womens_ot_401827769"]}}
BOARDS = {("M", "20260115"): "scoreboard_mens_20260115", ("M", "20251115"): "scoreboard_mens_20251115", ("F", "20260115"): "scoreboard_womens_20260115"}
IDS = {name: name.rsplit("_", 1)[1] for sex in GAMES.values() for names in sex.values() for name in names}


class FakeClient:
    """ESPN as the tests have it: the scoreboards of three days (only with the games the fixtures have the summary of), empty anywhere else."""

    def __init__(self, budget=None, broken=None, missing=()):
        self.budget, self.requests, self.broken, self.missing = budget, [], broken, set(missing)

    def _spend(self, what):
        if self.budget is not None and len(self.requests) >= self.budget:
            raise NcaaBudgetExhausted("spent")
        self.requests.append(what)

    def scoreboard(self, sex, day):
        self._spend(("scoreboard", sex, day))
        key = (sex, day.replace("-", ""))
        if key not in BOARDS:
            return []
        keep = {IDS[n] for n in GAMES[sex][key[1]]}
        return [g for g in parse_scoreboard(fixture(BOARDS[key])) if g["game_id"] in keep]

    def game(self, sex, game_id):
        self._spend(("game", sex, game_id))
        if game_id in self.missing:
            raise NcaaNotFound(game_id)
        if self.broken:
            raise self.broken
        name = next(n for n, i in IDS.items() if i == game_id)
        return parse_summary(fixture(name))

    def conferences(self, sex, season):
        return [{"id": "29", "name": "West Coast Conference", "short": "WCC"}, {"id": "14", "name": "Mid-American Conference", "short": "MAC"}, {"id": "4", "name": "Big East Conference", "short": "Big East"}]


def entry(conference_id, sex="M", conference="X", season="2025"):
    return {"competition": "D1 Men" if sex == "M" else "D1 Women", "season_label": f"{season}/{int(season) + 1}", "season_value": season, "league": "ncaa", "division": "D1", "gender": sex,
            "conference": conference, "ncaa": {"conference_id": conference_id}}


def source(client=None, today=date(2026, 1, 16)):
    return NcaaSource(client or FakeClient(), today=lambda: today)


def ids(docs):
    return [d["_id"] for d in docs]


class TestWhichGamesBelongToAConference:
    def test_a_game_goes_in_the_competition_of_its_home_team(self):
        """Washington State (home) and Gonzaga are both WCC: the game is the WCC's. It is not the one of the Big East, and the one of Bryant (home) is the America East's."""
        s = source()
        assert ids(s.fetch(entry("29"), None, frozenset())) == ["ncaa:401829197"]
        assert ids(s.fetch(entry("4"), None, frozenset())) == []

    def test_the_game_of_two_conferences_is_stored_once_in_the_one_of_the_home_team(self):
        s = source()
        found = [d for conference in ("29", "14", "4", "1") for d in s.fetch(entry(conference), None, frozenset())]
        assert sorted(ids(found)) == sorted(set(ids(found))) and "ncaa:401829197" in ids(found)

    def test_when_the_home_team_is_not_division_i_the_game_is_the_one_of_the_visitor(self):
        """In the game of RIT (not Division I) at Buffalo the home team is Buffalo, MAC (14): it is the MAC's; made the other way round the visitor's conference would own it."""
        s = source(today=date(2025, 11, 16))
        assert ids(s.fetch(entry("14"), None, frozenset())) == ["ncaa:401823428"]
        board = parse_scoreboard(fixture("scoreboard_mens_20251115"))
        game = next(g for g in board if g["game_id"] == "401823428")
        swapped = {**game, "teams": [{**t, "home": not t["home"]} for t in game["teams"]]}
        assert NcaaSource.owner(swapped) == "14"                 # the visitor, because the home team is RIT, with no conference

    def test_a_game_with_no_division_i_team_belongs_to_nobody(self):
        game = {"teams": [{"home": True, "conference_id": None}, {"home": False, "conference_id": None}]}
        assert NcaaSource.owner(game) is None

    def test_the_women_read_their_own_scoreboard_and_the_men_do_not(self):
        client = FakeClient()
        found = list(NcaaSource(client, today=lambda: date(2026, 1, 16)).fetch(entry("4", "F"), "2026-01-15", frozenset()))
        assert ids(found) == ["ncaa:401825641"] and {r[1] for r in client.requests if r[0] == "scoreboard"} == {"F"}


class TestTheDocuments:
    def test_each_game_comes_as_a_canonical_document_that_validates_with_its_teams_and_conference_names(self):
        docs = list(source().fetch(entry("29"), None, frozenset()))
        assert validate_game(docs[0], "M") == [] and [t["conference"] for t in docs[0]["HEADER"]["TEAM"]] == ["West Coast Conference", "West Coast Conference"]
        assert docs[0]["_season"] == "2025" and docs[0]["HEADER"]["competition"] == "D1 Men"

    def test_the_documents_are_the_same_whatever_the_order_the_entries_run_in(self):
        a = [d for c in ("29", "14") for d in source().fetch(entry(c), None, frozenset())]
        b = [d for c in ("14", "29") for d in source().fetch(entry(c), None, frozenset())]
        assert sorted(a, key=lambda d: d["_id"]) == sorted(b, key=lambda d: d["_id"])


class TestWhatIsAskedFor:
    def test_a_game_the_archive_already_has_is_not_asked_for_again(self):
        client = FakeClient()
        assert list(NcaaSource(client, today=lambda: date(2026, 1, 16)).fetch(entry("29"), None, frozenset({"ncaa:401829197"}))) == []
        assert not [r for r in client.requests if r[0] == "game" and r[2] == "401829197"]

    def test_the_first_time_reads_the_whole_season_and_a_later_one_only_from_the_date_it_is_given(self):
        first, later = FakeClient(), FakeClient()
        list(NcaaSource(first, today=lambda: date(2025, 12, 1)).fetch(entry("29"), None, frozenset()))
        list(NcaaSource(later, today=lambda: date(2025, 12, 1)).fetch(entry("29"), "2025-11-28", frozenset()))
        days = lambda client: [r[2] for r in client.requests if r[0] == "scoreboard"]
        assert days(first)[0] == "2025-10-25" and days(first)[-1] == "2025-12-01" and days(later) == ["2025-11-28", "2025-11-29", "2025-11-30", "2025-12-01"]

    def test_the_season_ends_in_april_and_never_asks_for_a_day_that_has_not_come(self):
        client = FakeClient()
        list(NcaaSource(client, today=lambda: date(2030, 1, 1)).fetch(entry("29"), None, frozenset()))
        days = [r[2] for r in client.requests if r[0] == "scoreboard"]
        assert days[-1] == "2026-04-20"
        future = FakeClient()
        list(NcaaSource(future, today=lambda: date(2025, 11, 3)).fetch(entry("29"), None, frozenset()))
        assert [r[2] for r in future.requests if r[0] == "scoreboard"][-1] == "2025-11-03"

    def test_the_scoreboard_of_a_day_is_asked_once_for_all_the_conferences_of_the_run(self):
        client = FakeClient()
        s = NcaaSource(client, today=lambda: date(2026, 1, 16))
        for conference in ("29", "14", "4"):
            list(s.fetch(entry(conference), "2026-01-15", frozenset()))
        assert [r for r in client.requests if r[0] == "scoreboard"] == [("scoreboard", "M", "2026-01-15"), ("scoreboard", "M", "2026-01-16")]


class TestWhenThingsGoWrong:
    def test_a_game_that_is_not_there_is_said_and_the_others_still_come(self):
        s = NcaaSource(FakeClient(missing=["401829197"]), today=lambda: date(2026, 1, 16))
        list(s.fetch(entry("29"), "2026-01-15", frozenset()))
        list(s.fetch(entry("1"), "2026-01-15", frozenset()))
        assert "401829197: not found" in s.notes and s.complete is True

    def test_a_game_that_fails_to_be_had_is_said_and_asked_again_the_next_run(self):
        s = NcaaSource(FakeClient(broken=NcaaFetchError("HTTP 403")), today=lambda: date(2026, 1, 16))
        assert list(s.fetch(entry("29"), "2026-01-15", frozenset())) == [] and any("401829197" in n and "403" in n for n in s.notes)

    def test_if_no_game_could_be_read_because_of_its_format_the_run_fails_instead_of_a_quiet_empty_archive(self):
        s = NcaaSource(FakeClient(broken=NcaaPageError("the columns changed")), today=lambda: date(2026, 1, 16))
        with pytest.raises(NcaaPageError):
            list(s.fetch(entry("29"), "2026-01-15", frozenset()))

    def test_when_the_budget_is_spent_it_stops_keeps_what_it_had_and_says_the_run_is_not_complete(self):
        """The first load goes by batches: the games already read are kept, and a run that did not see everything must not advance the date the next one starts from."""
        client = FakeClient(budget=2)                           # the scoreboard of the 15th and the game: the one of the 16th is not asked for
        s = NcaaSource(client, today=lambda: date(2026, 1, 16))
        found = list(s.fetch(entry("29"), "2026-01-15", frozenset()))
        assert ids(found) == ["ncaa:401829197"] and len(client.requests) == 2 and s.complete is False and any("budget" in n for n in s.notes)

    def test_a_scoreboard_that_cannot_be_read_stops_the_run_it_is_not_an_empty_day(self):
        class Down(FakeClient):
            def scoreboard(self, sex, day):
                raise NcaaFetchError("down")

        with pytest.raises(NcaaFetchError):
            list(NcaaSource(Down(), today=lambda: date(2026, 1, 16)).fetch(entry("29"), "2026-01-15", frozenset()))


def test_the_source_is_registered_as_ncaa_and_the_registry_accepts_it():
    from src.external import sources

    registry.SOURCES.pop("ncaa", None)
    try:
        assert type(sources.default_source("ncaa", 50)).__name__ == "NcaaSource"
        sources.register_defaults("ncaa", 50)
        assert registry.SOURCES["ncaa"].name == "ncaa"
    finally:
        registry.SOURCES.pop("ncaa", None)
