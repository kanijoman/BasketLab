"""The full scouting of the rival published in ``web-data`` (#638): one sealed file per team and scope (liga, copa, todo), next to its reports.

Scouting is rival-facing, so it is sealed like the rival report: every club of the competition and the competition itself can open it. The competitions
scouted are the ones where a club of interest plays (the club of the publisher's config and the ``clubs`` of its catalog): about twenty teams, not the
three hundred senior ones. Files are named by the hash of their content and an unchanged scouting keeps its bytes, as everything in ``web-data``.
"""
import copy
import json
from types import SimpleNamespace

import pytest
from db_helpers import new_mock_db

from src.live_prep.package_scopes import open_sealed, scope_key
from src.live_prep.package_sealing import ScopedSealer
from src.local_data.contract import validate_manifest, validate_report_index
from src.local_data.scouting_export import interest_clubs, scouting_collections, seal_scouting
from src.local_data.web_data import publish_web_data
from src.services.scouting_rival_service import ScoutingRivalService

A, B = "982047", "981204"
COLLECTION = "FEB_TEST_2026_2027_Liga_Regular_A"
MASTER = "a-master-secret-for-the-tests"


class FakeStats:
    def get_teams_with_ids(self, collection):
        return [{"id": A, "name": "EQUIPO A"}, {"id": B, "name": "EQUIPO B"}]

    def load_season_data(self, collection):
        return {"team_stats": []}


class FakeReport:
    def build(self, collection, team_id, mode="own"):
        return {"profile": ["Perfil."], "training": [], "strengths": [], "weaknesses": [], "differentials": [], "tactics": []}


def dated(doc, start, code):
    out = copy.deepcopy(doc)
    out["HEADER"]["starttime"], out["_id"] = start, code
    return out


@pytest.fixture(scope="module")
def docs(feb_game_doc):
    league = [dated(feb_game_doc, "10-10-2026 - 17:00", 9001), dated(feb_game_doc, "17-10-2026 - 17:00", 9002)]
    cup = [dated(feb_game_doc, "14-10-2026 - 20:00", 9101)]
    return league, cup


def factory(docs, with_cup=True):
    league, cup = docs

    def make(handler):
        return ScoutingRivalService(
            SimpleNamespace(repository=SimpleNamespace(connection=SimpleNamespace(get_collection=lambda n: SimpleNamespace(count_documents=lambda q: 3)))),
            stats=FakeStats(), report_service=FakeReport(), games=lambda h, c: iter(league), gender_of=lambda c: "",
            extra_games=lambda h, c, t: {"copa": iter(cup)} if with_cup else {}, levels_of=lambda h, c: {})
    return make


def _open(out, entry, scope):
    envelope = json.loads((out / entry["file"]).read_text(encoding="utf-8"))
    return json.loads(open_sealed(envelope, entry["wraps"], {scope: scope_key(MASTER, scope)}))


def test_one_sealed_file_per_team_and_scope(docs, tmp_path):
    entries = seal_scouting(object(), COLLECTION, tmp_path, ScopedSealer(MASTER, open_access=False), {}, "scouting/", service_factory=factory(docs))
    assert sorted((e["team_id"], e["scope"]) for e in entries) == sorted((t, s) for t in (A, B) for s in ("liga", "copa", "todo"))
    assert {e["mode"] for e in entries} == {"scouting"} and all(e["collection"] == COLLECTION for e in entries)
    assert all(e["file"].startswith("scouting/") and e["sha256"][:12] in e["file"] for e in entries)


def test_a_club_of_the_competition_opens_the_scouting_of_every_team_the_competition_too_and_a_stranger_no(docs, tmp_path):
    entries = seal_scouting(object(), COLLECTION, tmp_path, ScopedSealer(MASTER, open_access=False), {}, "scouting/", service_factory=factory(docs))
    entry = next(e for e in entries if e["team_id"] == A and e["scope"] == "liga")
    assert _open(tmp_path, entry, f"club:{B}")["scope"] == "liga"                     # the staff of another club scouts it
    assert _open(tmp_path, entry, f"competicion:{COLLECTION}")["team"]["id"] == A
    with pytest.raises(Exception):
        _open(tmp_path, entry, "club:555")


