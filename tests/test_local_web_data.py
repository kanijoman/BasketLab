"""The web-data branch (#328, #640): what the refresh publishes for the web, sealed by scope, with a manifest and files that never change in place.

The artifacts are served by a CDN with a cache of minutes and read by clients that may hold an older manifest: a file name that stays while its
bytes change would mix versions, so a name carries the hash of its content and an unchanged file is kept byte for byte (sealing is random).
Nothing readable is published: rows and reports are sealed, and access is the wraps of the index.
"""
import json
import sys
from pathlib import Path

import mongomock
import pymongo
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import fbcyl_games  # noqa: E402
import games  # noqa: E402
from src.live_prep.package_scopes import open_sealed, scope_key  # noqa: E402
from src.live_prep.package_sealing import ScopedSealer  # noqa: E402
from src.local_data.export import export_collection  # noqa: E402
from src.local_data.web_data import SCHEMA, publish_web_data  # noqa: E402

FEB = "L_F_-2_2025_2026_Liga_Regular_B"
FBCYL = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"
MASTER = "a-master-secret-for-the-tests"


@pytest.fixture()
def handler(monkeypatch):
    from src.api import deps

    monkeypatch.setattr(pymongo, "MongoClient", mongomock.MongoClient)
    deps._create_handler.cache_clear()
    handler = deps._create_handler()
    db = handler.connection.client["BASKETBALL"]
    db[FEB].insert_many(games.build_games())
    db[FBCYL].insert_many(fbcyl_games.build_games())
    yield handler
    deps._create_handler.cache_clear()


def _tree(out: Path) -> dict:
    return {str(p.relative_to(out)).replace("\\", "/"): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}


def _manifest(out: Path) -> dict:
    return json.loads((out / "index.json").read_text(encoding="utf-8"))


def _open(out: Path, entry: dict, scope: str) -> dict:
    envelope = json.loads((out / entry["file"]).read_text(encoding="utf-8"))
    return json.loads(open_sealed(envelope, entry["wraps"], {scope: scope_key(MASTER, scope)}))


def test_the_manifest_lists_the_rows_and_the_reports_of_every_competition(handler, tmp_path):
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB, FBCYL])
    manifest = _manifest(tmp_path)
    assert manifest["schema"] == SCHEMA and manifest["v"] == 2 and manifest["open_key"]
    assert sorted(r["collection"] for r in manifest["rows"]) == sorted([FEB, FBCYL])
    assert sorted(r["collection"] for r in manifest["reports"]) == sorted([FEB, FBCYL])
    assert {r["league"] for r in manifest["rows"]} == {"feb", "fbcyl"}
    assert all(set(e) >= {"file", "bytes", "sha256"} for e in manifest["rows"] + manifest["reports"])


def test_the_rows_are_the_export_of_the_competition_sealed_for_its_scope(handler, tmp_path):
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER, open_access=False), [FEB])
    entry = _manifest(tmp_path)["rows"][0]
    db = handler.connection.client["BASKETBALL"]
    assert _open(tmp_path, entry, f"competicion:{FEB}") == json.loads(json.dumps(export_collection(db[FEB], FEB), default=str))
    with pytest.raises(Exception):
        _open(tmp_path, entry, "club:101")                                # a club key does not open the rows of the whole competition


def test_while_the_beta_is_open_the_open_key_opens_the_rows_and_closing_it_removes_it(handler, tmp_path):
    publish_web_data(handler, tmp_path / "open", ScopedSealer(MASTER, open_access=True), [FEB])
    assert _open(tmp_path / "open", _manifest(tmp_path / "open")["rows"][0], "abierto")["collection"] == FEB
    publish_web_data(handler, tmp_path / "closed", ScopedSealer(MASTER, open_access=False), [FEB])
    manifest = _manifest(tmp_path / "closed")
    assert "open_key" not in manifest
    assert all(w["scope"] != "abierto" for e in manifest["rows"] for w in e["wraps"])


