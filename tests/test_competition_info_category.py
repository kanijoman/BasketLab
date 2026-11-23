"""Issue #1055: the index says the CATEGORY of each competition (senior or formación, and the age group), so the app can tell the teams of a club apart.

Bug (feedback of 0.7.0): a team of interest was recognised by id OR name; a club has the same name in all its categories, so a favourite of the senior team marked the matches of its
cadete and júnior teams. ``level`` says nothing (it is null in every youth competition and is the same for U16 and U18), so the index carries ``category`` and ``age_group``.
"""
from unittest.mock import MagicMock

import pytest

from src.live_prep.competition_info import competition_infos, fbcyl_infos, normalize_catalog, public
from src.services.competition_catalogue import DEFAULT_CATALOGUE, load_catalogue

CLUB = "9001"
CATALOGUE = load_catalogue(DEFAULT_CATALOGUE)


def fbcyl_info(group):
    return fbcyl_infos({"FBCYL_X": group}, CATALOGUE, lambda g: [], [CLUB])["FBCYL_X"]


def entry_of(group):
    return next(e for e in CATALOGUE if e.get("league") == "fbcyl" and e["fbcyl"]["competition_id"] == group)


def group_with(category, age_group=None):
    return next(e["fbcyl"]["competition_id"] for e in CATALOGUE if e.get("league") == "fbcyl" and e.get("category") == category and e.get("age_group") == age_group)


def test_a_youth_group_of_fbcyl_says_formacion_and_its_age_group():
    group = group_with("formacion", "U16")
    assert (fbcyl_info(group)["category"], fbcyl_info(group)["age_group"]) == ("formacion", "U16")


@pytest.mark.parametrize("group", [group_with("senior"), "7298"])        # 7298 = 1ª División Femenina, a senior league whose catalogue entry says no category
def test_a_senior_group_of_fbcyl_says_senior_and_no_age_group(group):
    info = fbcyl_info(group)
    assert (info["category"], info["age_group"]) == ("senior", None) and public(info)["category"] == "senior"


def test_a_feb_competition_is_senior_unless_the_catalogue_says_otherwise():
    db = MagicMock()
    db.repository.connection.get_collection.return_value.find_one.return_value = None
    catalog = normalize_catalog([{"competition": "LF X", "gender": "F"}, {"competition": "JR Y", "gender": "F", "category": "formacion", "age_group": "U18"}])
    infos = {n: competition_infos(db, [n], catalog, [CLUB])[n] for n in ("LF X", "JR Y")}
    assert (infos["LF X"]["category"], infos["LF X"]["age_group"]) == ("senior", None)
    assert (infos["JR Y"]["category"], infos["JR Y"]["age_group"]) == ("formacion", "U18")
