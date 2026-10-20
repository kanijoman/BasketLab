"""One-off: write tests/live_vectors/demo_scoped.json, the demo package and a demo round sealed BY SCOPE (issue #410). COMMITTED (random keys
and ivs: do not regenerate in CI); it lets the Python and the WebCrypto (app) implementations be checked against the very same bytes.

    python tests/live_vectors/make_demo_scoped.py
"""
import base64
import json
from pathlib import Path

from src.live_prep.package_scopes import SCOPE_OPEN, invite_link, invite_token, scope_key, seal

ROOT = Path(__file__).resolve().parents[2]
MASTER = "clave-maestra-de-prueba"
SCOPES = [SCOPE_OPEN, "club:1008631", "competicion:DEMO_2026"]

if __name__ == "__main__":
    vectors = json.loads((ROOT / "tests/live_vectors/vectors.json").read_text(encoding="utf-8"))
    package = vectors["engine"]["package"]
    envelope, wraps = seal(package, MASTER, SCOPES)
    round_plain = json.dumps({"v": 1, "collection": "DEMO_2026", "round": 4, "matches": []}, sort_keys=True, separators=(",", ":"))
    round_envelope, round_wraps = seal(round_plain, MASTER, SCOPES, compress=True)
    out = {
        "open_key": base64.b64encode(scope_key(MASTER, SCOPE_OPEN)).decode("ascii"),
        "package": {"file": json.dumps(envelope, separators=(",", ":")), "wraps": wraps},
        "round": {"file": json.dumps(round_envelope, separators=(",", ":")), "wraps": round_wraps, "plaintext": round_plain},
        "invitations": {scope: {"token": invite_token(MASTER, scope, "2027-06-30"), "link": invite_link(invite_token(MASTER, scope, "2027-06-30"))}
                        for scope in ("club:1008631", "club:999")},
    }
    (ROOT / "tests/live_vectors/demo_scoped.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("written tests/live_vectors/demo_scoped.json")
