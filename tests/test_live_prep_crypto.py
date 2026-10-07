"""Package encryption envelope (AES-256-GCM + PBKDF2-SHA256).

Python (``cryptography``) encrypts in ``live_prep``; the tablet decrypts with WebCrypto.
The cross-check below runs the real WebCrypto implementation in Node when available.
"""

import base64
import json
import shutil
import subprocess
import textwrap

import pytest

from src.live_prep.package_crypto import (
    DecryptionError,
    decrypt_package,
    encrypt_package,
)

ITER = 1000  # low for test speed; production default is much higher


def test_roundtrip():
    env = encrypt_package('{"a": "ñ"}', "secreto", iterations=ITER)
    assert decrypt_package(env, "secreto") == '{"a": "ñ"}'


def test_envelope_format():
    env = encrypt_package("x", "pw", iterations=ITER)
    assert set(env) == {"v", "alg", "kdf", "iterations", "salt", "iv", "ciphertext"}
    assert env["v"] == 1 and env["alg"] == "AES-256-GCM" and env["kdf"] == "PBKDF2-SHA256"
    assert env["iterations"] == ITER
    assert len(base64.b64decode(env["salt"])) == 16
    assert len(base64.b64decode(env["iv"])) == 12


def test_fresh_salt_and_iv_each_time():
    a, b = encrypt_package("x", "pw", iterations=ITER), encrypt_package("x", "pw", iterations=ITER)
    assert a["salt"] != b["salt"] and a["iv"] != b["iv"] and a["ciphertext"] != b["ciphertext"]


def test_wrong_passphrase_is_rejected():
    env = encrypt_package("x", "pw", iterations=ITER)
    with pytest.raises(DecryptionError):
        decrypt_package(env, "other")


def test_tampered_ciphertext_is_rejected():
    env = encrypt_package("hello", "pw", iterations=ITER)
    raw = bytearray(base64.b64decode(env["ciphertext"]))
    raw[0] ^= 1
    env["ciphertext"] = base64.b64encode(bytes(raw)).decode()
    with pytest.raises(DecryptionError):
        decrypt_package(env, "pw")


def test_unsupported_envelope_version_is_rejected():
    env = encrypt_package("x", "pw", iterations=ITER)
    env["v"] = 99
    with pytest.raises(DecryptionError):
        decrypt_package(env, "pw")


def test_default_iterations_are_strong():
    from src.live_prep.package_crypto import DEFAULT_ITERATIONS
    assert DEFAULT_ITERATIONS >= 600_000


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_webcrypto_in_node_can_decrypt_python_envelope():
    """Compatibility with what the Android WebView will run (WebCrypto)."""
    env = encrypt_package('{"equipo": "Peñas"}', "contraseña", iterations=ITER)
    script = textwrap.dedent(
        """
        const { webcrypto } = require('node:crypto');
        const env = JSON.parse(process.argv[1]);
        const pw = process.argv[2];
        const b64 = s => Uint8Array.from(Buffer.from(s, 'base64'));
        (async () => {
          const key0 = await webcrypto.subtle.importKey(
            'raw', new TextEncoder().encode(pw), 'PBKDF2', false, ['deriveKey']);
          const key = await webcrypto.subtle.deriveKey(
            { name: 'PBKDF2', salt: b64(env.salt), iterations: env.iterations, hash: 'SHA-256' },
            key0, { name: 'AES-GCM', length: 256 }, false, ['decrypt']);
          const plain = await webcrypto.subtle.decrypt(
            { name: 'AES-GCM', iv: b64(env.iv) }, key, b64(env.ciphertext));
          process.stdout.write(new TextDecoder().decode(plain));
        })().catch(e => { console.error(String(e)); process.exit(1); });
        """
    )
    out = subprocess.run(
        ["node", "-e", script, json.dumps(env), "contraseña"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout == '{"equipo": "Peñas"}'
