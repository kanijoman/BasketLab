"""The exporter of the local-first data (#327, step 2): one file per competition with the rows of the contract, and an index.

The web reads these files instead of calling the API (``frontend/src/localdata``), so the files must be exactly the rows the season pipelines
read, deterministic (a refresh that changes nothing changes no byte), safe to name and honest about what they do not have (FBCYL players).
"""
import json
import sys
from pathlib import Path

import pytest
from db_helpers import new_mock_db

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import fbcyl_games  # noqa: E402
import games  # noqa: E402
from src.database.aggregation import AggregationPipelineBuilder  # noqa: E402
from src.local_data.export import FORMAT, export_all, export_collection  # noqa: E402

FEB = "L_F_-2_2025_2026_Liga_Regular_B"
FBCYL = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"


@pytest.fixture()
def db():
    database = new_mock_db("export")
    database[FEB].insert_many(games.build_games())
    database[FBCYL].insert_many(fbcyl_games.build_games())
    return database


def test_a_feb_competition_exports_its_team_and_player_rows(db):
    payload = export_collection(db[FEB], FEB)
    assert (payload["format"], payload["league"], payload["collection"], payload["games"]) == (FORMAT, "feb", FEB, 12)
    assert len(payload["team_rows"]) == 24 and len(payload["player_rows"]) == 200
    expected = list(db[FEB].aggregate(AggregationPipelineBuilder.build_season_rows_pipeline()))
    assert [r["match_id"] for r in payload["team_rows"]] == [r["match_id"] for r in expected]
    assert "_id" not in payload["team_rows"][0] and "_id" not in payload["player_rows"][0]
    json.dumps(payload)                                                   # plain JSON, nothing from Mongo left in it


def test_an_fbcyl_competition_has_team_rows_and_player_rows_with_the_identity_resolved(db):
    payload = export_collection(db[FBCYL], FBCYL)
    assert payload["league"] == "fbcyl" and len(payload["team_rows"]) == 24
    assert payload["player_rows"] and all(r["player_uuid"] and "uuid" not in r for r in payload["player_rows"])   # #644


def test_an_empty_competition_exports_empty_tables_not_an_error(db):
    payload = export_collection(db["EMPTY"], "L_F_-2_2025_2026_Vacia")
    assert (payload["games"], payload["team_rows"], payload["player_rows"]) == (0, [], [])


def test_export_all_writes_one_safe_file_per_competition_and_an_index(db, tmp_path):
    index = export_all(db, tmp_path)
    names = {c["name"]: c for c in index["collections"]}
    assert set(names) == {FEB, FBCYL}
    for entry in names.values():
        assert entry["file"].isascii() and "/" not in entry["file"] and (tmp_path / entry["file"]).is_file()
        assert entry["bytes"] == (tmp_path / entry["file"]).stat().st_size
    assert names[FEB]["games"] == 12 and names[FBCYL]["league"] == "fbcyl"
    assert json.loads((tmp_path / "index.json").read_text(encoding="utf-8")) == index


def test_exporting_twice_changes_no_byte_regression(db, tmp_path):
    """A refresh that brings no new game must not rewrite the files (they are published and cached): no timestamps inside, stable order."""
    export_all(db, tmp_path)
    first = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    export_all(db, tmp_path)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == first


def test_only_refreshes_some_competitions_and_keeps_the_others(db, tmp_path):
    full = export_all(db, tmp_path)
    db[FEB].insert_one({**games.build_games()[0], "_id": 9999})
    index = export_all(db, tmp_path, only=[FEB])
    by_name = {c["name"]: c for c in index["collections"]}
    assert set(by_name) == {FEB, FBCYL} and by_name[FEB]["games"] == 13
    assert by_name[FBCYL] == {c["name"]: c for c in full["collections"]}[FBCYL]
    assert (tmp_path / by_name[FBCYL]["file"]).is_file()


def test_a_competition_that_no_longer_exists_leaves_no_stale_file(db, tmp_path):
    export_all(db, tmp_path)
    db.drop_collection(FBCYL)
    index = export_all(db, tmp_path)
    assert [c["name"] for c in index["collections"]] == [FEB]
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(["index.json", index["collections"][0]["file"]])


@pytest.mark.parametrize("name, build", [(FEB, games.build_games), (FBCYL, fbcyl_games.build_games)])
def test_rows_do_not_depend_on_the_order_the_games_were_stored_in_regression(name, build):
    """The archive restores the games sorted by ``_id`` and the scraper inserts them as they finish: the file must be the same bytes either way,
    or every refresh would republish every competition."""
    forward, backward = new_mock_db("forward"), new_mock_db("backward")
    forward[name].insert_many(build())
    backward[name].insert_many(list(reversed(build())))
    assert export_collection(forward[name], name) == export_collection(backward[name], name)
