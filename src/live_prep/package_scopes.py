"""Packages encrypted by scope (issue #410): open access for the beta, paid scopes later, no re-encryption.

Every package (or round bundle) is encrypted once with its own random key (CEK, AES-256-GCM). The CEK is WRAPPED once for each scope
that may open it (``abierto``, ``club:<id>``, ``competicion:<collection>``, ``temporada:<year>``, ``mensual:<YYYY-MM>``...) with the
key of that scope. The envelope of the file is v2 and has no key derivation::

    {"v": 2, "alg": "AES-256-GCM", "iv": 12 bytes, "ciphertext": <data || 16-byte GCM tag>[, "z": "gzip"]}

and the wraps travel in the ``index.json`` entry of the file (``wraps: [{"scope", "iv", "key"}]``), so switching a scope off is
publishing the next index without it. Scope keys are HKDF-SHA256 of a master secret and the scope name: nothing is stored, the
invitation generator derives any key again and the key of ``abierto`` is published in the index while the beta is open.

An invitation is a token ``bl1.<base64url JSON {s: scope, k: key, e: expires|null}>`` (or the link ``basketlab-live://invite#<token>``).
Expiry is a convention of the app (a device without a server cannot impose it): the real cut is rotating the scope name.
"""

from __future__ import annotations

import base64
import gzip
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .package_crypto import ALG, COMPRESSIONS, DecryptionError

SCOPED_VERSION = 2
SCOPE_OPEN = "abierto"
INVITE_SCHEME = "basketlab-live"
TOKEN_PREFIX = "bl1."
_SALT = b"basketlab-live-scopes-v1"


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _from_b64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def scope_key(master: str, scope: str) -> bytes:
    """The 32-byte key of a scope: deterministic for a master secret and a scope name."""
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=_SALT, info=scope.encode("utf-8")).derive(master.encode("utf-8"))


def seal(plaintext: str, master: str, scopes: List[str], compress: bool = False) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    """``(envelope, wraps)``: the file content and the CEK wrapped for each of ``scopes`` (to put in the index entry of the file)."""
    cek, iv = AESGCM.generate_key(256), os.urandom(12)
    data = plaintext.encode("utf-8")
    if compress:
        data = gzip.compress(data, mtime=0)
    envelope = {"v": SCOPED_VERSION, "alg": ALG, "iv": _b64(iv), "ciphertext": _b64(AESGCM(cek).encrypt(iv, data, None)),
                **({"z": "gzip"} if compress else {})}
    wraps = []
    for scope in dict.fromkeys(scopes):
        wrap_iv = os.urandom(12)
        wraps.append({"scope": scope, "iv": _b64(wrap_iv),
                      "key": _b64(AESGCM(scope_key(master, scope)).encrypt(wrap_iv, cek, scope.encode("utf-8")))})
    return envelope, wraps


def open_sealed(envelope: Dict[str, Any], wraps: List[Dict[str, str]], scope_keys: Dict[str, bytes]) -> str:
    """Open a file with the keys of the scopes the reader has; the first wrap whose scope is among them is used."""
    if envelope.get("v") != SCOPED_VERSION or envelope.get("alg") != ALG:
        raise DecryptionError("Unsupported package envelope.")
    if envelope.get("z") is not None and envelope["z"] not in COMPRESSIONS:
        raise DecryptionError("Unsupported package compression.")
    try:
        cek = None
        for wrap in wraps:
            key = scope_keys.get(wrap["scope"])
            if key is not None:
                try:
                    cek = AESGCM(key).decrypt(base64.b64decode(wrap["iv"]), base64.b64decode(wrap["key"]), wrap["scope"].encode("utf-8"))
                    break
                except InvalidTag:
                    continue
        if cek is None:
            raise DecryptionError("No key of the reader opens this package.")
        plain = AESGCM(cek).decrypt(base64.b64decode(envelope["iv"]), base64.b64decode(envelope["ciphertext"]), None)
        return (gzip.decompress(plain) if envelope.get("z") == "gzip" else plain).decode("utf-8")
    except (InvalidTag, KeyError, ValueError, OSError) as exc:
        raise DecryptionError("Could not decrypt the package (wrong key or corrupted file).") from exc


def invite_token(master: str, scope: str, expires: Optional[str] = None) -> str:
    payload = {"s": scope, "k": _b64url(scope_key(master, scope)), "e": expires}
    return TOKEN_PREFIX + _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))


def invite_link(token: str) -> str:
    return f"{INVITE_SCHEME}://invite#{token}"


def parse_invite(text: str) -> Dict[str, Any]:
    """``{scope, key, expires}`` of a token or a link as it was pasted; ``ValueError`` when it is neither."""
    token = text.strip().rsplit("#", 1)[-1]
    if not token.startswith(TOKEN_PREFIX) or len(token) == len(TOKEN_PREFIX):
        raise ValueError("Not a BasketLab invitation.")
    try:
        payload = json.loads(_from_b64url(token[len(TOKEN_PREFIX):]))
        return {"scope": str(payload["s"]), "key": _from_b64url(payload["k"]), "expires": payload.get("e")}
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Not a BasketLab invitation.") from exc
