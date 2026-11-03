"""The comparison of the archive with Atlas (issue #724, step 1): before Atlas is switched off, what it holds must be in the archive.

It reads Atlas and ONLY reads it: the connection is wrapped so that anything that is not a listing of names or a projected ``find`` raises (a bug can never write).
The games are compared by ``_id`` (the archive restores them with the ids they have) and by whether they carry the current ``DERIVED``.
"""
import pytest

from src.local_data.atlas_compare import ReadOnly, compare, render_markdown
from src.pbp.game_derived import DERIVED_VERSION
from tests.db_helpers import new_mock_db

FEB = "PRIMERA_FEB_2026_2027_Liga_Regular_Unico"
OLD = "PRIMERA_FEB_2025_2026_Liga_Regular_Unico"


def _fill(db, name, ids, derived=DERIVED_VERSION):
    for i in ids:
        doc = {"_id": i, "HEADER": {"id": i}}
        if derived is not None:
            doc["DERIVED"] = {"v": derived}
        db[name].insert_one(doc)


def _row(report, name):
    return next(r for r in report if r["collection"] == name)


def test_a_game_only_atlas_has_is_reported_by_id_and_makes_the_comparison_unsafe():
    archive, atlas = new_mock_db("a"), new_mock_db("b")
    _fill(archive, FEB, ["g1", "g2"])
    _fill(atlas, FEB, ["g1", "g2", "g3"])
    row = _row(compare(archive, atlas), FEB)
    assert row["only_atlas"] == ["g3"] and row["only_archive"] == []
    assert (row["atlas"], row["archive"]) == (3, 2)
    assert "g3" in render_markdown(compare(archive, atlas))


def test_what_only_the_archive_has_is_expected_and_not_a_problem():
    archive, atlas = new_mock_db("a"), new_mock_db("b")
    _fill(archive, FEB, ["g1"])
    _fill(archive, OLD, ["o1", "o2"])                  # older seasons live only in the archive (Atlas never had them)
    _fill(atlas, FEB, ["g1"])
    report = compare(archive, atlas)
    assert _row(report, OLD)["atlas"] == 0 and _row(report, OLD)["only_archive"] == ["o1", "o2"]
    assert render_markdown(report).startswith("## ✅")


def test_a_collection_that_only_atlas_has_is_reported_whole():
    archive, atlas = new_mock_db("a"), new_mock_db("b")
    _fill(atlas, FEB, ["g1"])
    row = _row(compare(archive, atlas), FEB)
    assert (row["archive"], row["atlas"], row["only_atlas"]) == (0, 1, ["g1"])
    assert render_markdown(compare(archive, atlas)).startswith("## ❌")


def test_the_games_without_the_current_derived_are_counted_on_each_side():
    archive, atlas = new_mock_db("a"), new_mock_db("b")
    _fill(archive, FEB, ["g1"], derived=DERIVED_VERSION - 1)
    _fill(archive, FEB, ["g2"], derived=None)
    _fill(atlas, FEB, ["g1", "g2"])
    row = _row(compare(archive, atlas), FEB)
    assert (row["archive_stale"], row["atlas_stale"]) == (2, 0)


def test_equal_sides_are_all_fine_and_an_empty_pair_has_nothing_to_say():
    archive, atlas = new_mock_db("a"), new_mock_db("b")
    _fill(archive, FEB, ["g1"])
    _fill(atlas, FEB, ["g1"])
    assert render_markdown(compare(archive, atlas)).startswith("## ✅")
    assert compare(new_mock_db("c"), new_mock_db("d")) == []


def test_collections_that_are_not_games_are_ignored():
    archive, atlas = new_mock_db("a"), new_mock_db("b")
    atlas["system.profile"].insert_one({"_id": 1})
    atlas["HISTORICAL"].insert_one({"_id": 1})
    assert compare(archive, atlas) == []