def test_the_reports_of_a_competition_have_their_own_index_so_a_page_loads_only_its_own(handler, tmp_path):
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER, open_access=False), [FEB])
    entry = _manifest(tmp_path)["reports"][0]
    index = json.loads((tmp_path / entry["file"]).read_text(encoding="utf-8"))
    assert len(index["reports"]) == 8 and {e["mode"] for e in index["reports"]} == {"own", "rival"}
    own = next(e for e in index["reports"] if e["mode"] == "own" and e["team_id"] == "101")
    assert _open(tmp_path, own, "club:101")["team"] == "ALPHA"


def test_every_file_name_carries_the_hash_of_its_content(handler, tmp_path):
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB])
    manifest = _manifest(tmp_path)
    for entry in manifest["rows"] + manifest["reports"]:
        assert entry["sha256"][:12] in entry["file"] and entry["file"].isascii() and entry["file"].startswith(("rows/", "reports/"))
        assert (tmp_path / entry["file"]).stat().st_size == entry["bytes"]


def test_a_refresh_without_news_changes_no_byte_regression(handler, tmp_path):
    """Sealing is random: without the previous publication every file would be new (and every cache invalid) on each of the 3 refreshes a day."""
    sealer = ScopedSealer(MASTER)
    publish_web_data(handler, tmp_path, sealer, [FEB, FBCYL])
    before = _tree(tmp_path)
    publish_web_data(handler, tmp_path, sealer, [FEB, FBCYL])
    assert _tree(tmp_path) == before


def test_a_new_game_never_changes_a_file_in_place_and_leaves_no_orphans(handler, tmp_path):
    sealer = ScopedSealer(MASTER)
    publish_web_data(handler, tmp_path, sealer, [FEB, FBCYL])
    before = _tree(tmp_path)
    handler.connection.client["BASKETBALL"][FEB].insert_one({**games.build_games()[0], "_id": 9999})
    publish_web_data(handler, tmp_path, sealer, [FEB, FBCYL])
    after = _tree(tmp_path)
    assert all(after[name] == data for name, data in before.items() if name in after and name != "index.json")   # same name, same bytes
    assert before.keys() - after.keys() and after.keys() - before.keys()                                         # what changed got a new name
    manifest = _manifest(tmp_path)
    reports = [e["file"] for r in manifest["reports"] for e in json.loads(after[r["file"]])["reports"]]
    referenced = {e["file"] for e in manifest["rows"] + manifest["reports"]} | set(reports) | {"index.json", "frontend/vercel.json"}
    assert set(after) == referenced
    untouched = [n for n in after if "FBCYL" in n and n in before]
    assert untouched                                                                                             # the other competition kept its files


def test_a_subset_republishes_only_those_competitions_and_keeps_the_rest(handler, tmp_path):
    sealer = ScopedSealer(MASTER)
    publish_web_data(handler, tmp_path, sealer, [FEB, FBCYL])
    publish_web_data(handler, tmp_path, sealer, [FEB], keep_others=True)
    assert sorted(r["collection"] for r in _manifest(tmp_path)["rows"]) == sorted([FEB, FBCYL])


def test_the_branch_carries_the_vercel_guard(handler, tmp_path):
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB])
    guard = json.loads((tmp_path / "frontend" / "vercel.json").read_text(encoding="utf-8"))
    assert guard == {"git": {"deploymentEnabled": False}}


def test_no_competition_publishes_an_empty_but_valid_manifest(handler, tmp_path):
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [])
    manifest = _manifest(tmp_path)
    assert manifest["rows"] == [] and manifest["reports"] == []


def test_the_entry_point_publishes_with_the_secret_of_the_environment_and_refuses_without_it(handler, tmp_path, monkeypatch):
    import run_web_data

    monkeypatch.delenv("PACKAGE_MASTER_KEY", raising=False)
    monkeypatch.delenv("PACKAGE_PASSWORD", raising=False)
    assert run_web_data.main(["--out", str(tmp_path / "none")]) == 2
    monkeypatch.setenv("PACKAGE_MASTER_KEY", MASTER)
    assert run_web_data.main(["--out", str(tmp_path / "all"), "--collection", FEB]) == 0
    assert [r["collection"] for r in _manifest(tmp_path / "all")["rows"]] == [FEB]
