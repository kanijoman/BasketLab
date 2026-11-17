"""A REAL publication of a competition big enough for the whole preview (#949), for the browser e2e.

``tests/local_vectors/web_data`` is the small league of the fixtures (12 games): the preview needs ``MIN_POOL`` (30) scenarios, so the e2e only sees the forecast and the "few data" notice there. This
seals the rows and the calendar of the LF Challenge 2026-27 captured in ``tests/fixtures/forecast`` (39 games, 240 matches) exactly as ``publish_web_data`` does (``seal_file`` + ``ScopedSealer``, open
key in the index) into a directory, so a browser served from it opens it like the real ``web-data`` branch. Nothing is committed: the e2e builds it on each run.

    python tests/e2e_web/forecast_publication.py OUT_DIR
"""
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from src.live_prep.package_sealing import ScopedSealer  # noqa: E402
from src.local_data.contract import SCHEMA, validate_manifest  # noqa: E402
from src.local_data.team_reports import seal_file  # noqa: E402
from src.local_data.web_data import INDEX, ROWS, SECTIONS  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "forecast"
STEM = "lf_challenge_2026_2027"
SECRET = "e2e-forecast-master-secret"          # public on purpose: these are fixtures


def _read(name: str) -> dict:
    return json.loads(gzip.decompress((FIXTURES / f"{name}.json.gz").read_bytes()).decode("utf-8"))


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def publish(out_dir: Path) -> dict:
    """Write the sealed files and ``index.json`` of the competition; return the manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    sealer = ScopedSealer(SECRET, open_access=True)
    rows, calendar = _read(STEM), _read(f"{STEM}.calendar")
    name, scopes = rows["collection"], [f"competicion:{rows['collection']}"]
    entry = {"collection": name, "league": rows["league"], "games": rows["games"], "gender": rows["gender"], "category": "senior",
             **seal_file(out_dir, name, _dump(rows), scopes, sealer, None, ROWS)}
    cal = {"collection": name, "league": calendar["league"], "games": calendar["games"], **seal_file(out_dir, name, _dump(calendar), scopes, sealer, None, SECTIONS["calendar"])}
    manifest = {"schema": SCHEMA, "v": sealer.index_version, **sealer.index_extra(), "rows": [entry], **{s: [] for s in SECTIONS}, "reports": []}
    manifest["calendar"] = [cal]
    validate_manifest(manifest)                      # raises when the index breaks the contract
    (out_dir / INDEX).write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    publish(Path(sys.argv[1]))
