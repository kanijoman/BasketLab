"""The committed publication of ``tests/local_vectors/web_data`` (#328, #639) is the contract the browser is tested against.

The web tests open it with WebCrypto and the open key of its manifest; this keeps it honest on the Python side: it must still open, and say exactly
what the exporter produces today for the same leagues (a change in the reports or the rows shows up here, and the fix is to regenerate the directory).
"""
import json
import sys
from pathlib import Path

import mongomock
import pymongo
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import generate_web_data as vectors  # noqa: E402
from src.live_prep.package_scopes import open_sealed, scope_key  # noqa: E402
from src.local_data.export import export_collection, export_derived  # noqa: E402
from src.local_data.team_reports import _dump, build_reports  # noqa: E402
from src.local_data.web_data import SCHEMA, SECTIONS  # noqa: E402

OUT = vectors.OUT


@pytest.fixture()
def handler(monkeypatch):
    monkeypatch.setattr(pymongo, "MongoClient", mongomock.MongoClient)
    yield vectors.fixture_handler()
    vectors.deps._create_handler.cache_clear()


def _manifest() -> dict:
    return json.loads((OUT / "index.json").read_text(encoding="utf-8"))


def _open(entry: dict) -> str:
    envelope = json.loads((OUT / entry["file"]).read_text(encoding="utf-8"))
    return open_sealed(envelope, entry["wraps"], {"abierto": scope_key(vectors.SECRET, "abierto")})


def test_the_manifest_is_the_current_schema_and_publishes_the_open_key():
    manifest = _manifest()
    assert manifest["schema"] == SCHEMA and manifest["v"] == 2 and manifest["open_key"]
    assert sorted(r["collection"] for r in manifest["rows"]) == sorted([vectors.FEB, vectors.FBCYL])


def test_the_sealed_rows_say_what_the_exporter_says_today(handler):
    db = handler.connection.client["BASKETBALL"]
    for entry in _manifest()["rows"]:
        fresh = json.loads(json.dumps(export_collection(db[entry["collection"]], entry["collection"]), default=str))
        assert json.loads(_open(entry)) == fresh, entry["collection"]


def test_the_sealed_reports_say_what_the_service_says_today(handler):
    for manifest_entry in _manifest()["reports"]:
        index = json.loads((OUT / manifest_entry["file"]).read_text(encoding="utf-8"))
        fresh = {(tid, mode, None): _dump(report) for tid, _name, mode, report in build_reports(handler, manifest_entry["collection"])}
        for entry in index["reports"]:
            if entry["mode"] == "scouting":
                service = vectors.fixture_scouting_service(handler)
                fresh[(entry["team_id"], "scouting", entry["scope"])] = _dump(service.build_scopes(manifest_entry["collection"], entry["team_id"])[entry["scope"]])
        assert {(e["team_id"], e["mode"], e.get("scope")) for e in index["reports"]} == set(fresh)
        for entry in index["reports"]:
            assert _open(entry) == fresh[(entry["team_id"], entry["mode"], entry.get("scope"))]


def test_the_published_scouting_has_the_scopes_of_a_team_with_cup_games():
    index = json.loads((OUT / next(e["file"] for e in _manifest()["reports"] if e["collection"] == vectors.FEB)).read_text(encoding="utf-8"))
    scouting = [e for e in index["reports"] if e["mode"] == "scouting"]
    assert sorted((e["team_id"], e["scope"]) for e in scouting) == sorted((t, s) for t in ("101", "102") for s in ("liga", "copa", "todo"))
    assert {s: _open(next(e for e in scouting if e["team_id"] == "101" and e["scope"] == s)) and json.loads(_open(next(e for e in scouting if e["team_id"] == "101" and e["scope"] == s)))["sample_games"]
            for s in ("liga", "copa", "todo")} == {"liga": 2, "copa": 1, "todo": 3}


def test_every_file_of_the_publication_is_referenced_and_named_by_its_hash():
    manifest = _manifest()
    files = {e["file"] for e in manifest["rows"] + [x for section in SECTIONS for x in manifest.get(section, [])] + manifest["reports"]}
    for entry in manifest["reports"]:
        files |= {e["file"] for e in json.loads((OUT / entry["file"]).read_text(encoding="utf-8"))["reports"]}
    on_disk = {str(p.relative_to(OUT)).replace("\\", "/") for p in OUT.rglob("*") if p.is_file()}
    assert on_disk == files | {"index.json", "frontend/vercel.json"}


def test_the_publication_has_the_derived_of_each_competition_and_they_say_what_the_exporter_says_today(handler):
    manifest = _manifest()
    assert sorted(d["collection"] for d in manifest["derived"]) == sorted(r["collection"] for r in manifest["rows"])
    db = handler.connection.client["BASKETBALL"]
    for entry in manifest["derived"]:
        fresh = json.loads(json.dumps(export_derived(db[entry["collection"]], entry["collection"]), default=str))
        assert json.loads(_open(entry)) == fresh, entry["collection"]
