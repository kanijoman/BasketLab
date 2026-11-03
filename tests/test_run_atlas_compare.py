"""The entry point of the comparison (issue #724): it needs the READ credential of Atlas and says through its exit code whether the archive misses games."""
import run_atlas_compare
from tests.db_helpers import new_mock_db

FEB = "PRIMERA_FEB_2026_2027_Liga_Regular_Unico"


def test_without_the_read_credential_it_stops_and_touches_nothing(monkeypatch, capsys):
    monkeypatch.delenv("ATLAS_READ_URI", raising=False)
    assert run_atlas_compare.main([]) == 2
    assert "ATLAS_READ_URI" in capsys.readouterr().err


def test_exit_code_and_summary_tell_whether_the_archive_misses_games(tmp_path, monkeypatch, capsys):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    archive, atlas = new_mock_db("a"), new_mock_db("b")
    atlas[FEB].insert_one({"_id": "g1"})
    assert run_atlas_compare.main([], archive=archive, atlas=atlas) == 1
    assert "g1" in summary.read_text(encoding="utf-8")
    archive[FEB].insert_one({"_id": "g1"})
    assert run_atlas_compare.main([], archive=archive, atlas=atlas) == 0
    assert "✅" in capsys.readouterr().out
