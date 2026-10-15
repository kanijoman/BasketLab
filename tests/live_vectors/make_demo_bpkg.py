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
    # the compressed bundle of a round (issue #286): three matches, the club's in the middle, a package from each of its two teams
    matches = [{"match": {"code": code, "start": f"2026-10-17T{hour}:00", "round": 4,
                          "home": {"id": h, "name": f"EQ {h}"}, "away": {"id": a, "name": f"EQ {a}"}},
                "own_id": own, "rival_id": other, "is_club": club, "package": vectors["engine"]["package"]}
               for code, hour, h, a, club in (("101", "12", "11", "12", False), ("102", "17", "1008631", "1008898", True), ("103", "19", "31", "32", False))
               for own, other in ((h, a), (a, h))]
    bundle = {"v": 1, "collection": "DEMO_2026", "round": 4, "matches": matches}
    round_envelope = encrypt_package(json.dumps(bundle, sort_keys=True, ensure_ascii=False, separators=(",", ":")), PASSPHRASE, compress=True)
    (ROOT / "tests/live_vectors/demo_round.bpkgz").write_text(json.dumps(round_envelope, separators=(",", ":")), encoding="utf-8")
    print("written tests/live_vectors/demo_round.bpkgz")
