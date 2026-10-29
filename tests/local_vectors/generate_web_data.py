"""Regenerate ``web_data/``: a REAL publication of ``publish_web_data`` over the small leagues of the fixtures (#328, #639).

The contract between the exporter (Python) and the browser (WebCrypto): the web tests (``frontend/src/webdata``) read the manifest, open the sealed
rows and reports with the open key the manifest publishes, and must find what the exporter produced. Sealing is random, so the directory is
committed and only regenerated on demand (``python tests/local_vectors/generate_web_data.py``); ``test_local_vectors.py`` checks that it still
opens and says what the exporter says today. The secret is public on purpose: these are fixtures.
"""
import shutil
import sys
from pathlib import Path

import mongomock
import pymongo

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(Path(__file__).resolve().parent)]

import fbcyl_games  # noqa: E402
import games  # noqa: E402

from src.api import deps  # noqa: E402
from src.live_prep.package_sealing import ScopedSealer  # noqa: E402
from src.local_data.web_data import publish_web_data  # noqa: E402

OUT = Path(__file__).resolve().parent / "web_data"
SECRET = "vector-master-secret-for-the-web-tests"
FEB = "L_F_-2_2025_2026_Liga_Regular_B"
FBCYL = "FBCYL_1\u00aa_FASE-GRUPO_A-1_2026_"


def fixture_handler():
    """A handler over a mongomock database with both leagues (the real ``deps._create_handler`` with the client swapped)."""
    pymongo.MongoClient = mongomock.MongoClient
    deps._create_handler.cache_clear()
    handler = deps._create_handler()
    db = handler.connection.client["BASKETBALL"]
    db[FEB].insert_many(games.build_games())
    db[FBCYL].insert_many(fbcyl_games.build_games())
    return handler


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    manifest = publish_web_data(fixture_handler(), OUT, ScopedSealer(SECRET, open_access=True), [FEB, FBCYL])
    print("wrote", OUT, sum(1 for p in OUT.rglob("*") if p.is_file()), "files,", len(manifest["rows"]), "competitions")


if __name__ == "__main__":
    main()
