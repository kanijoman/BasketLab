"""The purge of a competition from the archive (issue #724): the one order that reduces the archive, and the only one that deletes data.

Removing an entry of the catalogue never deletes anything and ``--no-shrink`` refuses to shrink the archive, so a competition that is gone for good needs its own deliberate
order. It asks for the name of the competition and its season typed again, shows what it would delete (a dry run is what you get without the confirmation), refuses a
competition that is still ACTIVE in the catalogue, and works on the files of the archive directory (the one place the games live), including its collection metadata.
"""
import json
from pathlib import Path

import pytest
from db_helpers import new_mock_db

from src.local_data.archive import META, dump_archive, load_archive
from src.local_data.archive_purge import (
    NothingToPurge, StillActive, collections_of, confirmation_for, purge, purge_archive, refuse_if_active,
)

PRIMERA_24 = ["PRIMERA_FEB_2024_2025_Liga_Regular_Único", "PRIMERA_FEB_2024_2025_Play-Offs_Final"]
PRIMERA_25 = "PRIMERA_FEB_2025_2026_Liga_Regular_Único"
LF_CHALLENGE = "LF_CHALLENGE_2024_2025_Liga_Regular_Único"
FBCYL = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"
ALL = PRIMERA_24 + [PRIMERA_25, LF_CHALLENGE, FBCYL]


def _meta(name):
    return {"_id": name, "league": "FEB", "competition_label": "PRIMERA FEB", "season_label": "2024/2025", "group_label": "x"}


@pytest.fixture()
def archive(tmp_path):
    db = new_mock_db("archive")
    for name in ALL:
        db[name].insert_many([{"_id": 1, "PLAYBYPLAY": {}, "DERIVED": {"v": 6}}, {"_id": 2, "PLAYBYPLAY": {}, "DERIVED": {"v": 6}}])
    db[META].insert_many([_meta(n) for n in ALL])
    dump_archive(db, tmp_path, light=lambda name: False)
    return tmp_path


def _manifest(directory):
    return json.loads((Path(directory) / "archive.json").read_text(encoding="utf-8"))


class TestWhatABelongsToACompetition:
    def test_the_collections_of_a_competition_and_season_are_found_by_name(self, archive):
        names = [c["name"] for c in _manifest(archive)["collections"]]
        assert sorted(collections_of(names, "PRIMERA FEB", "2024/2025")) == sorted(PRIMERA_24)
        assert collections_of(names, "PRIMERA FEB", "2025/2026") == [PRIMERA_25]
        assert collections_of(names, "LF", "2024/2025") == []                          # a competition is not a prefix of another one
        assert collections_of(names, "PRIMERA FEB", "2023/2024") == []

    def test_a_fbcyl_group_is_found_by_its_label_and_season(self, archive):
        names = [c["name"] for c in _manifest(archive)["collections"]]
        assert collections_of(names, "1ª FASE-GRUPO A-1", "2026", league="fbcyl") == [FBCYL]
        assert collections_of(names, "1ª FASE-GRUPO A-1", "2026", league="feb") == []

    def test_the_confirmation_is_the_competition_and_the_season_as_asked(self):
        assert confirmation_for("PRIMERA FEB", "2024/2025") == "PRIMERA FEB 2024/2025"


class TestStillActive:
    def _catalogue(self, tmp_path, **over):
        entry = {"competition": "PRIMERA FEB", "season_label": "2024/2025", "season_value": "2024", "competition_url": "https://x/y", "groups": "all", **over}
        path = tmp_path / "competitions.json"
        path.write_text(json.dumps({"competitions": [entry]}), encoding="utf-8")
        return path

    def test_an_active_competition_is_refused(self, tmp_path):
        with pytest.raises(StillActive, match="active"):
            refuse_if_active(self._catalogue(tmp_path), "primera  FEB", "2024/2025", "feb")            # case and spaces do not make another competition

    def test_a_paused_one_a_removed_one_and_another_season_can_be_purged(self, tmp_path):
        refuse_if_active(self._catalogue(tmp_path, active=False), "PRIMERA FEB", "2024/2025", "feb")
        refuse_if_active(self._catalogue(tmp_path), "PRIMERA FEB", "2023/2024", "feb")
        refuse_if_active(self._catalogue(tmp_path), "OTHER", "2024/2025", "feb")

    def test_a_fbcyl_group_is_checked_with_its_own_label(self, tmp_path):
        fbcyl = {"league": "fbcyl", "competition": "1ª FASE-GRUPO A-1", "season_label": "2026", "season_value": "2026",
                 "fbcyl": {"competition_id": "7298", "category": "1129"}}
        path = tmp_path / "competitions.json"
        path.write_text(json.dumps({"competitions": [fbcyl]}), encoding="utf-8")
        with pytest.raises(StillActive):
            refuse_if_active(path, "1ª FASE-GRUPO A-1", "2026", "fbcyl")


