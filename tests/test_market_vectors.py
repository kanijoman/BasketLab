"""The committed publication of the Talent vectors (``tests/local_vectors/talent_data``) still opens and says what the exporter says today.

The web tests read it as the browser would; if the exporter changes a row (a field, a rounding, the unit of the minutes), this is the test that tells that the vectors are behind and must be
regenerated with ``python tests/local_vectors/generate_talent_data.py`` (the files are sealed at random, so they are compared by their content, not their bytes)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import generate_equivalence  # noqa: E402
import generate_formation  # noqa: E402
import generate_talent_data as vectors  # noqa: E402
from src.live_prep.package_scopes import open_sealed, scope_key  # noqa: E402
from src.live_prep.package_sealing import ScopedSealer  # noqa: E402
from src.market.contract import validate_talent_manifest  # noqa: E402
from src.market.publish import publish_talent_data  # noqa: E402


def _rows(directory, entry):
    envelope = json.loads((Path(directory) / entry["file"]).read_text(encoding="utf-8"))
    return json.loads(open_sealed(envelope, entry["wraps"], {"abierto": scope_key(vectors.SECRET, "abierto")}))


@pytest.fixture(scope="module")
def today(tmp_path_factory):
    out = tmp_path_factory.mktemp("talent")
    publish_talent_data(vectors.fixture_connection(), out, ScopedSealer(vectors.SECRET, open_access=True), [vectors.FEB, vectors.FBCYL], vectors.CATALOGUE, roster_rows=vectors.ROSTER, links=vectors.LINKS)
    return out


def test_the_committed_manifest_satisfies_the_contract_and_publishes_the_open_key():
    manifest = json.loads((vectors.OUT / "index.json").read_text(encoding="utf-8"))
    validate_talent_manifest(manifest)
    assert manifest["open_key"] and [e["key"] for e in manifest["competitions"]] == ["fbcyl|1129-1|2026", "feb|lf2|2025"]


def test_the_committed_files_open_with_the_open_key_and_are_what_the_exporter_makes_today(today):
    committed = json.loads((vectors.OUT / "index.json").read_text(encoding="utf-8"))["competitions"]
    fresh = json.loads((today / "index.json").read_text(encoding="utf-8"))["competitions"]
    assert [e["key"] for e in committed] == [e["key"] for e in fresh]
    for old, new in zip(committed, fresh):
        assert _rows(vectors.OUT, old) == _rows(today, new), f"{old['key']}: regenerate with python tests/local_vectors/generate_talent_data.py"
        assert {k: old[k] for k in old if k not in ("file", "bytes", "sha256", "wraps", "zones")} == {k: new[k] for k in new if k not in ("file", "bytes", "sha256", "wraps", "zones")}
        assert _rows(vectors.OUT, old["zones"]) == _rows(today, new["zones"]), f"{old['key']} zones: regenerate with python tests/local_vectors/generate_talent_data.py"


def test_the_committed_identities_say_who_the_linked_fbcyl_player_is(today):
    committed = json.loads((vectors.OUT / "index.json").read_text(encoding="utf-8"))["identities"]
    fresh = json.loads((today / "index.json").read_text(encoding="utf-8"))["identities"]
    assert _rows(vectors.OUT, committed) == _rows(today, fresh) == {"format": 1, "links": vectors.LINKS, "by_feb": {"feb:10100": ["fbcyl|1129-1|2026"]}}


def _same(a, b, path="") -> None:
    """Equal structure and strings; numbers within 2e-5 (the document is rounded to 5 decimals and the least squares of numpy differs in the last bits between platforms: the CI is Linux)."""
    if isinstance(a, dict):
        assert isinstance(b, dict) and a.keys() == b.keys(), path
        for k in a:
            _same(a[k], b[k], f"{path}/{k}")
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            _same(x, y, f"{path}[{i}]")
    elif isinstance(a, (int, float)) and not isinstance(a, bool):
        assert b == pytest.approx(a, abs=2e-5), path
    else:
        assert a == b, path


def test_the_committed_equivalence_vectors_are_what_the_estimator_gives_today():
    committed = json.loads(generate_equivalence.OUT.read_text(encoding="utf-8"))
    _same(committed, json.loads(json.dumps(generate_equivalence.build())))


def test_the_committed_formation_vectors_are_what_the_index_gives_today():
    committed = json.loads(generate_formation.OUT.read_text(encoding="utf-8"))
    _same(committed, json.loads(json.dumps(generate_formation.build())))
