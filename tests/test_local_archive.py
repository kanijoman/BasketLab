"""The private archive of the games (#646): one compressed file per competition, restored into an ephemeral Mongo on every refresh.

The refresh downloads the archive, loads it into a Mongo that lives as long as the job, scrapes what is new and writes the archive back: the
files must round-trip every type Mongo holds, be byte-identical when nothing changed (no commit, no cache invalidation) and be checked
against their hash before anything is loaded.
"""
import gzip
import json
from datetime import datetime

import pytest
from bson import ObjectId
from db_helpers import new_mock_db

from src.local_data.archive import dump_archive, load_archive, working_set

NAMES = ["PRIMERA_FEB_2024_2025_Liga_Regular_\u00danico", "PRIMERA_FEB_2025_2026_Liga_Regular_\u00danico", "PRIMERA_FEB_2026_2027_Liga_Regular_\u00danico",
         "FBCYL_2026_2027_Liga_Regular_A"]


def _game(n, **extra):
    return {"_id": n, "HEADER": {"starttime": "01-10-2026 - 18:00"}, "PLAYBYPLAY": {"LINES": [{"n": i} for i in range(50)]},
            "DERIVED": {"v": 6}, "when": datetime(2026, 10, 1, 18, 0), "ref": ObjectId("65a1b2c3d4e5f60718293a4b"), **extra}


@pytest.fixture()
def db():
    db = new_mock_db("archive")
    for name in NAMES:
        db[name].insert_many([_game(2), _game(1)])
    db["HISTORICAL"].insert_one({"_id": 1})
    return db


def _docs(db, name):
    return sorted(db[name].find({}), key=lambda d: d["_id"])


def test_round_trip_keeps_every_type_and_field(db, tmp_path):
    dump_archive(db, tmp_path, light=lambda name: False)
    target = new_mock_db("restored")
    load_archive(tmp_path, target)
    for name in NAMES:
        assert _docs(target, name) == _docs(db, name)


def test_only_games_collections_are_archived(db, tmp_path):
    manifest = dump_archive(db, tmp_path, light=lambda name: False)
    assert sorted(c["name"] for c in manifest["collections"]) == sorted(NAMES)


def test_unchanged_database_writes_the_same_bytes(db, tmp_path):
    dump_archive(db, tmp_path, light=lambda name: False)
    first = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    db[NAMES[0]].delete_many({})
    db[NAMES[0]].insert_many([_game(1), _game(2)])               # same games inserted in another order
    dump_archive(db, tmp_path, light=lambda name: False)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == first


def test_a_corrected_game_changes_only_its_collection_file(db, tmp_path):
    dump_archive(db, tmp_path, light=lambda name: False)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    db[NAMES[1]].update_one({"_id": 1}, {"$set": {"HEADER.starttime": "02-10-2026 - 18:00"}})
    dump_archive(db, tmp_path, light=lambda name: False)
    changed = {p.name for p in tmp_path.iterdir() if p.read_bytes() != before.get(p.name)}
    assert len(changed) == 2 and "archive.json" in changed        # the file and the manifest


def test_the_light_version_drops_the_play_by_play_and_keeps_the_rest(db, tmp_path):
    dump_archive(db, tmp_path, light=lambda name: name == NAMES[0])
    target = new_mock_db("restored")
    load_archive(tmp_path, target)
    light, full = _docs(target, NAMES[0]), _docs(target, NAMES[1])
    assert all("PLAYBYPLAY" not in d and d["DERIVED"] == {"v": 6} and d["HEADER"] for d in light)
    assert all(len(d["PLAYBYPLAY"]["LINES"]) == 50 for d in full)


def test_a_light_fbcyl_game_drops_its_moves(tmp_path):
    db = new_mock_db("fb")
    db[NAMES[3]].insert_one({"_id": 1, "moves": [{"a": 1}], "stats": {"teams": []}, "DERIVED": {"v": 6}})
    dump_archive(db, tmp_path, light=lambda name: True)
    target = new_mock_db("restored")
    load_archive(tmp_path, target)
    assert _docs(target, NAMES[3]) == [{"_id": 1, "stats": {"teams": []}, "DERIVED": {"v": 6}}]


def test_a_tampered_file_is_refused_before_anything_is_loaded(db, tmp_path):
    manifest = dump_archive(db, tmp_path, light=lambda name: False)
    victim = tmp_path / manifest["collections"][-1]["file"]
    victim.write_bytes(gzip.compress(b'{"_id": 99}\n', mtime=0))
    target = new_mock_db("restored")
    with pytest.raises(ValueError, match="sha256"):
        load_archive(tmp_path, target)
    assert target.list_collection_names() == []


def test_loading_twice_is_idempotent_and_replaces_by_game(db, tmp_path):
    dump_archive(db, tmp_path, light=lambda name: False)
    target = new_mock_db("restored")
    load_archive(tmp_path, target)
    target[NAMES[0]].update_one({"_id": 1}, {"$set": {"stale": True}})
    load_archive(tmp_path, target)
    load_archive(tmp_path, target)
    assert _docs(target, NAMES[0]) == _docs(db, NAMES[0])


