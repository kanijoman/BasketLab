"""The scouting of the rival for FBCYL (issue #635, step 2 of #627): the same service, the same report, over the games of a FBCYL collection.

The games are a REAL one (``tests/fixtures/fbcyl_game_ok.json.gz``: a clean feed of LF Castilla y León 2026/27) turned into the FEB document the engine reads by the adapter, as the
data layer does for every FBCYL game (``live_prep.eval_source``). What FBCYL changes is not the engine but the trust: its play-by-play is noted by the clubs themselves (no team
rebounds, sometimes no turnovers or steals), so every report says so. FBCYL has no cups: only the league scope exists.
"""
import copy
import gzip
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.live_core.fbcyl_adapter import to_feb_document
from src.services.scouting_rival_service import ScoutingRivalService

RAW = json.loads(gzip.open(Path(__file__).parent / "fixtures" / "fbcyl_game_ok.json.gz").read())
COLLECTION = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"
EXPERIMENTAL = "experimental"


@pytest.fixture()
def docs():
    first, second = to_feb_document(copy.deepcopy(RAW)), to_feb_document(copy.deepcopy(RAW))
    first["HEADER"]["starttime"], second["HEADER"]["starttime"] = "03-10-2026 - 18:30", "10-10-2026 - 18:30"
    second["_id"] = "second-game"
    return [first, second]


@pytest.fixture()
def teams(docs):
    return [(str(t["id"]), t["name"]) for t in docs[0]["HEADER"]["TEAM"]]


class FakeStats:
    def __init__(self, teams):
        self._teams = teams

    def get_teams_with_ids(self, collection):
        return [{"id": i, "name": n} for i, n in self._teams]

    def load_season_data(self, collection):
        return {"team_stats": [{"team_id": i, "points_per_game": 70.0 - k * 4, "turnovers_per_game": 12.0 + k * 3, "net_rating": 2.0 - k * 4} for k, (i, _) in enumerate(self._teams)]}


class FakeReport:
    def build(self, collection, team_id, mode="own"):
        return {"training": [], "profile": ["Perfil del informe."], "strengths": [], "weaknesses": [], "differentials": [], "tactics": []}


def service(docs, teams, **kwargs):
    db = MagicMock()
    db.repository.connection.get_collection.return_value.count_documents.return_value = len(docs)
    return db, ScoutingRivalService(db, stats=FakeStats(teams), report_service=FakeReport(), games=lambda handler, collection: iter(docs), gender_of=lambda c: "F", **kwargs)


def test_the_report_of_a_fbcyl_team_with_the_note_of_the_experimental_play_by_play(docs, teams):
    (rival, name), _ = teams
    _, svc = service(docs, teams)
    report = svc.build(COLLECTION, rival)
    assert report["team"]["id"] == rival and report["sample_games"] == 2 and report["collection"] == COLLECTION and report["own_team"] is None
    assert any(EXPERIMENTAL in notice.lower() for notice in report["notices"]), report["notices"]


def test_with_our_team_it_adds_the_matchup_for_fbcyl_too(docs, teams):
    (rival, _), (own, own_name) = teams
    _, svc = service(docs, teams)
    report = svc.build(COLLECTION, rival, own_team_id=own)
    assert report["own_team"] == {"id": own, "name": own_name} and report["comparison"]


def test_the_scouting_of_a_fbcyl_team_has_only_the_league_scope_and_asks_for_no_cups(docs, teams):
    (rival, _), _ = teams

    def no_cups(*_args):
        raise AssertionError("FBCYL has no cups: nothing is asked for them")

    _, svc = service(docs, teams, extra_games=no_cups, levels_of=no_cups)
    reports = svc.build_scopes(COLLECTION, rival)
    assert list(reports) == ["liga"]
    report = reports["liga"]
    assert report["scope"] == "liga" and report["collection"] == COLLECTION and report["own_team"] is None and report["comparison"] == []
    assert any(EXPERIMENTAL in notice.lower() for notice in report["notices"]), report["notices"]


def test_a_feb_report_does_not_carry_the_note_of_the_experimental_play_by_play(feb_game_doc):
    docs = [copy.deepcopy(feb_game_doc)]
    ids = [(str(t["id"]), t["name"]) for t in docs[0]["HEADER"]["TEAM"]]
    db = MagicMock()
    db.repository.connection.get_collection.return_value.count_documents.return_value = 1
    svc = ScoutingRivalService(db, stats=FakeStats(ids), report_service=FakeReport(), games=lambda handler, collection: iter(docs), gender_of=lambda c: "")
    assert not any(EXPERIMENTAL in notice.lower() for notice in svc.build("FEB_TEST_2026_A", ids[0][0])["notices"])


def test_the_total_of_games_of_a_fbcyl_collection_counts_the_games_with_moves_not_the_feb_play_by_play(docs, teams):
    (rival, _), _ = teams
    db, svc = service(docs, teams)
    svc.build(COLLECTION, rival)
    filters = [call.args[0] for call in db.repository.connection.get_collection.return_value.count_documents.call_args_list]
    assert {"moves.0": {"$exists": True}} in filters
    assert not any("PLAYBYPLAY.LINES" in f for f in filters)


def test_an_unknown_team_is_still_not_found(docs, teams):
    from src.services.team_report_service import TeamNotFoundError

    _, svc = service(docs, teams)
    with pytest.raises(TeamNotFoundError):
        svc.build(COLLECTION, "no-such-team")
    with pytest.raises(TeamNotFoundError):
        svc.build_scopes(COLLECTION, "no-such-team")


@pytest.mark.parametrize("stored, expected", [({"_gender": "F"}, "F"), ({"_gender": "M"}, "M"), ({"_gender": "X"}, ""), ({}, ""), (None, "")])
def test_the_gender_of_a_fbcyl_collection_is_the_one_its_games_carry(stored, expected):
    """FBCYL is not in the catalog of the packages: the words of the report (#495) agree with the ``_gender`` of its documents, and the neutral if there is none."""
    from src.services.scouting_rival_service import _catalog_gender

    db = MagicMock()
    db.repository.connection.get_collection.return_value.find_one.return_value = stored
    assert _catalog_gender(db, COLLECTION) == expected
