"""The rival scouting service (issue #299): the engine data, the rule-based team report and the matchup, for ANY team."""

import copy
from unittest.mock import MagicMock

import pytest

from src.services.scouting_rival_service import ScoutingRivalService
from src.services.team_report_service import TeamNotFoundError

A, B = "982047", "981204"        # the two teams of the sample game; the service must work for either as the scouted team
COLLECTION = "FEB_TEST_2025_A"


class FakeStats:
    def get_teams_with_ids(self, collection):
        return [{"id": A, "name": "EQUIPO A"}, {"id": B, "name": "EQUIPO B"}]

    def load_season_data(self, collection):
        return {"team_stats": [
            {"team_id": A, "points_per_game": 70.0, "turnovers_per_game": 12.0, "net_rating": 2.0},
            {"team_id": B, "points_per_game": 66.0, "turnovers_per_game": 15.0, "net_rating": -2.0}]}


class FakeReport:
    calls = []

    def build(self, collection, team_id, mode="own"):
        FakeReport.calls.append((collection, team_id, mode))
        return {"training": [{"kind": "exploit", "text": "Atacar su rebote defensivo", "priority": 1}], "profile": ["Perfil del informe."],
                "strengths": [], "weaknesses": [], "differentials": [], "tactics": []}


class BrokenReport:
    def build(self, *args, **kwargs):
        raise RuntimeError("the rule report failed")


@pytest.fixture()
def docs(feb_game_doc):
    first, second = copy.deepcopy(feb_game_doc), copy.deepcopy(feb_game_doc)
    first["HEADER"]["starttime"], second["HEADER"]["starttime"] = "10-10-2026 - 17:00", "17-10-2026 - 17:00"
    return [first, second]


@pytest.fixture()
def db():
    handler = MagicMock()
    handler.repository.connection.get_collection.return_value.count_documents.return_value = 2
    return handler


def service(db, docs, report=None):
    FakeReport.calls = []
    return ScoutingRivalService(db, stats=FakeStats(), report_service=report or FakeReport(), games=lambda handler, collection: iter(docs))


def test_the_report_of_the_chosen_team(db, docs):
    report = service(db, docs).build(COLLECTION, A)
    assert report["team"]["id"] == A and report["sample_games"] == 2
    assert report["collection"] == COLLECTION and report["own_team"] is None and report["comparison"] == []
    assert report["keys"] is not None and "Perfil del informe." in report["profile"]
    assert FakeReport.calls == [(COLLECTION, A, "rival")]


def test_any_team_of_the_collection_can_be_scouted(db, docs):
    assert service(db, docs).build(COLLECTION, B)["team"]["id"] == B


def test_with_our_team_it_adds_the_matchup(db, docs):
    report = service(db, docs).build(COLLECTION, B, own_team_id=A)
    assert report["own_team"] == {"id": A, "name": "EQUIPO A"}
    by_key = {c["key"]: c for c in report["comparison"]}
    assert by_key["points_per_game"]["advantage"] == "own" and by_key["turnovers_per_game"]["advantage"] == "own"


def test_progress_counts_games_over_the_total_of_the_collection(db, docs):
    seen = []
    service(db, docs).build(COLLECTION, A, progress=lambda done, total: seen.append((done, total)))
    assert seen and seen[-1] == (2, 2)


def test_a_team_that_is_not_in_the_collection(db, docs):
    with pytest.raises(TeamNotFoundError):
        service(db, docs).build(COLLECTION, "000")
    with pytest.raises(TeamNotFoundError):
        service(db, docs).build(COLLECTION, A, own_team_id="000")


def test_scouting_a_team_against_itself_makes_no_sense(db, docs):
    with pytest.raises(ValueError, match="distintos"):
        service(db, docs).build(COLLECTION, A, own_team_id=A)


def test_fbcyl_is_not_supported_yet(db, docs):
    with pytest.raises(ValueError, match="FEB"):
        service(db, docs).build("FBCYL_1A_FASE_GRUPO_A_2025", A)


def test_a_failing_rule_report_does_not_stop_the_scouting(db, docs):
    report = service(db, docs, BrokenReport()).build(COLLECTION, A)
    assert report["team"]["id"] == A
    assert any("informe por reglas" in n for n in report["notices"])


# ---------------------------------------------------------------- the play-by-play figures in the matchup (#358)

def test_the_matchup_includes_the_pbp_figures_of_both_teams(db, docs):
    rows = {r["team_id"]: {"pts_second_chance_per_game": value} for r, value in ((({"team_id": A}), 12.0), (({"team_id": B}), 8.0))}
    rival_service = ScoutingRivalService(db, stats=FakeStats(), report_service=FakeReport(), games=lambda handler, collection: iter(docs),
                                         pbp=lambda collection: [{"team_id": t, **v} for t, v in rows.items()])

    comparison = {c["key"]: c for c in rival_service.build(COLLECTION, B, own_team_id=A)["comparison"]}

    assert comparison["pts_second_chance_per_game"]["own"] == 12.0 and comparison["pts_second_chance_per_game"]["rival"] == 8.0
    assert comparison["pts_second_chance_per_game"]["advantage"] == "own"


def test_a_failure_loading_the_pbp_figures_leaves_the_matchup_as_it_was(db, docs):
    def boom(collection):
        raise RuntimeError("db")

    rival_service = ScoutingRivalService(db, stats=FakeStats(), report_service=FakeReport(), games=lambda handler, collection: iter(docs), pbp=boom)
    comparison = rival_service.build(COLLECTION, B, own_team_id=A)["comparison"]

    assert {c["key"] for c in comparison} >= {"points_per_game", "turnovers_per_game"}