class TestReadOnly:
    def test_it_reads_names_and_projected_finds(self):
        atlas = new_mock_db("b")
        _fill(atlas, FEB, ["g1"])
        guarded = ReadOnly(atlas)
        assert guarded.list_collection_names() == [FEB]
        assert [d["_id"] for d in guarded[FEB].find({}, {"_id": 1})] == ["g1"]

    @pytest.mark.parametrize("call", [
        lambda c: c.insert_one({}), lambda c: c.insert_many([{}]), lambda c: c.update_one({}, {"$set": {"a": 1}}), lambda c: c.update_many({}, {"$set": {"a": 1}}),
        lambda c: c.delete_many({}), lambda c: c.delete_one({}), lambda c: c.drop(), lambda c: c.create_index("a"), lambda c: c.replace_one({}, {}), lambda c: c.bulk_write([]),
        lambda c: c.aggregate([{"$out": "x"}]),
    ])
    def test_nothing_that_writes_gets_through(self, call):
        atlas = new_mock_db("b")
        _fill(atlas, FEB, ["g1"])
        with pytest.raises(PermissionError):
            call(ReadOnly(atlas)[FEB])
        assert atlas[FEB].count_documents({}) == 1

    def test_the_database_cannot_be_dropped_either(self):
        with pytest.raises(PermissionError):
            ReadOnly(new_mock_db("b")).drop_collection("x")


class TestCollectionMeta:
    """``COLLECTION_META`` (one document per collection, written by the FEB scrape) is not in the archive: the report says what Atlas holds of it, for information."""

    def test_it_lists_the_metadata_of_atlas_and_which_have_no_games_or_lack_metadata(self):
        from src.local_data.atlas_compare import compare_meta

        archive, atlas = new_mock_db("a"), new_mock_db("b")
        _fill(atlas, FEB, ["g1"])
        _fill(atlas, OLD, ["o1"])
        atlas["COLLECTION_META"].insert_many([{"_id": FEB, "competition_label": "PRIMERA FEB"}, {"_id": "GONE_2020_2021_X", "competition_label": "OTRA"}])
        meta = compare_meta(archive, atlas)
        assert meta["atlas"] == 2 and meta["archive"] == 0
        assert meta["without_games"] == ["GONE_2020_2021_X"]            # metadata of a collection that no longer has games
        assert meta["without_meta"] == [OLD]                            # a collection with games and no metadata (labelled with its own name by the packages)

    def test_the_archive_side_counts_once_it_carries_the_metadata(self):
        from src.local_data.atlas_compare import compare_meta

        archive, atlas = new_mock_db("a"), new_mock_db("b")
        archive["COLLECTION_META"].insert_one({"_id": FEB})
        atlas["COLLECTION_META"].insert_one({"_id": FEB})
        assert compare_meta(archive, atlas)["archive"] == 1

    def test_the_summary_has_its_section_and_it_never_makes_the_report_unsafe(self):
        from src.local_data.atlas_compare import compare_meta

        archive, atlas = new_mock_db("a"), new_mock_db("b")
        _fill(archive, FEB, ["g1"])
        _fill(atlas, FEB, ["g1"])
        atlas["COLLECTION_META"].insert_one({"_id": "GONE_2020_2021_X"})
        text = render_markdown(compare(archive, atlas), compare_meta(archive, atlas))
        assert text.startswith("## ✅") and "COLLECTION_META" in text and "GONE_2020_2021_X" in text

    def test_atlas_is_only_read_with_a_projection(self):
        from src.local_data.atlas_compare import compare_meta

        atlas = new_mock_db("b")
        atlas["COLLECTION_META"].insert_one({"_id": FEB, "competition_url": "x"})
        meta = compare_meta(new_mock_db("a"), atlas)
        assert meta["atlas"] == 1
        with pytest.raises(PermissionError):
            ReadOnly(atlas)["COLLECTION_META"].find({})                  # no projection: refused
