"""Regenerate ``web_data_ext/``: a REAL publication of ``publish_external`` over two external sources (#884, PR C).

REAL FEB games badged as the source (``tests/market_helpers.FixtureSource``: the real sample game, whose play-by-play and box reconcile, and the 12 games of the fixture league, which do not) go through the whole
chain: refresh of each source into its archive, then the publication. FIBA works on its last run (18/11/2026); NCAA worked the day before and FAILS on the last one, so its ``last_ok`` is 17/11 and the web can say
«data from 17/11». The secret is the one of ``web_data``, so one open key opens both publications; it is public on purpose: these are fixtures. Sealing is random: the directory is committed and only regenerated
on demand (``python tests/local_vectors/generate_web_data_ext.py``); ``test_local_web_ext_vectors.py`` checks that it still opens and says what the exporter says today.
"""
import json
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(HERE), str(HERE.parent)]

from market_helpers import FixtureSource  # noqa: E402
from mongomock_handler import mongomock_handler  # noqa: E402

import mongomock  # noqa: E402

from src.external import registry  # noqa: E402
from src.external.publish import publish_external  # noqa: E402
from src.external.refresh import refresh_source  # noqa: E402
from src.live_prep.package_sealing import ScopedSealer  # noqa: E402
from src.services.competition_catalogue import load_catalogue  # noqa: E402

OUT = HERE / "web_data_ext"
SECRET = "vector-master-secret-for-the-web-tests"
FIBA = "FIBA_U18_EuroBasket_2026_"
NCAA = "NCAA_D1_2026_SEC"
DAY = datetime(2026, 11, 17, 7, 0, tzinfo=timezone.utc)
ENTRIES = [
    {"competition": "U18 EuroBasket", "season_label": "2026", "season_value": "2026", "league": "fiba", "division": "U18", "gender": "F", "fiba": {"event": "fiba-u18-eurobasket-test"}},
    {"competition": "D1", "season_label": "2026/2027", "season_value": "2026", "league": "ncaa", "division": "D1", "gender": "M", "conference": "SEC", "ncaa": {"conference_id": "23"}},
]


def build(out_dir: Path) -> dict:
    """The publication in ``out_dir`` (returns its manifest): FIBA fresh on 18/11, NCAA good on 17/11 and failed on 18/11."""
    saved = dict(registry.SOURCES)
    registry.SOURCES.clear()
    work = Path(tempfile.mkdtemp(prefix="web-data-ext-"))
    try:
        catalogue_path = work / "competitions.json"
        catalogue_path.write_text(json.dumps({"competitions": ENTRIES}), encoding="utf-8")
        catalogue = load_catalogue(catalogue_path)
        registry.register(FixtureSource("fiba"))
        ncaa = registry.register(FixtureSource("ncaa"))
        archive = work / "archive-ext"
        db = lambda: mongomock.MongoClient()["BASKETBALL"]  # noqa: E731 - one database per run, as each job has its own
        refresh_source("ncaa", catalogue, db(), archive, DAY)
        ncaa.boom = "NCAA changed its page again"
        refresh_source("ncaa", catalogue, db(), archive, DAY + timedelta(days=1))
        refresh_source("fiba", catalogue, db(), archive, DAY + timedelta(days=1))
        return publish_external(archive, out_dir, catalogue, mongomock_handler(), ScopedSealer(SECRET, open_access=True))
    finally:
        registry.SOURCES.clear()
        registry.SOURCES.update(saved)
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    manifest = build(OUT)
    print("wrote", OUT, sum(1 for p in OUT.rglob("*") if p.is_file()), "files,", len(manifest["rows"]), "competitions,", len(manifest["sources"]), "sources")


if __name__ == "__main__":
    main()