def test_a_team_without_cup_games_has_only_the_league_scope(docs, tmp_path):
    entries = seal_scouting(object(), COLLECTION, tmp_path, ScopedSealer(MASTER, open_access=False), {}, "scouting/", service_factory=factory(docs, with_cup=False))
    assert {e["scope"] for e in entries} == {"liga"}


def test_a_team_without_games_with_play_by_play_is_left_out_not_an_error(docs, tmp_path):
    def make(handler):
        service = factory(docs)(handler)
        original = service.build_scopes
        service.build_scopes = lambda collection, team_id, progress=None: (_ for _ in ()).throw(ValueError("no tiene partidos")) if team_id == B else original(collection, team_id)
        return service
    entries = seal_scouting(object(), COLLECTION, tmp_path, ScopedSealer(MASTER, open_access=False), {}, "scouting/", service_factory=make)
    assert {e["team_id"] for e in entries} == {A}


def test_an_unchanged_scouting_keeps_its_bytes_and_a_changed_one_gets_a_new_name_regression(docs, tmp_path):
    sealer = ScopedSealer(MASTER)
    first = seal_scouting(object(), COLLECTION, tmp_path, sealer, {}, "scouting/", service_factory=factory(docs))
    before = {p.name: p.read_bytes() for p in (tmp_path / "scouting").iterdir()}
    old = {(e["collection"], e["team_id"], e["mode"], e["scope"]): e for e in first}
    again = seal_scouting(object(), COLLECTION, tmp_path, sealer, old, "scouting/", service_factory=factory(docs))
    assert {p.name: p.read_bytes() for p in (tmp_path / "scouting").iterdir()} == before and [e["file"] for e in again] == [e["file"] for e in first]
    league, cup = docs
    changed = seal_scouting(object(), COLLECTION, tmp_path, sealer, old, "scouting/", service_factory=factory((league[:1], cup)))
    assert {e["file"] for e in changed if e["scope"] == "liga"}.isdisjoint({e["file"] for e in first if e["scope"] == "liga"})


@pytest.fixture()
def handler(monkeypatch):
    import mongomock
    import pymongo

    from src.api import deps

    monkeypatch.setattr(pymongo, "MongoClient", mongomock.MongoClient)
    deps._create_handler.cache_clear()
    handler = deps._create_handler()
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))
    import games

    handler.connection.client["BASKETBALL"]["L_F_-2_2025_2026_Liga_Regular_B"].insert_many(games.build_games())
    yield handler
    deps._create_handler.cache_clear()


def test_the_publication_with_scouting_satisfies_the_contract_and_lists_the_files_in_the_report_index(handler, docs, tmp_path):
    collection = "L_F_-2_2025_2026_Liga_Regular_B"
    manifest = publish_web_data(handler, tmp_path, ScopedSealer(MASTER, open_access=False), [collection], scouting=[collection],
                                scouting_service=factory(docs))
    validate_manifest(manifest)
    index = json.loads((tmp_path / manifest["reports"][0]["file"]).read_text(encoding="utf-8"))
    validate_report_index(index)
    assert {e["mode"] for e in index["reports"]} == {"own", "rival", "scouting"}
    assert {e["scope"] for e in index["reports"] if e["mode"] == "scouting"} == {"liga", "copa", "todo"}
    assert all("scope" not in e for e in index["reports"] if e["mode"] != "scouting")


