"""PreparationPackage: versioned, checksummed, JSON-serialisable data handed to the
live-game engine (built by ``live_prep`` from MongoDB, consumed on the tablet)."""

import json

import pytest

from src.live_core.package import (
    SCHEMA_VERSION,
    ChecksumMismatchError,
    IncompatibleSchemaError,
    PackageError,
    PreparationPackage,
    make_package_id,
)


def _pkg(**overrides):
    base = dict(
        collection="FEB_LF2_2025_A",
        season="2025-2026",
        team={"id": "982047", "name": "Team A"},
        rival={"id": "982050", "name": "Team B"},
        competition_meta={"competition_url": "https://x/lf2", "season_value": "2025",
                          "group_value": "9", "year": 2025},
        baselines={"league": {"efg": 0.5}, "team": {"efg": 0.52}},
        tables={"players": [], "lineups": [], "roles": [], "rival_players": [], "zones": {}},
        rule_config={"foul_cap": 3},
        created_at="2026-10-07T10:00:00Z",
    )
    base.update(overrides)
    return PreparationPackage(**base)


def test_package_id_is_deterministic():
    assert make_package_id("COL", "42", "2025-2026") == make_package_id("COL", "42", "2025-2026")
    assert make_package_id("COL", "42", "2025-2026") != make_package_id("COL", "43", "2025-2026")
    assert _pkg().package_id == make_package_id("FEB_LF2_2025_A", "982047", "2025-2026")


def test_roundtrip_preserves_content():
    pkg = _pkg()
    loaded = PreparationPackage.loads(pkg.dumps())
    assert loaded == pkg
    assert loaded.schema_version == SCHEMA_VERSION


def test_dumps_is_canonical_regardless_of_key_order():
    a = _pkg(baselines={"x": 1, "y": 2})
    b = _pkg(baselines={"y": 2, "x": 1})
    assert a.dumps() == b.dumps()
    assert a.checksum() == b.checksum()


def test_tampered_content_is_rejected():
    envelope = json.loads(_pkg().dumps())
    envelope["package"]["baselines"]["team"]["efg"] = 0.99
    with pytest.raises(ChecksumMismatchError):
        PreparationPackage.loads(json.dumps(envelope))


def test_newer_schema_version_is_rejected_with_clear_error():
    envelope = json.loads(_pkg().dumps())
    envelope["package"]["schema_version"] = SCHEMA_VERSION + 1
    # recompute so only the version differs
    import hashlib
    body = json.dumps(envelope["package"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    envelope["checksum"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    with pytest.raises(IncompatibleSchemaError) as exc:
        PreparationPackage.loads(json.dumps(envelope))
    assert str(SCHEMA_VERSION + 1) in str(exc.value)


@pytest.mark.parametrize("missing", ["collection", "team", "rival", "tables", "created_at"])
def test_missing_required_field_is_rejected(missing):
    envelope = json.loads(_pkg().dumps())
    del envelope["package"][missing]
    import hashlib
    body = json.dumps(envelope["package"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    envelope["checksum"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    with pytest.raises(PackageError):
        PreparationPackage.loads(json.dumps(envelope))


def test_non_json_input_is_a_package_error():
    with pytest.raises(PackageError):
        PreparationPackage.loads("not json")


def test_unicode_survives_roundtrip():
    pkg = _pkg(team={"id": "1", "name": "Peñas Ñandú"})
    assert PreparationPackage.loads(pkg.dumps()).team["name"] == "Peñas Ñandú"
