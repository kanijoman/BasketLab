"""The identity links are consumed by Talent (#996): a FBCYL player LINKED (``linked``, never ``review``) to a FEB person is published with ``linked_to`` (her ``person_id`` is not rewritten),
inherits the bio of the FEB person (by the closest season, with ``bio_from`` saying where) and appears in a small sealed ``identities`` file (``links``: FBCYL id to FEB id; ``by_feb``: the FBCYL
competitions that hold rows of a FEB person) that the profile reads to put the trajectory together without opening every FBCYL competition."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_market_publish import FBCYL, LF2, MASTER, _by, _manifest, _open, _publish, _tree, connection  # noqa: E402,F401
from src.live_prep.package_scopes import open_sealed, scope_key  # noqa: E402
from src.market.contract import validate_talent_manifest  # noqa: E402
from src.market.external_bio import read_person_links  # noqa: E402
from src.market.season_rows import attach_bio  # noqa: E402

FBCYL_ID, FEB_ID = "fbcyl:34001-00", "feb:10100"
ROSTER = [{"person_id": FEB_ID, "season": "2025", "team_id": "101", "name": "ANA PRUEBA UNO CASTRO", "birth": "2004-05-06", "height": 178, "position": "Base", "nationality": "ESPAÑA", "formacion": True, "dorsal": 7}]


def _identities(out, manifest):
    entry = manifest["identities"]
    return json.loads(open_sealed(json.loads((out / entry["file"]).read_text(encoding="utf-8")), entry["wraps"], {"talent": scope_key(MASTER, "talent")}))


def test_a_linked_fbcyl_row_keeps_its_id_says_who_she_is_and_inherits_the_bio_of_the_feb_person(connection, tmp_path):
    manifest = _publish(connection, tmp_path, roster_rows=ROSTER, links={FBCYL_ID: FEB_ID})
    row = next(r for r in _open(tmp_path, _by(manifest, "Primera Nacional Femenina"))["rows"] if r["person_id"] == FBCYL_ID)
    assert row["linked_to"] == FEB_ID and row["league"] == "fbcyl"
    assert (row["birth"], row["height"], row["position"], row["nationality"], row["full_name"]) == ("2004-05-06", 178, "Base", "ESPAÑA", "ANA PRUEBA UNO CASTRO")
    assert row["bio_from"]["height"] == "2025:101" and row["formacion"] is None and row["dorsal"] is None          # the formation and the number are those of the FEB club, not of this team


def test_a_fbcyl_row_without_link_is_what_it_was(connection, tmp_path):
    manifest = _publish(connection, tmp_path, roster_rows=ROSTER)
    rows = _open(tmp_path, _by(manifest, "Primera Nacional Femenina"))["rows"]
    assert all(r["linked_to"] is None and r["birth"] is None for r in rows) and "identities" not in manifest


def test_identities_say_who_is_who_and_where_their_rows_are_and_the_manifest_still_satisfies_the_contract(connection, tmp_path):
    manifest = _publish(connection, tmp_path, roster_rows=ROSTER, links={FBCYL_ID: FEB_ID, "fbcyl:nobody": "feb:1"})
    validate_talent_manifest(manifest)
    assert manifest == _manifest(tmp_path)
    assert _identities(tmp_path, manifest) == {"format": 1, "links": {FBCYL_ID: FEB_ID}, "by_feb": {FEB_ID: ["fbcyl|1129-1|2026"]}}          # a link with no published row says nothing


def test_the_same_run_twice_keeps_every_byte_and_no_file_is_left_without_a_reference(connection, tmp_path):
    _publish(connection, tmp_path, roster_rows=ROSTER, links={FBCYL_ID: FEB_ID})
    before = _tree(tmp_path)
    _publish(connection, tmp_path, roster_rows=ROSTER, links={FBCYL_ID: FEB_ID})
    assert _tree(tmp_path) == before
    manifest = _publish(connection, tmp_path, roster_rows=ROSTER)                                                 # the link is gone: so is its file
    assert "identities" not in manifest and not [p for p in _tree(tmp_path) if "identities" in p]


def test_only_linked_links_are_read_and_a_missing_file_is_nobody(tmp_path):
    (tmp_path / "links").mkdir()
    link = lambda ext, status, feb: {"external": ext, "status": status, "feb": feb, "method": "name+club", "shared": []}
    (tmp_path / "links" / "fbcyl.json").write_text(json.dumps({"format": 1, "source": "fbcyl", "links": [link(FBCYL_ID, "linked", FEB_ID), link("fbcyl:u2", "review", None)]}), encoding="utf-8")
    assert read_person_links(tmp_path, "fbcyl") == {FBCYL_ID: FEB_ID}
    assert read_person_links(tmp_path / "nowhere", "fbcyl") == {}


def test_attach_bio_takes_the_roster_of_the_linked_person_and_never_of_an_unlinked_one():
    row = {"person_id": FBCYL_ID, "team_id": "7", "league": "fbcyl", "name": "A. B C"}
    (linked,) = attach_bio([row], ROSTER, "2026", linked={FBCYL_ID: FEB_ID})
    assert linked["linked_to"] == FEB_ID and linked["height"] == 178
    (alone,) = attach_bio([row], ROSTER, "2026")
    assert alone["linked_to"] is None and alone["height"] is None


def test_run_talent_data_reads_the_fbcyl_links_of_the_external_archive(tmp_path):
    import run_talent_data

    (tmp_path / "links").mkdir()
    (tmp_path / "links" / "fbcyl.json").write_text(json.dumps({"format": 1, "source": "fbcyl", "links": [{"external": FBCYL_ID, "status": "linked", "feb": FEB_ID, "method": "name+club", "shared": []}]}), encoding="utf-8")
    assert run_talent_data.read_links(tmp_path) == {FBCYL_ID: FEB_ID} and run_talent_data.read_links(tmp_path / "nowhere") == {}
