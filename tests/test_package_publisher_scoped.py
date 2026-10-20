"""The publisher can seal by scope (issue #410): packages open for the beta with a key in the index, paid scopes for later.

``access.mode`` is ``legacy`` (password, what the apps in the field read) until the release of the app that reads scopes is out, then
``scoped``. In scoped mode the index is v2 and says the key of the ``abierto`` scope while ``access.open`` is true.
"""
import base64
import json
from datetime import datetime, timezone

import pytest

from src.live_prep.package_crypto import decrypt_package
from src.live_prep.package_scopes import SCOPE_OPEN, open_sealed, scope_key
from src.live_prep.package_sealing import LegacySealer, ScopedSealer, make_sealer
from src.live_prep.publisher import build_index, load_config, publish_all, publish_round_bundles
from tests.test_package_publisher import OWN, PASSWORD, R1, _builder, _match, _round, _round_builder, _round_service, _schedule

MASTER = "clave-maestra-de-prueba"
NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def keys(*scopes):
    return {s: scope_key(MASTER, s) for s in scopes}


def scoped(**kw):
    return ScopedSealer(MASTER, now=NOW, **kw)


def test_a_scoped_package_is_open_to_the_beta_the_club_and_its_competition_and_the_wraps_are_in_the_index_entry(tmp_path):
    entries = publish_all(object(), tmp_path, scoped(extra_scopes=["temporada:2026-27"], monthly=True), ["COL"], OWN,
                          service=_schedule([_match("10", R1, "2026-10-10T17:00")]), build=_builder())
    [entry] = entries
    assert [w["scope"] for w in entry["wraps"]] == [SCOPE_OPEN, f"club:{OWN}", "competicion:COL", "temporada:2026-27", "mensual:2026-11"]
    envelope = read(tmp_path / OWN / f"{R1}.bpkg")
    assert envelope["v"] == 2 and "kdf" not in envelope
    for scope in (SCOPE_OPEN, f"club:{OWN}", "competicion:COL", "temporada:2026-27", "mensual:2026-11"):
        assert json.loads(open_sealed(envelope, entry["wraps"], keys(scope))) == {"team": OWN, "rival": R1}
    assert read(tmp_path / "index.json")["packages"] == entries


def test_without_the_open_scope_the_beta_key_is_not_a_way_in_and_nothing_is_re_encrypted(tmp_path):
    entries = publish_all(object(), tmp_path, scoped(open_access=False), ["COL"], OWN,
                          service=_schedule([_match("10", R1, "2026-10-10T17:00")]), build=_builder())
    scopes = [w["scope"] for w in entries[0]["wraps"]]
    assert SCOPE_OPEN not in scopes and scopes == [f"club:{OWN}", "competicion:COL"]
    from src.live_prep.package_crypto import DecryptionError
    with pytest.raises(DecryptionError):
        open_sealed(read(tmp_path / OWN / f"{R1}.bpkg"), entries[0]["wraps"], keys(SCOPE_OPEN))


def test_a_scoped_round_bundle_is_compressed_and_wrapped_for_the_club_and_the_competition(tmp_path):
    entries = publish_round_bundles(object(), tmp_path, scoped(), ["A"], OWN, service=_round_service({"A": _round(4, (OWN, R1))}),
                                    build=_round_builder([]))
    [entry] = entries
    assert [w["scope"] for w in entry["wraps"]] == [SCOPE_OPEN, f"club:{OWN}", "competicion:A"]
    envelope = read(tmp_path / entry["file"])
    assert envelope["v"] == 2 and envelope["z"] == "gzip"
    assert json.loads(open_sealed(envelope, entry["wraps"], keys(SCOPE_OPEN)))["round"] == 4


def test_a_legacy_publication_is_what_it_was_with_no_wraps(tmp_path):
    entries = publish_all(object(), tmp_path, LegacySealer(PASSWORD), ["COL"], OWN,
                          service=_schedule([_match("10", R1, "2026-10-10T17:00")]), build=_builder())
    assert "wraps" not in entries[0]
    assert json.loads(decrypt_package(read(tmp_path / OWN / f"{R1}.bpkg"), PASSWORD)) == {"team": OWN, "rival": R1}


def test_the_index_of_a_scoped_publication_is_v2_and_publishes_the_open_key_only_while_it_is_open():
    index = build_index([], now="n", sealer=scoped())
    assert index["v"] == 2 and base64.b64decode(index["open_key"]) == scope_key(MASTER, SCOPE_OPEN)
    closed = build_index([], now="n", sealer=scoped(open_access=False))
    assert closed["v"] == 2 and "open_key" not in closed
    assert build_index([], now="n", sealer=LegacySealer(PASSWORD)) == build_index([], now="n"), "legacy keeps the index of always"


def test_the_config_chooses_the_mode_and_defaults_to_the_one_the_apps_in_the_field_read(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"team_id": OWN}), encoding="utf-8")
    assert load_config(path)["access"] == {"mode": "legacy", "open": True, "monthly": False, "scopes": []}
    path.write_text(json.dumps({"team_id": OWN, "access": {"mode": "scoped", "open": False, "monthly": True, "scopes": ["temporada:2026-27"]}}),
                    encoding="utf-8")
    assert load_config(path)["access"] == {"mode": "scoped", "open": False, "monthly": True, "scopes": ["temporada:2026-27"]}
    path.write_text(json.dumps({"team_id": OWN, "access": {"mode": "otro"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="mode"):
        load_config(path)


def test_make_sealer_builds_the_sealer_of_the_mode_from_the_environment():
    legacy = make_sealer({"mode": "legacy"}, {"PACKAGE_PASSWORD": PASSWORD})
    assert isinstance(legacy, LegacySealer)
    sealed = make_sealer({"mode": "scoped", "open": True, "monthly": False, "scopes": []}, {"PACKAGE_MASTER_KEY": MASTER, "PACKAGE_PASSWORD": PASSWORD}, NOW)
    assert isinstance(sealed, ScopedSealer) and sealed.master == MASTER, "the master key wins over the password"
    fallback = make_sealer({"mode": "scoped", "open": True, "monthly": False, "scopes": []}, {"PACKAGE_PASSWORD": PASSWORD}, NOW)
    assert fallback.master == PASSWORD, "the existing secret is enough to start"
    with pytest.raises(ValueError, match="at least"):
        make_sealer({"mode": "scoped", "open": True, "monthly": False, "scopes": []}, {"PACKAGE_PASSWORD": "corta"}, NOW)
