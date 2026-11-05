"""The scouting of the rival of FBCYL published in ``web-data`` (issue #635): the same sealed files per team, over the FBCYL groups where a club of interest plays.

For FEB the clubs of interest come from the catalog of the packages; FBCYL has no packages, its clubs are the ones the recorder watches (``config/fbcyl_watchlist.json``). The
rule is the same: the latest season of the groups where one of them plays, whoever the rival is (the group A-1 of UNILEON has thirteen teams, each with its own scouting).
FBCYL has no cups, so every team has only the league scope.
"""
import copy
import gzip
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from db_helpers import new_mock_db

from src.live_prep.fbcyl_adapter import to_feb_document
from src.live_prep.package_sealing import ScopedSealer
from src.local_data.contract import validate_manifest, validate_report_index
from src.local_data.scouting_export import fbcyl_interest_clubs, scouting_collections, seal_scouting
from src.local_data.web_data import publish_web_data
from src.services.scouting_rival_service import ScoutingRivalService
from tests.test_local_web_data import FBCYL, cheap_lineups, handler  # noqa: F401  (fixtures: a handler with a FEB and a FBCYL competition, cheap exporters)

RAW = json.loads(gzip.open(Path(__file__).parent / "fixtures" / "fbcyl_game_ok.json.gz").read())
A1 = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"
A2 = "FBCYL_1ª_FASE-GRUPO_A-2_2026_"
OLD = "FBCYL_1ª_FASE-GRUPO_A-1_2025_"
MASTER = "a-master-secret-for-the-tests"


def _game(code, season, teams):
    return {"_id": code, "_season": season, "stats": {"teams": [{"teamIdExtern": t} for t in teams]}}


def test_the_clubs_of_interest_of_fbcyl_are_the_teams_the_recorder_watches(tmp_path):
    path = tmp_path / "watch.json"
    path.write_text(json.dumps({"groups": ["7298"], "teams": ["39609", 41000]}), encoding="utf-8")
    assert fbcyl_interest_clubs(path) == {"39609", "41000"}
    assert fbcyl_interest_clubs(tmp_path / "missing.json") == set()                 # no file, no clubs: nothing is scouted for FBCYL
    assert "39609" in fbcyl_interest_clubs()                                       # the real one: UNILEON


def test_the_fbcyl_groups_scouted_are_those_where_a_club_of_interest_plays_in_the_latest_season():
    db = new_mock_db("fbcyl_interest")
    db[A1].insert_one(_game("a1-1", "2026", [39609, 40098]))
    db[A2].insert_one(_game("a2-1", "2026", [41111, 41112]))                         # a group without our club
    db[OLD].insert_one(_game("old-1", "2025", [39609, 40098]))                       # the same club, last season
    db["SEGUNDA_FEB_2026_2027_Liga_Regular_A"].insert_one({"_id": 2, "HEADER": {"TEAM": [{"id": "7"}]}})
    handler = SimpleNamespace(connection=SimpleNamespace(client={"BASKETBALL": db}))
    assert scouting_collections(handler, {"7"}, {"39609"}) == ["SEGUNDA_FEB_2026_2027_Liga_Regular_A", A1]
    assert scouting_collections(handler, set(), {"39609"}) == [A1]
    assert scouting_collections(handler, {"7"}) == ["SEGUNDA_FEB_2026_2027_Liga_Regular_A"]      # without FBCYL clubs the call is the one of before
    assert scouting_collections(handler, set(), {"1"}) == []


def _service(handler_unused):
    docs = [to_feb_document(copy.deepcopy(RAW)), to_feb_document(copy.deepcopy(RAW))]
    docs[0]["HEADER"]["starttime"], docs[1]["HEADER"]["starttime"] = "03-10-2026 - 18:30", "10-10-2026 - 18:30"
    docs[1]["_id"] = "second-game"
    teams = [(str(t["id"]), t["name"]) for t in docs[0]["HEADER"]["TEAM"]]

    class Stats:
        def get_teams_with_ids(self, collection):
            return [{"id": i, "name": n} for i, n in teams]

        def load_season_data(self, collection):
            return {"team_stats": []}

    class Report:
        def build(self, collection, team_id, mode="own"):
            return {"profile": [], "training": [], "strengths": [], "weaknesses": [], "differentials": [], "tactics": []}

    db = SimpleNamespace(repository=SimpleNamespace(connection=SimpleNamespace(get_collection=lambda n: SimpleNamespace(count_documents=lambda q: 2))))
    return ScoutingRivalService(db, stats=Stats(), report_service=Report(), games=lambda h, c: iter(docs), gender_of=lambda c: "F")


def test_every_team_of_a_fbcyl_group_gets_a_sealed_scouting_with_only_the_league_scope(tmp_path):
    entries = seal_scouting(object(), A1, tmp_path, ScopedSealer(MASTER, open_access=False), {}, "scouting/", service_factory=_service)
    assert len({e["team_id"] for e in entries}) == 2 and {e["scope"] for e in entries} == {"liga"} and {e["mode"] for e in entries} == {"scouting"}
    assert all(e["collection"] == A1 and e["file"].startswith("scouting/") for e in entries)
    sealed = json.loads((tmp_path / entries[0]["file"]).read_text(encoding="utf-8"))
    assert sealed                                                                   # a real envelope was written


def test_the_entry_point_scouts_the_fbcyl_groups_of_the_clubs_of_interest_by_default(handler, cheap_lineups, tmp_path, monkeypatch):  # noqa: F811
    import run_web_data
    from src.local_data import scouting_export

    sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))
    import generate_web_data as vectors

    seen = []
    real = scouting_export.scouting_collections
    monkeypatch.setenv("PACKAGE_MASTER_KEY", MASTER)
    monkeypatch.setattr(scouting_export, "interest_clubs", lambda config=None: {"101"})
    monkeypatch.setattr(scouting_export, "fbcyl_interest_clubs", lambda path=None: {"39609"})
    monkeypatch.setattr(scouting_export, "scouting_collections", lambda handler_, clubs, fbcyl_clubs=(): seen.append((set(clubs), set(fbcyl_clubs))) or real(handler_, clubs, fbcyl_clubs))
    monkeypatch.setattr(scouting_export, "_default_service", vectors.fixture_scouting_service)
    assert run_web_data.main(["--out", str(tmp_path), "--collection", "L_F_-2_2025_2026_Liga_Regular_B"]) == 0
    assert seen == [({"101"}, {"39609"})]


def test_a_fbcyl_competition_published_with_scouting_satisfies_the_contract(handler, cheap_lineups, tmp_path):  # noqa: F811
    manifest = publish_web_data(handler, tmp_path, ScopedSealer(MASTER, open_access=False), [FBCYL], scouting=[FBCYL], scouting_service=_service)
    validate_manifest(manifest)
    index = json.loads((tmp_path / manifest["reports"][0]["file"]).read_text(encoding="utf-8"))
    validate_report_index(index)
    scouting = [e for e in index["reports"] if e["mode"] == "scouting"]
    assert scouting and {e["scope"] for e in scouting} == {"liga"} and all(e["team_id"] and e["team"] for e in scouting)