class TestPurgeTheArchive:
    def test_it_removes_the_files_the_entries_and_the_metadata_of_those_collections_only(self, archive):
        summary = purge_archive(archive, PRIMERA_24)
        assert sorted(summary["collections"]) == sorted(PRIMERA_24) and summary["games"] == 4 and summary["metadata"] == 2
        remaining = [c["name"] for c in _manifest(archive)["collections"]]
        assert sorted(remaining) == sorted([PRIMERA_25, LF_CHALLENGE, FBCYL])
        assert not any((archive / c["file"]).exists() for c in []) and len(list(archive.glob("*.jsonl.gz"))) == 4      # three competitions' files and the metadata file
        assert _manifest(archive)["meta"]["docs"] == 3

    def test_what_is_left_loads_and_nothing_else_was_touched(self, archive):
        before = {p.name: p.read_bytes() for p in archive.glob("*.jsonl.gz") if "2025_2026" in p.name or "LF_CHALLENGE" in p.name or "FBCYL" in p.name}
        purge_archive(archive, PRIMERA_24)
        for name, data in before.items():
            assert (archive / name).read_bytes() == data                                    # untouched byte for byte
        target = new_mock_db("restored")
        loaded = load_archive(archive, target)                                              # the manifest and the hashes are consistent
        assert sorted(loaded) == sorted([PRIMERA_25, LF_CHALLENGE, FBCYL])
        assert sorted(d["_id"] for d in target[META].find({})) == sorted([PRIMERA_25, LF_CHALLENGE, FBCYL])

    def test_purging_the_last_metadata_removes_the_metadata_file_too(self, archive):
        purge_archive(archive, ALL)
        assert "meta" not in _manifest(archive) and not list(archive.glob("*.jsonl.gz")) and _manifest(archive)["collections"] == []

    def test_a_name_that_is_not_in_the_archive_is_an_error_and_nothing_changes(self, archive):
        before = (archive / "archive.json").read_bytes()
        with pytest.raises(NothingToPurge):
            purge_archive(archive, ["NOT_IN_THE_ARCHIVE_2020_2021_A"])
        with pytest.raises(NothingToPurge):
            purge_archive(archive, [])
        assert (archive / "archive.json").read_bytes() == before


class TestThePurgeOrder:
    """What the command does: a dry run without the confirmation, and the purge only with exactly the confirmation."""

    def _catalogue(self, tmp_path, active=False):
        entry = {"competition": "PRIMERA FEB", "season_label": "2024/2025", "season_value": "2024", "competition_url": "https://x/y", "groups": "all", "active": active}
        path = tmp_path / "catalogue.json"
        path.write_text(json.dumps({"competitions": [entry]}), encoding="utf-8")
        return path

    def test_without_the_confirmation_it_only_shows_what_it_would_delete(self, archive, tmp_path):
        before = (archive / "archive.json").read_bytes()
        result = purge(archive, "PRIMERA FEB", "2024/2025", self._catalogue(tmp_path))
        assert result["purged"] is False and sorted(result["collections"]) == sorted(PRIMERA_24) and result["games"] == 4
        assert (archive / "archive.json").read_bytes() == before

    def test_with_the_exact_confirmation_it_purges(self, archive, tmp_path):
        result = purge(archive, "PRIMERA FEB", "2024/2025", self._catalogue(tmp_path), confirm="PRIMERA FEB 2024/2025")
        assert result["purged"] is True and len(_manifest(archive)["collections"]) == 3

    @pytest.mark.parametrize("typed", ["primera feb 2024/2025", "PRIMERA FEB", "PRIMERA FEB 2025/2026", "2024/2025", " PRIMERA FEB 2024/2025"])
    def test_any_other_confirmation_changes_nothing_and_is_an_error(self, archive, tmp_path, typed):
        before = (archive / "archive.json").read_bytes()
        with pytest.raises(ValueError, match="confirm"):
            purge(archive, "PRIMERA FEB", "2024/2025", self._catalogue(tmp_path), confirm=typed)
        assert (archive / "archive.json").read_bytes() == before

    def test_an_active_competition_is_never_purged_even_with_the_confirmation(self, archive, tmp_path):
        with pytest.raises(StillActive):
            purge(archive, "PRIMERA FEB", "2024/2025", self._catalogue(tmp_path, active=True), confirm="PRIMERA FEB 2024/2025")
        assert len(_manifest(archive)["collections"]) == 5

    def test_the_entry_point_has_a_purge_command_that_shows_the_plan_without_the_confirmation(self, archive, tmp_path, capsys):
        import run_archive

        code = run_archive.main(["purge", "--dir", str(archive), "--competition", "PRIMERA FEB", "--season", "2024/2025", "--catalogue", str(self._catalogue(tmp_path))])
        out = capsys.readouterr().out
        assert code == 0 and "PRIMERA FEB 2024/2025" in out and PRIMERA_24[0] in out and "dry run" in out.lower()
        assert run_archive.main(["purge", "--dir", str(archive), "--competition", "PRIMERA FEB", "--season", "2024/2025", "--catalogue", str(self._catalogue(tmp_path)),
                                 "--confirm", "wrong"]) == 2
        assert len(_manifest(archive)["collections"]) == 5