def test_an_empty_collection_is_archived_and_restored_empty(tmp_path):
    db = new_mock_db("empty")
    db.create_collection(NAMES[0])
    dump_archive(db, tmp_path, light=lambda name: False)
    target = new_mock_db("restored")
    assert load_archive(tmp_path, target) == {NAMES[0]: 0}


def test_a_collection_that_left_the_database_leaves_the_archive(db, tmp_path):
    dump_archive(db, tmp_path, light=lambda name: False)
    db.drop_collection(NAMES[3])
    manifest = dump_archive(db, tmp_path, light=lambda name: False)
    assert NAMES[3] not in [c["name"] for c in manifest["collections"]]
    assert len(list(tmp_path.glob("*.jsonl.gz"))) == 3


def test_the_manifest_is_plain_json_with_hashes(db, tmp_path):
    dump_archive(db, tmp_path, light=lambda name: False)
    manifest = json.loads((tmp_path / "archive.json").read_text(encoding="utf-8"))
    assert manifest["format"] == 1 and all(len(c["sha256"]) == 64 and c["games"] == 2 for c in manifest["collections"])


@pytest.mark.parametrize("names, current_and_previous", [
    (NAMES[:3], {NAMES[1], NAMES[2]}),                             # the season in course and the one before
    (NAMES[:2], {NAMES[0], NAMES[1]}),
    (["COPA_ESPA_A_2026_2027_Play_offs", "TERCERA_FEB_2025_2026_Liga_Regular_A-B", "TERCERA_FEB_2023_2024_Liga_Regular_A-B"],
     {"COPA_ESPA_A_2026_2027_Play_offs", "TERCERA_FEB_2025_2026_Liga_Regular_A-B"}),
    (["NO_SEASON_HERE"], {"NO_SEASON_HERE"}),                      # without a season in the name: never lightened
    ([], set()),
])
def test_working_set_is_the_current_and_the_previous_season(names, current_and_previous):
    assert {n for n in names if working_set(names)(n)} == current_and_previous


def test_the_entry_point_refuses_to_replace_without_the_flag(tmp_path, capsys):
    import run_archive

    assert run_archive.main(["load", "--src", str(tmp_path)]) == 2
    assert "--replace" in capsys.readouterr().err


def test_a_refresh_that_lost_games_does_not_overwrite_the_archive_regression(db, tmp_path):
    """The archive is rewritten from the ephemeral Mongo at the end of a refresh: a restore that failed halfway, or a scrape that dropped a
    collection, must stop there instead of replacing the only copy of the games with fewer."""
    dump_archive(db, tmp_path, light=lambda name: False)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    db[NAMES[1]].delete_one({"_id": 1})
    with pytest.raises(ValueError, match="fewer games"):
        dump_archive(db, tmp_path, light=lambda name: False, allow_shrink=False)
    db.drop_collection(NAMES[1])
    with pytest.raises(ValueError, match="fewer games"):
        dump_archive(db, tmp_path, light=lambda name: False, allow_shrink=False)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before          # nothing was touched


def test_new_games_and_new_collections_are_not_shrinking(db, tmp_path):
    dump_archive(db, tmp_path, light=lambda name: False)
    db[NAMES[1]].insert_one(_game(3))
    db["PRIMERA_FEB_2027_2028_Liga_Regular_\u00danico"].insert_one(_game(1))
    manifest = dump_archive(db, tmp_path, light=lambda name: False, allow_shrink=False)
    assert sum(c["games"] for c in manifest["collections"]) == 8 + 1 + 1


def test_an_empty_collection_survives_a_restore_and_the_next_dump_regression(tmp_path):
    """Run 40862376952: the archive held ``COPA_ESPA\u00d1A_2024_2025_PLAYOFFS_Final`` with 0 games; Mongo does not create a collection until its
    first document, so the restore left it out and the refresh's own safeguard took it for lost games and refused to save the archive."""
    db = new_mock_db("with_empty")
    db[NAMES[0]].insert_one(_game(1))
    db.create_collection(NAMES[1])
    dump_archive(db, tmp_path, light=lambda name: False)
    restored = new_mock_db("restored")
    load_archive(tmp_path, restored)
    assert set(restored.list_collection_names()) == {NAMES[0], NAMES[1]}
    manifest = dump_archive(restored, tmp_path, light=lambda name: False, allow_shrink=False)
    assert {c["name"]: c["games"] for c in manifest["collections"]} == {NAMES[0]: 1, NAMES[1]: 0}


def test_an_empty_collection_that_is_gone_is_not_lost_games(tmp_path):
    """Defence in depth: nothing was lost with a collection that had no game."""
    db = new_mock_db("with_empty")
    db[NAMES[0]].insert_one(_game(1))
    db.create_collection(NAMES[1])
    dump_archive(db, tmp_path, light=lambda name: False)
    db.drop_collection(NAMES[1])
    manifest = dump_archive(db, tmp_path, light=lambda name: False, allow_shrink=False)
    assert [c["name"] for c in manifest["collections"]] == [NAMES[0]]
