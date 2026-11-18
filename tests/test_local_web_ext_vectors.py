"""A REAL publication of ``web-data-ext`` (#884, PR C): the exporter's output over two external sources, committed in ``tests/local_vectors/web_data_ext`` for the web tests, and what keeps it honest.

FIBA worked on its last run; NCAA worked the day before and FAILED on the last one (its ``last_ok`` is kept, so the web can say «data from 17/11»). Both are real FEB games badged as the source, run through the whole
chain (refresh, archive, publication). Sealing is random, so the directory is committed and only regenerated on demand (``python tests/local_vectors/generate_web_data_ext.py``); this test checks that it still
opens and says what the exporter says today. The secret is public on purpose: these are fixtures.
"""
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import generate_web_data_ext as vectors  # noqa: E402

from src.live_prep.package_scopes import open_sealed, scope_key  # noqa: E402
from src.local_data.contract import validate_manifest  # noqa: E402

OUT = vectors.OUT


def _manifest() -> dict:
    return json.loads((OUT / "index.json").read_text(encoding="utf-8"))


def _open(directory: Path, entry: dict) -> dict:
    envelope = json.loads((directory / entry["file"]).read_text(encoding="utf-8"))
    return json.loads(open_sealed(envelope, entry["wraps"], {"abierto": scope_key(vectors.SECRET, "abierto")}))


def test_the_committed_manifest_satisfies_the_contract_and_has_the_open_key_of_web_data():
    manifest = _manifest()
    validate_manifest(manifest)
    assert manifest["open_key"] and manifest["open_key"] == json.loads((vectors.OUT.parent / "web_data" / "index.json").read_text(encoding="utf-8"))["open_key"]     # one open key opens both publications


def test_it_has_a_competition_per_source_with_the_names_the_selector_reads():
    rows = {r["collection"]: r for r in _manifest()["rows"]}
    assert set(rows) == {vectors.FIBA, vectors.NCAA}
    fiba, ncaa = rows[vectors.FIBA], rows[vectors.NCAA]
    assert (fiba["league"], fiba["gender"], fiba["category"], fiba["competition_label"]) == ("fiba", "F", "senior", "FIBA U18 EuroBasket")
    assert (ncaa["league"], ncaa["gender"], ncaa["competition_label"], ncaa["group_label"]) == ("ncaa", "M", "NCAA D1", "SEC")      # the conference is the group


def test_it_says_how_fresh_each_source_is_and_that_ncaa_failed_on_its_last_run():
    sources = {s["source"]: s for s in _manifest()["sources"]}
    assert (sources["fiba"]["state"], sources["fiba"]["ok"], sources["fiba"]["last_ok"]) == ("ok", True, "2026-11-18T07:00:00Z")
    assert (sources["ncaa"]["state"], sources["ncaa"]["ok"], sources["ncaa"]["last_ok"], sources["ncaa"]["finished"]) == ("failed", False, "2026-11-17T07:00:00Z", "2026-11-18T07:00:00Z")
    assert all(s["published"] == 1 and s["games"] == 13 and s["unreliable"] == 12 for s in sources.values())


def test_the_sealed_rows_open_with_the_open_key_and_carry_the_prefixed_ids():
    for entry in _manifest()["rows"]:
        rows = _open(OUT, entry)
        assert rows["league"] == entry["league"] and {r["team_id"] for r in rows["team_rows"]} == {f"{entry['league']}:982047", f"{entry['league']}:981204"}


def test_it_says_what_the_exporter_says_today(tmp_path):
    fresh = vectors.build(tmp_path)
    assert {r["collection"] for r in fresh["rows"]} == {r["collection"] for r in _manifest()["rows"]}
    stored = {r["collection"]: r for r in _manifest()["rows"]}
    for entry in fresh["rows"]:
        assert _open(tmp_path, entry) == _open(OUT, stored[entry["collection"]])
    assert fresh["sources"] == _manifest()["sources"]
