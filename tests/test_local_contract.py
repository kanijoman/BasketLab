"""The contract of ``web-data`` (#328): ONE description of the manifest, the TypeScript types generated from it and a validator that the exporter's output passes.

The browser reads ``index.json`` and the index of each competition's reports; their shape used to live twice (the exporter and hand-written TypeScript) and
only a real publication tied them. The shape is now declared once, in ``src/local_data/contract.py``; ``frontend/src/webdata/contract.generated.ts`` is
generated from it (``python run_web_contract.py``) and a test fails when they differ; ``validate`` is what any publication, committed or fresh, must pass.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import generate_web_data as vectors  # noqa: E402
from src.local_data.contract import ContractError, render_typescript, validate_manifest, validate_report_index  # noqa: E402

GENERATED = Path(__file__).resolve().parent.parent / "frontend" / "src" / "webdata" / "contract.generated.ts"
PUBLICATION = vectors.OUT


def _manifest() -> dict:
    return json.loads((PUBLICATION / "index.json").read_text(encoding="utf-8"))


def _report_index(entry: dict) -> dict:
    return json.loads((PUBLICATION / entry["file"]).read_text(encoding="utf-8"))


def test_the_generated_typescript_is_the_current_contract():
    assert GENERATED.read_text(encoding="utf-8").replace("\r\n", "\n") == render_typescript()


def test_the_generated_typescript_declares_what_the_browser_reads():
    text = render_typescript()
    for name in ("WebDataManifest", "RowsEntry", "ReportIndexEntry", "ReportIndex", "ReportEntry", "Wrap"):
        assert f"export interface {name} " in text
    assert "league: 'feb' | 'fbcyl'" in text and "mode: 'own' | 'rival'" in text
    assert "open_key?: string" in text                                    # only while the beta is open
    assert "AUTO-GENERATED" in text.splitlines()[0]


def test_the_committed_publication_satisfies_the_contract():
    manifest = _manifest()
    validate_manifest(manifest)
    for entry in manifest["reports"]:
        validate_report_index(_report_index(entry))


@pytest.mark.parametrize("mutate, message", [
    (lambda m: m.pop("schema"), "schema"),
    (lambda m: m.update(schema=99), "schema"),
    (lambda m: m["rows"][0].pop("wraps"), "wraps"),
    (lambda m: m["rows"][0].update(league="nba"), "league"),
    (lambda m: m["rows"][0].update(bytes="12"), "bytes"),
    (lambda m: m["reports"][0].pop("file"), "file"),
    (lambda m: m["rows"][0]["wraps"][0].pop("iv"), "iv"),
    (lambda m: m.update(rows="nope"), "rows"),
])
def test_a_manifest_that_does_not_satisfy_the_contract_is_refused_and_says_where(mutate, message):
    manifest = _manifest()
    mutate(manifest)
    with pytest.raises(ContractError, match=message):
        validate_manifest(manifest)


@pytest.mark.parametrize("mutate, message", [
    (lambda i: i["reports"][0].update(mode="both"), "mode"),
    (lambda i: i["reports"][0].pop("team_id"), "team_id"),
    (lambda i: i.pop("collection"), "collection"),
])
def test_a_report_index_that_does_not_satisfy_the_contract_is_refused(mutate, message):
    index = _report_index(_manifest()["reports"][0])
    mutate(index)
    with pytest.raises(ContractError, match=message):
        validate_report_index(index)


def test_a_closed_beta_manifest_has_no_open_key_and_is_still_valid():
    manifest = _manifest()
    manifest.pop("open_key")
    validate_manifest(manifest)


def test_what_the_exporter_writes_today_satisfies_the_contract(tmp_path):
    import mongomock
    import pymongo

    from src.live_prep.package_sealing import ScopedSealer
    from src.local_data.web_data import publish_web_data

    original = pymongo.MongoClient
    pymongo.MongoClient = mongomock.MongoClient
    try:
        handler = vectors.fixture_handler()
        manifest = publish_web_data(handler, tmp_path, ScopedSealer("a-master-secret-for-the-tests", open_access=False), [vectors.FEB])
    finally:
        pymongo.MongoClient = original
        vectors.deps._create_handler.cache_clear()
    validate_manifest(manifest)
    for entry in manifest["reports"]:
        validate_report_index(json.loads((tmp_path / entry["file"]).read_text(encoding="utf-8")))
