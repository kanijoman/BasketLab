"""Package encryption envelope: AES-256-GCM, key derived with PBKDF2-SHA256.

The Drive folder is link-shared, so packages are encrypted; the tablet decrypts with
WebCrypto using the same parameters. Envelope (all binary fields base64)::

    {"v": 1, "alg": "AES-256-GCM", "kdf": "PBKDF2-SHA256", "iterations": N,
     "salt": 16 bytes, "iv": 12 bytes, "ciphertext": <data || 16-byte GCM tag>}
"""

from __future__ import annotations

import base64
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


class DecryptionError(ValueError):
    """Wrong passphrase, tampered data or unsupported envelope."""


def _derive_key(passphrase: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return kdf.derive(passphrase.encode("utf-8"))


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def encrypt_package(plaintext: str, passphrase: str, iterations: int = DEFAULT_ITERATIONS) -> Dict[str, Any]:
    salt, iv = os.urandom(16), os.urandom(12)
    key = _derive_key(passphrase, salt, iterations)
    ciphertext = AESGCM(key).encrypt(iv, plaintext.encode("utf-8"), None)
    return {
        "v": ENVELOPE_VERSION, "alg": ALG, "kdf": KDF, "iterations": iterations,
        "salt": _b64(salt), "iv": _b64(iv), "ciphertext": _b64(ciphertext),
    }


def decrypt_package(envelope: Dict[str, Any], passphrase: str) -> str:
    if envelope.get("v") != ENVELOPE_VERSION or envelope.get("alg") != ALG or envelope.get("kdf") != KDF:
        raise DecryptionError("Unsupported package envelope.")
    try:
        salt = base64.b64decode(envelope["salt"])
        iv = base64.b64decode(envelope["iv"])
        data = base64.b64decode(envelope["ciphertext"])
        key = _derive_key(passphrase, salt, int(envelope["iterations"]))
        return AESGCM(key).decrypt(iv, data, None).decode("utf-8")
    except (InvalidTag, KeyError, ValueError) as exc:
        raise DecryptionError("Could not decrypt the package (wrong passphrase or corrupted file).") from exc
