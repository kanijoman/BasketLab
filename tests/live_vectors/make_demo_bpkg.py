"""One-off: write tests/live_vectors/demo.bpkg, the demo preparation package encrypted with the
fixture passphrase. The file is COMMITTED (random salt/iv: do not regenerate in CI); it lets the
Python and the WebCrypto (app) implementations be checked against the very same bytes.

    python tests/live_vectors/make_demo_bpkg.py
"""
import json
from pathlib import Path

from src.live_prep.package_crypto import encrypt_package

ROOT = Path(__file__).resolve().parents[2]
PASSPHRASE = "clave-de-prueba-1"

if __name__ == "__main__":
    vectors = json.loads((ROOT / "tests/live_vectors/vectors.json").read_text(encoding="utf-8"))
    envelope = encrypt_package(vectors["engine"]["package"], PASSPHRASE)
    (ROOT / "tests/live_vectors/demo.bpkg").write_text(json.dumps(envelope, separators=(",", ":")), encoding="utf-8")
    print("written tests/live_vectors/demo.bpkg")
