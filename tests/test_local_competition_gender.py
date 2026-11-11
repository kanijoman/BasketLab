"""The gender of each competition in the manifest (#843): the browser needs it to pick the calibrated win probability (``WP_BY_GENDER``: women's and men's margins do not spread alike).

It is read from what already says it, with the REAL catalogue (``config/competitions.json``): FEB by the label of the competition in ``COLLECTION_META`` or, without metadata, by the name of the
collection; FBCYL by the ``_gender`` its games carry or, without it, by the catalogue entry of its ESB group. A competition that says nothing has no gender (the browser uses the neutral defaults).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

from src.live_prep.package_sealing import ScopedSealer  # noqa: E402
from src.local_data.competition_gender import competition_genders  # noqa: E402
from src.local_data.web_data import publish_web_data  # noqa: E402
from src.services.competition_catalogue import DEFAULT_CATALOGUE, load_catalogue  # noqa: E402
from tests.test_local_web_data import FBCYL, FEB, MASTER, cheap_lineups, handler  # noqa: E402,F401  (fixtures)

CATALOGUE = load_catalogue(DEFAULT_CATALOGUE)


def _db(handler):
    return handler.connection.client["BASKETBALL"]


@pytest.mark.parametrize("label,expected", [("LF ENDESA", "F"), ("PRIMERA FEB", "M"), ("L.F.-2", "F"), ("SEGUNDA FEB", "M"), ("LF CHALLENGE", "F")])
def test_a_feb_collection_with_metadata_has_the_gender_of_its_competition_in_the_catalogue(handler, label, expected):
    _db(handler)["COLLECTION_META"].insert_one({"_id": FEB, "competition_label": label})
    assert competition_genders(handler, [FEB], CATALOGUE) == {FEB: expected}


@pytest.mark.parametrize("name,expected", [("PRIMERA_FEB_2026_Liga_Regular", "M"), ("LF_ENDESA_2026_2027_Liga_Regular", "F"), ("L_F_-2_2025_2026_Liga_Regular_B", "F")])
def test_without_metadata_the_name_of_the_collection_says_the_competition(handler, name, expected):
    assert competition_genders(handler, [name], CATALOGUE) == {name: expected}


def test_a_competition_that_is_not_in_the_catalogue_has_no_gender(handler):
    assert competition_genders(handler, ["TORNEO_X_2026_2027_Liga_Regular"], CATALOGUE) == {}


def test_an_older_season_of_a_paused_competition_keeps_its_gender(handler):
    paused = [{**e, "active": False} for e in CATALOGUE]
    assert competition_genders(handler, ["PRIMERA_FEB_2024_2025_Liga_Regular"], paused) == {"PRIMERA_FEB_2024_2025_Liga_Regular": "M"}


def test_fbcyl_says_its_gender_with_the_games_or_else_with_the_entry_of_its_group(handler):
    assert competition_genders(handler, [FBCYL], CATALOGUE) == {FBCYL: "F"}                      # the fixture games carry no ``_gender``: group 7298 of the catalogue is women's
    _db(handler)[FBCYL].update_many({}, {"$set": {"_gender": "M"}})
    assert competition_genders(handler, [FBCYL], CATALOGUE) == {FBCYL: "M"}                      # what the games say wins


def test_an_fbcyl_collection_without_games_gender_or_group_has_none(handler):
    assert competition_genders(handler, ["FBCYL_OTRO_GRUPO_2026_"], CATALOGUE) == {}


def test_the_rows_entry_of_the_manifest_has_the_gender_when_it_is_known(handler, tmp_path):
    manifest = publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB, FBCYL], genders={FEB: "F"})
    assert {e["collection"]: e.get("gender") for e in manifest["rows"]} == {FEB: "F", FBCYL: None}


def test_an_unchanged_publication_with_a_known_gender_keeps_the_bytes_of_the_rows(handler, tmp_path):
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB], genders={FEB: "F"})
    before = {p.name: p.read_bytes() for p in (tmp_path / "rows").glob("*.json")}
    publish_web_data(handler, tmp_path, ScopedSealer(MASTER), [FEB], genders={FEB: "F"})
    assert {p.name: p.read_bytes() for p in (tmp_path / "rows").glob("*.json")} == before
