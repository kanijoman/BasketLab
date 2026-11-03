"""The images of the teams in the publication (#717, 17a): the report index of a competition lists, besides its reports, the sealed file of the crest and the photos of each team
(mode ``images``), only for the competitions of the newest season and only when the publisher is given a source of images (a library call or a test never reaches for the network)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

from src.live_prep.package_sealing import ScopedSealer  # noqa: E402
from src.local_data.images_export import Source  # noqa: E402
from src.local_data.web_data import publish_web_data  # noqa: E402
from tests.test_local_web_data import FBCYL, FEB, MASTER, cheap_lineups, handler  # noqa: E402,F401  (fixtures)


class Nothing(Source):
    """A FEB that has no image and no identity for anyone."""

    def get(self, url):
        return None

    def length(self, url):
        return None

    def identity(self, team_id, player_id):
        return None, None

    def photo_url(self, uuid):
        return None

    def team_logo_url(self, team_id):
        return None


def _entries(tmp_path, manifest, collection):
    entry = next(r for r in manifest["reports"] if r["collection"] == collection)
    return json.loads((tmp_path / entry["file"]).read_text(encoding="utf-8"))["reports"]


def test_without_a_source_of_images_nothing_is_published_of_them(handler, tmp_path):
    manifest = publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB, FBCYL])
    assert all(e["mode"] != "images" for c in (FEB, FBCYL) for e in _entries(tmp_path, manifest, c)) and not (tmp_path / "images").exists()


def test_the_current_season_competitions_list_the_file_of_each_team_in_their_report_index_and_fbcyl_too(handler, tmp_path):
    manifest = publish_web_data(handler, tmp_path, ScopedSealer(MASTER, open_access=False), [FEB, FBCYL], image_source=Nothing())
    images = [e for e in _entries(tmp_path, manifest, FEB) if e["mode"] == "images"]
    assert sorted(e["team_id"] for e in images) == ["101", "102", "103", "104"] and all(e["file"].startswith("images/") and (tmp_path / e["file"]).is_file() for e in images)
    assert {w["scope"] for w in images[0]["wraps"]} >= {f"competicion:{FEB}", "club:101"}
    fbcyl = [e for e in _entries(tmp_path, manifest, FBCYL) if e["mode"] == "images"]                  # FBCYL has crest and photos too (#721), asked of the ESB by uuid
    assert sorted(e["team_id"] for e in fbcyl) == ["34001", "34002", "34003", "34004"] and all(e["file"].startswith("images/") for e in fbcyl)


def test_the_files_of_a_team_that_left_are_removed_and_the_rest_keep_their_bytes(handler, tmp_path):
    sealer = ScopedSealer(MASTER)
    first = publish_web_data(handler, tmp_path, sealer, [FEB], image_source=Nothing())
    before = {e["file"]: (tmp_path / e["file"]).read_bytes() for e in _entries(tmp_path, first, FEB) if e["mode"] == "images"}
    second = publish_web_data(handler, tmp_path, sealer, [FEB], image_source=Nothing())
    after = {e["file"]: (tmp_path / e["file"]).read_bytes() for e in _entries(tmp_path, second, FEB) if e["mode"] == "images"}
    assert after == before
    third = publish_web_data(handler, tmp_path, sealer, [FEB])                                   # no source: the images are not listed and their files go
    assert not list((tmp_path / "images").glob("*.json")) and all(e["mode"] != "images" for e in _entries(tmp_path, third, FEB))
