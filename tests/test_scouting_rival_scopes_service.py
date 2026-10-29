"""The scouting service by scope (#638): the same report for the league, the cup and both, built once per team and sold as three.

The rule-based team report and the league context belong to the team's LEAGUE: the cup scope does not get them. A game against a team of another category
is marked and said in the notices of the scopes that count it. The matchup with our team is not part of what is published: it is computed in the browser
from two profiles, because it depends on a pair of teams.
"""
import copy
from unittest.mock import MagicMock

import pytest

from src.services.scouting_rival_service import ScoutingRivalService

A, B = "982047", "981204"
COLLECTION = "FEB_TEST_2026_A"


class FakeStats:
    def get_teams_with_ids(self, collection):
        return [{"id": A, "name": "EQUIPO A"}, {"id": B, "name": "EQUIPO B"}]

    def load_season_data(self, collection):
        return {"team_stats": []}


class FakeReport:
    calls = []

    def build(self, collection, team_id, mode="own"):
        FakeReport.calls.append((collection, team_id, mode))
        return {"training": [{"kind": "exploit", "text": "Atacar su rebote defensivo", "priority": 1}], "profile": ["Perfil del informe."],
                "strengths": [], "weaknesses": [], "differentials": [], "tactics": []}


class BrokenReport:
    def build(self, *args, **kwargs):
        raise RuntimeError("the rule report failed")


def dated(doc, start, code):
    out = copy.deepcopy(doc)
    out["HEADER"]["starttime"], out["_id"] = start, code
    return out


@pytest.fixture()
def league(feb_game_doc):
    return [dated(feb_game_doc, "10-10-2026 - 17:00", 9001), dated(feb_game_doc, "17-10-2026 - 17:00", 9002)]


@pytest.fixture()
def cup(feb_game_doc):
    return [dated(feb_game_doc, "14-10-2026 - 20:00", 9101)]


def _db():
    handler = MagicMock()
    handler.repository.connection.get_collection.return_value.count_documents.return_value = 3
    return handler


def service(league, cup=None, levels=None, report=None):
    FakeReport.calls = []
    return ScoutingRivalService(
        _db(), stats=FakeStats(), report_service=report or FakeReport(), games=lambda handler, collection: iter(league),
        gender_of=lambda collection: "", extra_games=lambda handler, collection, team: {"copa": iter(cup)} if cup else {},
        levels_of=lambda handler, collection: levels or {})


def test_without_other_competitions_there_is_only_the_league(league):
    reports = service(league).build_scopes(COLLECTION, A)
    assert list(reports) == ["liga"] and reports["liga"]["scope"] == "liga" and reports["liga"]["sample_games"] == 2


def test_the_league_the_cup_and_both_are_three_reports_with_their_games(league, cup):
    reports = service(league, cup).build_scopes(COLLECTION, A)
    assert {s: r["sample_games"] for s, r in reports.items()} == {"liga": 2, "copa": 1, "todo": 3}
    assert {s: r["scope"] for s, r in reports.items()} == {"liga": "liga", "copa": "copa", "todo": "todo"}
    assert [g["competition"] for g in reports["todo"]["games"]] == ["liga", "copa", "liga"]


def test_the_rule_report_is_the_leagues_and_is_built_once(league, cup):
    reports = service(league, cup).build_scopes(COLLECTION, A)
    assert FakeReport.calls == [(COLLECTION, A, "rival")]
    assert "Perfil del informe." in reports["liga"]["profile"] and "Perfil del informe." in reports["todo"]["profile"]
    assert "Perfil del informe." not in reports["copa"]["profile"]                       # the league's profile is not the cup's


def test_the_cup_scope_says_what_it_is_made_of(league, cup):
    notices = service(league, cup).build_scopes(COLLECTION, A)["copa"]["notices"]
    assert any("Copa" in n and "1" in n for n in notices)


def test_the_grouped_scope_says_how_many_games_are_against_another_category(league, cup):
    reports = service(league, cup, levels={A: 1, B: 3}).build_scopes(COLLECTION, A)           # every game of the fixture is A against B
    flagged = sum(1 for g in reports["todo"]["games"] if g["other_level"])
    assert flagged == 3 and any(f"{flagged} de estos partidos son contra rivales de otra categoría" in n for n in reports["todo"]["notices"])
    assert any("1 de estos partidos son contra rivales de otra categoría" in n for n in reports["copa"]["notices"])
    assert not any("otra categoría" in n for n in reports["liga"]["notices"])            # the league is its own category: it says nothing about it


def test_without_known_categories_nothing_is_said_about_them(league, cup):
    reports = service(league, cup).build_scopes(COLLECTION, A)
    assert not any("categoría" in n for r in reports.values() for n in r["notices"])


def test_a_failing_rule_report_does_not_stop_the_scouting_and_is_said_where_it_would_have_been_used(league, cup):
    reports = service(league, cup, report=BrokenReport()).build_scopes(COLLECTION, A)
    assert set(reports) == {"liga", "copa", "todo"}
    assert any("informe por reglas" in n for n in reports["liga"]["notices"])
    assert not any("informe por reglas" in n for n in reports["copa"]["notices"])


def test_the_matchup_is_not_part_of_what_is_published(league, cup):
    reports = service(league, cup).build_scopes(COLLECTION, A)
    assert all(r["comparison"] == [] and r["own_team"] is None for r in reports.values())


def test_every_scope_carries_the_team_and_the_collection(league, cup):
    for scope, report in service(league, cup).build_scopes(COLLECTION, B).items():
        assert report["team"]["id"] == B and report["collection"] == COLLECTION, scope


def test_an_unknown_team_is_refused_as_always(league):
    from src.services.team_report_service import TeamNotFoundError

    with pytest.raises(TeamNotFoundError):
        service(league).build_scopes(COLLECTION, "000")


def test_the_original_build_is_unchanged_by_the_scopes(league, cup):
    report = service(league, cup).build(COLLECTION, A)
    assert report["sample_games"] == 2 and "scope" not in report
