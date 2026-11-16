"""The published web-data written as a local export, for the studies (#938): ``scripts/web_data_dump.py``.

The rows of ``web-data`` are what ``run_local_export.py`` writes (``export_collection``), sealed per competition; while the beta is open the manifest carries the key of the open scope, so
they open without a password. The dump writes them in the layout of the local export (``index.json`` + one file per competition) so that ``npm run study:forecast`` and
``npm run study:projection`` read the published games, and the per-possession CSV next to them for ``scripts/pace_style_study.py``. Tested on the REAL sealed publication of the
vectors (``tests/local_vectors/web_data``, made with a public secret) and a per-possession CSV made by the exporter from a real game.
"""
import copy
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from db_helpers import new_mock_db

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import web_data_dump as dump  # noqa: E402
from src.live_prep.package_scopes import SCOPE_OPEN, seal  # noqa: E402
from src.local_data.possessions_export import export_possession_csv  # noqa: E402

VECTORS = ROOT / "tests" / "local_vectors" / "web_data"
SECRET = "vector-master-secret-for-the-web-tests"          # the public secret of the vectors (generate_web_data.py)
SAMPLE = ROOT / "src" / "JSON_samples" / "feb_game.json"
LF2 = "L_F_-2_2025_2026_Liga_Regular_B"
MANIFEST = json.loads((VECTORS / "index.json").read_text(encoding="utf-8"))


class WithFiles(dump.DirectorySource):
    """The publication of the vectors with some files (and manifest) replaced, as another publication would have them."""

    def __init__(self, root: Path, manifest: dict, extra: dict):
        super().__init__(root)
        self.manifest, self.extra = manifest, extra

    def read(self, path: str) -> bytes:
        if path == "index.json":
            return json.dumps(self.manifest).encode("utf-8")
        return self.extra[path] if path in self.extra else super().read(path)


def test_the_rows_open_with_the_open_key_of_the_manifest_and_are_written_as_a_local_export(tmp_path):
    index = dump.dump(dump.DirectorySource(VECTORS), tmp_path, min_games=0, pattern=".")
    published = {e["collection"]: e for e in MANIFEST["rows"]}
    assert sorted(e["name"] for e in index["collections"]) == sorted(published)
    for entry in index["collections"]:
        competition = json.loads((tmp_path / entry["file"]).read_text(encoding="utf-8"))
        assert competition["collection"] == entry["name"] and competition["team_rows"]
        assert entry["games"] == published[entry["name"]]["games"] and entry["gender"] == published[entry["name"]]["gender"]
        assert entry["league"] == competition["league"]
    assert json.loads((tmp_path / "index.json").read_text(encoding="utf-8")) == index


def test_only_the_competitions_asked_for_by_name_and_size(tmp_path):
    assert [e["name"] for e in dump.dump(dump.DirectorySource(VECTORS), tmp_path / "a", min_games=0, pattern="L_F_-2")["collections"]] == [LF2]
    assert dump.dump(dump.DirectorySource(VECTORS), tmp_path / "b", min_games=100, pattern=".")["collections"] == []


def test_a_closed_publication_has_no_open_key_and_cannot_be_dumped(tmp_path):
    closed = {k: v for k, v in MANIFEST.items() if k != "open_key"}
    with pytest.raises(SystemExit, match="open key"):
        dump.dump(WithFiles(VECTORS, closed, {}), tmp_path, min_games=0, pattern=".")


@pytest.fixture()
def possession_csv():
    """The per-possession CSV the publisher makes of two copies of a real game."""
    database = new_mock_db("dump")
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    database[LF2].insert_many([{**copy.deepcopy(sample), "_id": f"game-{n}"} for n in (1, 2)])
    handler = MagicMock()
    handler.repository.connection.get_collection.side_effect = lambda name: database[name]
    handler.connection.get_collection.side_effect = lambda name: database[name]
    return export_possession_csv(handler, LF2)


def test_the_per_possession_csv_of_a_competition_is_written_next_to_its_rows(tmp_path, possession_csv):
    envelope, wraps = seal(json.dumps(possession_csv), SECRET, [SCOPE_OPEN], compress=True)
    manifest = copy.deepcopy(MANIFEST)
    manifest["possession_csv"] = [{"collection": LF2, "file": "possession_csv/lf2.json", "wraps": wraps}]
    index = dump.dump(WithFiles(VECTORS, manifest, {"possession_csv/lf2.json": json.dumps(envelope).encode("utf-8")}), tmp_path, min_games=0, pattern=".")
    entry = next(e for e in index["collections"] if e["name"] == LF2)
    assert (tmp_path / entry["possession_csv"]).read_bytes().decode("utf-8") == possession_csv["csv"]
    assert all("possession_csv" not in e for e in index["collections"] if e["name"] != LF2)
