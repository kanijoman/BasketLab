"""Packages encrypted by scope (issue #410): one random key per package, wrapped once for every scope that may open it.

Beta users open the ``abierto`` scope with a key published in the index (no password); when the key is switched on, only the scopes of
the people who pay (club, competition, season, month) wrap the new packages and the beta users get an invitation. Nothing is
re-encrypted: the wraps live in the index, the file is the same.
"""
import base64
import json

import pytest

from src.live_prep.package_crypto import DecryptionError
from src.live_prep.package_scopes import (
    INVITE_SCHEME, SCOPE_OPEN, invite_link, invite_token, open_sealed, parse_invite, scope_key, seal,
)

MASTER = "clave-maestra-de-prueba"
PLAIN = json.dumps({"hello": "mundo", "n": list(range(200))})


def keys(*scopes, master=MASTER):
    return {s: scope_key(master, s) for s in scopes}


def test_a_scope_key_is_deterministic_per_master_and_scope():
    assert scope_key(MASTER, "club:1") == scope_key(MASTER, "club:1") and len(scope_key(MASTER, "club:1")) == 32
    assert scope_key(MASTER, "club:1") != scope_key(MASTER, "club:2")
    assert scope_key(MASTER, "club:1") != scope_key("otra-maestra", "club:1")


def test_every_scope_of_the_wraps_opens_the_package_and_a_scope_that_is_not_there_does_not():
    envelope, wraps = seal(PLAIN, MASTER, [SCOPE_OPEN, "club:1", "mensual:2026-11"])
    assert envelope["v"] == 2 and [w["scope"] for w in wraps] == [SCOPE_OPEN, "club:1", "mensual:2026-11"]
    for scope in (SCOPE_OPEN, "club:1", "mensual:2026-11"):
        assert open_sealed(envelope, wraps, keys(scope)) == PLAIN
    with pytest.raises(DecryptionError):
        open_sealed(envelope, wraps, keys("club:2"))
    with pytest.raises(DecryptionError):
        open_sealed(envelope, wraps, keys("club:1", master="otra-maestra"))


def test_the_file_is_the_same_whatever_the_scopes_so_switching_the_open_scope_off_needs_no_re_encryption():
    envelope, wraps = seal(PLAIN, MASTER, [SCOPE_OPEN, "club:1"])
    without_open = [w for w in wraps if w["scope"] != SCOPE_OPEN]
    assert open_sealed(envelope, without_open, keys("club:1")) == PLAIN
    with pytest.raises(DecryptionError):
        open_sealed(envelope, without_open, keys(SCOPE_OPEN))


def test_a_wrap_is_bound_to_its_scope():
    """A wrap moved under another scope name does not open: the scope is authenticated data."""
    envelope, wraps = seal(PLAIN, MASTER, ["club:1"])
    forged = [{**wraps[0], "scope": "club:2"}]
    with pytest.raises(DecryptionError):
        open_sealed(envelope, forged, keys("club:2"))


def test_compressed_bundles_are_compressed_before_encrypting():
    big = json.dumps({"x": "a" * 20000})
    plain_env, _ = seal(big, MASTER, ["club:1"])
    zipped_env, wraps = seal(big, MASTER, ["club:1"], compress=True)
    assert zipped_env["z"] == "gzip" and "z" not in plain_env
    assert len(zipped_env["ciphertext"]) < len(plain_env["ciphertext"]) / 5
    assert open_sealed(zipped_env, wraps, keys("club:1")) == big


def test_each_package_has_its_own_key():
    a, wa = seal(PLAIN, MASTER, ["club:1"])
    b, wb = seal(PLAIN, MASTER, ["club:1"])
    assert a["ciphertext"] != b["ciphertext"] and wa[0]["key"] != wb[0]["key"]


def test_an_unsupported_envelope_is_refused():
    envelope, wraps = seal(PLAIN, MASTER, ["club:1"])
    with pytest.raises(DecryptionError):
        open_sealed({**envelope, "v": 1}, wraps, keys("club:1"))


def test_an_invitation_carries_the_key_of_a_scope_in_a_token_and_a_link():
    token = invite_token(MASTER, "club:1", expires="2026-12-31")
    assert token.startswith("bl1.") and "=" not in token
    assert parse_invite(token) == {"scope": "club:1", "key": scope_key(MASTER, "club:1"), "expires": "2026-12-31"}
    link = invite_link(token)
    assert link == f"{INVITE_SCHEME}://invite#{token}" and parse_invite(link) == parse_invite(token)
    assert parse_invite(f"  {link}\n")["scope"] == "club:1"                        # as pasted from a chat
    assert parse_invite(invite_token(MASTER, "club:1"))["expires"] is None


@pytest.mark.parametrize("bad", ["", "hola", "bl1.", "bl1.@@@", "bl2." + base64.urlsafe_b64encode(b"{}").decode().rstrip("=")])
def test_a_text_that_is_not_an_invitation_is_refused(bad):
    with pytest.raises(ValueError):
        parse_invite(bad)


def test_the_committed_demo_fixture_opens_with_python_as_the_app_opens_it():
    """tests/live_vectors/demo_scoped.json is read by the app tests (WebCrypto) too: the very same bytes."""
    from pathlib import Path
    demo = json.loads((Path(__file__).parent / "live_vectors/demo_scoped.json").read_text(encoding="utf-8"))
    package = json.loads((Path(__file__).parent / "live_vectors/vectors.json").read_text(encoding="utf-8"))["engine"]["package"]
    sealed = demo["package"]
    assert open_sealed(json.loads(sealed["file"]), sealed["wraps"], {SCOPE_OPEN: base64.b64decode(demo["open_key"])}) == package
    club = parse_invite(demo["invitations"]["club:1008631"]["link"])
    assert open_sealed(json.loads(sealed["file"]), sealed["wraps"], {club["scope"]: club["key"]}) == package
    other = parse_invite(demo["invitations"]["club:999"]["token"])
    with pytest.raises(DecryptionError):
        open_sealed(json.loads(sealed["file"]), sealed["wraps"], {other["scope"]: other["key"]})