def test_a_second_publication_changes_no_byte_and_leaves_no_orphan_scouting(handler, docs, tmp_path):
    collection = "L_F_-2_2025_2026_Liga_Regular_B"
    sealer = ScopedSealer(MASTER)
    publish_web_data(handler, tmp_path, sealer, [collection], scouting=[collection], scouting_service=factory(docs))
    before = {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    publish_web_data(handler, tmp_path, sealer, [collection], scouting=[collection], scouting_service=factory(docs))
    assert {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before
    publish_web_data(handler, tmp_path, sealer, [collection])                                    # without scouting: its files go
    assert not list((tmp_path / "scouting").glob("*.json"))


def test_the_clubs_of_interest_are_the_publishers_club_and_the_clubs_of_its_catalog():
    config = {"team_id": "1", "competitions": [{"competition": "X", "clubs": ["2", "3"]}, {"competition": "Y"}]}
    assert interest_clubs(config) == {"1", "2", "3"}


def test_the_competitions_scouted_are_those_where_a_club_of_interest_plays_in_the_latest_season():
    db = new_mock_db("interest")
    db["PRIMERA_FEB_2026_2027_Liga_Regular_Unico"].insert_one({"_id": 1, "HEADER": {"TEAM": [{"id": "1"}, {"id": "9"}]}})
    db["SEGUNDA_FEB_2026_2027_Liga_Regular_A"].insert_one({"_id": 2, "HEADER": {"TEAM": [{"id": "7"}, {"id": "8"}]}})
    db["PRIMERA_FEB_2025_2026_Liga_Regular_Unico"].insert_one({"_id": 3, "HEADER": {"TEAM": [{"id": "1"}, {"id": "9"}]}})
    db["COPA_ESPANA_2026_2027_FASE_DE_GRUPOS_A"].insert_one({"_id": 4, "HEADER": {"TEAM": [{"id": "1"}, {"id": "9"}]}})
    handler = SimpleNamespace(connection=SimpleNamespace(client={"BASKETBALL": db}))
    assert scouting_collections(handler, {"1"}) == ["PRIMERA_FEB_2026_2027_Liga_Regular_Unico"]   # not last season's, not the cup, not a league without our clubs


def _cli(monkeypatch, handler, out, *args, clubs=frozenset({"101"})):
    import sys
    from pathlib import Path

    import run_web_data
    from src.local_data import scouting_export

    sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))
    import generate_web_data as vectors

    monkeypatch.setenv("PACKAGE_MASTER_KEY", MASTER)
    monkeypatch.setattr(scouting_export, "interest_clubs", lambda config=None: set(clubs))                 # by default a club of the fixture league
    monkeypatch.setattr(scouting_export, "_default_service", vectors.fixture_scouting_service)          # mongomock cannot sort the real games by date
    assert run_web_data.main(["--out", str(out), "--collection", "L_F_-2_2025_2026_Liga_Regular_B", *args]) == 0
    manifest = json.loads((out / "index.json").read_text(encoding="utf-8"))
    index = json.loads((out / manifest["reports"][0]["file"]).read_text(encoding="utf-8"))
    return {e["mode"] for e in index["reports"]}


def test_the_entry_point_scouts_the_competitions_of_the_clubs_of_interest_by_default(handler, tmp_path, monkeypatch):
    assert "scouting" in _cli(monkeypatch, handler, tmp_path / "default")


def test_the_entry_point_can_leave_the_scouting_out(handler, tmp_path, monkeypatch):
    assert "scouting" not in _cli(monkeypatch, handler, tmp_path / "none", "--no-scouting")


def test_the_entry_point_scouts_the_collections_it_is_told_to_even_if_no_club_of_interest_plays_there(handler, tmp_path, monkeypatch):
    assert "scouting" not in _cli(monkeypatch, handler, tmp_path / "nobody", clubs={"nobody"})              # no club of interest plays there: nothing is scouted
    assert "scouting" in _cli(monkeypatch, handler, tmp_path / "asked", "--scouting", "L_F_-2_2025_2026_Liga_Regular_B", clubs={"nobody"})
