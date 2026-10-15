"""Package encryption envelope: AES-256-GCM, key derived with PBKDF2-SHA256.

The Drive folder is link-shared, so packages are encrypted; the tablet decrypts with
WebCrypto using the same parameters. Envelope (all binary fields base64)::

    {"v": 1, "alg": "AES-256-GCM", "kdf": "PBKDF2-SHA256", "iterations": N,
     "salt": 16 bytes, "iv": 12 bytes, "ciphertext": <data || 16-byte GCM tag>}

A bundle of packages (issue #286) is compressed BEFORE it is encrypted (ciphertext does not compress) and the envelope says so with
``"z": "gzip"``; a plain envelope has no ``z``. An app that predates ``z`` only ever reads plain ones.
"""

from __future__ import annotations

import base64
import gzip
import os
from typing import Any, Dict

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ENVELOPE_VERSION = 1
DEFAULT_ITERATIONS = 600_000
ALG = "AES-256-GCM"
KDF = "PBKDF2-SHA256"
COMPRESSIONS = ("gzip",)


class DecryptionError(ValueError):
    """Wrong passphrase, tampered data or unsupported envelope."""


def _derive_key(passphrase: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return kdf.derive(passphrase.encode("utf-8"))


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def encrypt_package(plaintext: str, passphrase: str, iterations: int = DEFAULT_ITERATIONS, compress: bool = False) -> Dict[str, Any]:
    salt, iv = os.urandom(16), os.urandom(12)
    key = _derive_key(passphrase, salt, iterations)
    data = plaintext.encode("utf-8")
    if compress:
        data = gzip.compress(data, mtime=0)
    ciphertext = AESGCM(key).encrypt(iv, data, None)
    return {
        "v": ENVELOPE_VERSION, "alg": ALG, "kdf": KDF, "iterations": iterations,
        "salt": _b64(salt), "iv": _b64(iv), "ciphertext": _b64(ciphertext), **({"z": "gzip"} if compress else {}),
    }


def decrypt_package(envelope: Dict[str, Any], passphrase: str) -> str:
    if envelope.get("v") != ENVELOPE_VERSION or envelope.get("alg") != ALG or envelope.get("kdf") != KDF:
        raise DecryptionError("Unsupported package envelope.")
    if envelope.get("z") is not None and envelope["z"] not in COMPRESSIONS:
        raise DecryptionError("Unsupported package compression.")
    try:
        salt = base64.b64decode(envelope["salt"])
        iv = base64.b64decode(envelope["iv"])
        data = base64.b64decode(envelope["ciphertext"])
        key = _derive_key(passphrase, salt, int(envelope["iterations"]))
        plain = AESGCM(key).decrypt(iv, data, None)
        return (gzip.decompress(plain) if envelope.get("z") == "gzip" else plain).decode("utf-8")
    except (InvalidTag, KeyError, ValueError, OSError) as exc:
        raise DecryptionError("Could not decrypt the package (wrong passphrase or corrupted file).") from exc
