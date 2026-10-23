"""The old index ``header_local_team_name_1`` of the FEB collections (issue #137).

It was built on ``HEADER.localTeam.teamName``, a field FEB games do not have (the index code was corrected to ``HEADER.TEAM.name``), but the collections created before keep it:
it is useless and costs space on the free Atlas tier. ``python run_drop_legacy_indexes.py`` lists it (dry run) and drops it with ``--apply``, never touching anything else.
"""
import pytest
from db_helpers import new_mock_db

from src.services.legacy_indexes import drop_legacy_indexes, run

LEGACY_KEY = [("HEADER.localTeam.teamName", 1)]


def collection(name="FEB_X"):
    col = new_mock_db("legacy")[name]
    col.insert_one({"_id": 1, "HEADER": {"TEAM": [{"id": "1", "name": "A"}]}})
    return col


def names(col):
    return {i["name"] for i in col.list_indexes()}


def test_a_dry_run_says_what_it_would_drop_and_drops_nothing():
    col = collection()
    col.create_index(LEGACY_KEY, name="header_local_team_name_1")
    result = drop_legacy_indexes(col)
    assert result["found"] == ["header_local_team_name_1"] and result["dropped"] == []
    assert "header_local_team_name_1" in names(col)


def test_apply_drops_the_legacy_index_and_keeps_every_other_one():
    col = collection()
    col.create_index(LEGACY_KEY, name="header_local_team_name_1")
    col.create_index([("HEADER.TEAM.id", 1)], name="team_id_1")
    col.create_index([("HEADER.TEAM.name", 1)], name="header_team_name_1")
    result = drop_legacy_indexes(col, apply=True)
    assert result["dropped"] == ["header_local_team_name_1"]
    assert names(col) == {"_id_", "team_id_1", "header_team_name_1"}


def test_an_index_with_that_name_on_another_field_is_not_the_legacy_one_and_is_left_alone_regression():
    """The name is not enough: a collection where someone put ``header_local_team_name_1`` on a real field keeps it."""
    col = collection()
    col.create_index([("HEADER.TEAM.name", 1)], name="header_local_team_name_1")
    result = drop_legacy_indexes(col, apply=True)
    assert result["found"] == [] and result["dropped"] == []
    assert "header_local_team_name_1" in names(col)


def test_it_is_idempotent_and_a_collection_without_the_index_is_fine():
    col = collection()
    col.create_index(LEGACY_KEY, name="header_local_team_name_1")
    assert drop_legacy_indexes(col, apply=True)["dropped"] == ["header_local_team_name_1"]
    again = drop_legacy_indexes(col, apply=True)
    assert again["found"] == [] and again["dropped"] == []
    assert names(collection("FEB_Y")) == {"_id_"} and drop_legacy_indexes(collection("FEB_Z"), apply=True)["found"] == []


def test_it_says_whether_the_index_that_replaces_it_exists():
    col = collection()
    col.create_index(LEGACY_KEY, name="header_local_team_name_1")
    assert drop_legacy_indexes(col)["replacement"] is False
    col.create_index([("HEADER.TEAM.name", 1)], name="header_team_name_1")
    assert drop_legacy_indexes(col)["replacement"] is True


def test_the_run_goes_over_the_feb_collections_only_and_reports_each_one():
    db = new_mock_db("legacy_run")
    for name in ("FEB_A", "FEB_B", "FBCYL_C", "COLLECTION_META"):
        db[name].insert_one({"_id": 1})
    db["FEB_A"].create_index(LEGACY_KEY, name="header_local_team_name_1")
    db["FBCYL_C"].create_index(LEGACY_KEY, name="header_local_team_name_1")      # not a FEB collection: not touched
    report = run(db, apply=True)
    assert set(report) == {"FEB_A", "FEB_B"} and report["FEB_A"]["dropped"] == ["header_local_team_name_1"]
    assert "header_local_team_name_1" in {i["name"] for i in db["FBCYL_C"].list_indexes()}


def test_the_run_can_be_limited_to_one_collection():
    db = new_mock_db("legacy_one")
    for name in ("FEB_A", "FEB_B"):
        db[name].insert_one({"_id": 1})
        db[name].create_index(LEGACY_KEY, name="header_local_team_name_1")
    assert set(run(db, apply=True, only="FEB_B")) == {"FEB_B"}
    assert "header_local_team_name_1" in {i["name"] for i in db["FEB_A"].list_indexes()}


def test_a_collection_that_does_not_exist_is_an_error_not_a_silent_nothing():
    with pytest.raises(ValueError, match="FEB_NOPE"):
        run(new_mock_db("legacy_missing"), only="FEB_NOPE")
