"""Regenerate ``talent_data/``: a REAL publication of ``publish_talent_data`` over the small leagues of the fixtures (#878).

The contract between the exporter (Python) and the browser (WebCrypto) for BasketLab Talent: the web tests (``frontend/src/market``) read the manifest, open the sealed rows with the open key the
manifest publishes and must find what the exporter produced. Sealing is random, so the directory is committed and only regenerated on demand (``python tests/local_vectors/generate_talent_data.py``);
``tests/test_market_vectors.py`` checks that it still opens and says what the exporter says today. The secret is public on purpose: these are fixtures.
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
from src.market.publish import publish_talent_data  # noqa: E402

OUT = Path(__file__).resolve().parent / "talent_data"
SECRET = "vector-master-secret-for-the-talent-tests"
FEB = "L_F_-2_2025_2026_Liga_Regular_B"
FBCYL = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"
CATALOGUE = [
    {"competition": "L.F.-2", "league": "feb", "level": 3, "gender": "F", "active": True, "packages": True},
    {"league": "fbcyl", "competition": "1ª FASE-GRUPO A-1", "season_value": "2026", "season_label": "2026", "note": "Primera Nacional Femenina, grupo A-1", "active": True,
     "fbcyl": {"competition_id": "7298", "category": "1129", "gender": "F", "territory": "1"}},
]
ROSTER = [
    {"person_id": "feb:10100", "season": "2025", "team_id": "101", "name": "ANA PRUEBA UNO", "birth": "2004-05-06", "height": 178, "position": "Base", "nationality": "ESPAÑA", "formacion": True, "dorsal": 7},
    {"person_id": "feb:10200", "season": "2025", "team_id": "102", "name": "BEA PRUEBA DOS", "birth": "2001-11-20", "height": 185, "position": "Alero", "nationality": "ESPAÑA", "formacion": False, "dorsal": 9},
]


def fixture_connection():
    pymongo.MongoClient = mongomock.MongoClient
    deps._create_handler.cache_clear()
    handler = deps._create_handler()
    db = handler.connection.client["BASKETBALL"]
    db[FEB].insert_many(games.build_games())
    db["COLLECTION_META"].insert_one({"_id": FEB, "league": "FEB", "competition_label": "L.F.-2", "season_value": "2025", "season_label": "2025/2026", "group_label": "Liga Regular · B"})
    db[FBCYL].insert_many(fbcyl_games.build_games())
    return handler.connection


def main() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    manifest = publish_talent_data(fixture_connection(), OUT, ScopedSealer(SECRET, open_access=True), [FEB, FBCYL], CATALOGUE, roster_rows=ROSTER)
    print(f"{len(manifest['competitions'])} competitions written to {OUT}")


if __name__ == "__main__":
    main()
