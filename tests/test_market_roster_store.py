"""Where the roster sweep leaves its result and where the publication reads it (A5 #905 writes, B2 #878 reads): ``rosters/<season>.json`` of the private ``basketlab-archive-ext``.

One file per season, ``{"format": 1, "season": "2025", "rows": [...]}``, sorted and without a timestamp, so a run with no news changes no byte and a commit only exists when something changed."""
import json

import pytest

from src.market.roster_store import FORMAT, merge_season, read_rosters, read_swept, write_season


def _row(person, team, season="2025"):
    return {"person_id": person, "season": season, "team_id": team, "name": "ANA PRUEBA", "birth": "2004-05-06", "height": 178, "position": "Base", "nationality": "ESPAÑA", "formacion": True, "dorsal": 7}


def test_a_season_is_written_sorted_and_read_back_identical(tmp_path):
    rows = [_row("feb:2", "10"), _row("feb:1", "11"), _row("feb:1", "10")]
    assert write_season(tmp_path, "2025", rows) is True
    assert [(r["person_id"], r["team_id"]) for r in read_rosters(tmp_path)] == [("feb:1", "10"), ("feb:1", "11"), ("feb:2", "10")]
    assert json.loads((tmp_path / "2025.json").read_text(encoding="utf-8"))["format"] == FORMAT


def test_writing_the_same_rows_again_changes_nothing_and_says_so(tmp_path):
    rows = [_row("feb:1", "10")]
    write_season(tmp_path, "2025", rows)
    before = (tmp_path / "2025.json").read_bytes()
    assert write_season(tmp_path, "2025", list(reversed(rows))) is False and (tmp_path / "2025.json").read_bytes() == before


def test_every_season_is_read_in_order_and_a_missing_folder_is_no_rosters(tmp_path):
    write_season(tmp_path, "2026", [_row("feb:1", "10", "2026")])
    write_season(tmp_path, "2024", [_row("feb:1", "10", "2024")])
    assert [r["season"] for r in read_rosters(tmp_path)] == ["2024", "2026"]
    assert read_rosters(tmp_path / "nowhere") == []


def test_a_file_that_cannot_be_read_stops_the_publication_instead_of_dropping_every_birth_date(tmp_path):
    (tmp_path / "2025.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="2025.json"):
        read_rosters(tmp_path)
    (tmp_path / "2025.json").write_text(json.dumps({"format": 99, "season": "2025", "rows": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="format"):
        read_rosters(tmp_path)


def test_rows_of_another_season_in_a_file_are_a_mistake_not_a_guess(tmp_path):
    with pytest.raises(ValueError, match="season"):
        write_season(tmp_path, "2025", [_row("feb:1", "10", "2024")])


class TestSweptTeams:
    """A team can have no roster rows (an empty page) and still have been swept, so the file says which teams were asked: a first load in several runs knows where it stopped."""

    def test_the_file_lists_the_swept_teams_even_if_a_team_has_no_rows(self, tmp_path):
        write_season(tmp_path, "2025", [_row("feb:1", "10")], teams=["10", "11"])
        assert read_swept(tmp_path) == {"2025": {"10", "11"}}
        assert json.loads((tmp_path / "2025.json").read_text(encoding="utf-8"))["teams"] == ["10", "11"]

    def test_a_file_without_the_list_counts_the_teams_of_its_rows_as_swept(self, tmp_path):
        (tmp_path / "2024.json").write_text(json.dumps({"format": FORMAT, "season": "2024", "rows": [_row("feb:1", "10", "2024"), _row("feb:2", "12", "2024")]}), encoding="utf-8")
        assert read_swept(tmp_path) == {"2024": {"10", "12"}}

    def test_teams_swept_without_rows_must_include_the_teams_of_the_rows(self, tmp_path):
        with pytest.raises(ValueError, match="teams"):
            write_season(tmp_path, "2025", [_row("feb:1", "10")], teams=["11"])

    def test_a_missing_folder_has_swept_nothing(self, tmp_path):
        assert read_swept(tmp_path / "nowhere") == {}


class TestMerge:
    def test_the_rows_of_a_swept_team_replace_the_old_ones_and_the_others_stay(self, tmp_path):
        write_season(tmp_path, "2025", [_row("feb:1", "10"), _row("feb:2", "10"), _row("feb:3", "11")], teams=["10", "11"])
        changed = merge_season(tmp_path, "2025", [_row("feb:1", "10"), _row("feb:9", "10")], swept=["10"])           # feb:2 left the roster of team 10, feb:9 joined it
        assert changed is True
        assert [(r["person_id"], r["team_id"]) for r in read_rosters(tmp_path)] == [("feb:1", "10"), ("feb:3", "11"), ("feb:9", "10")]
        assert read_swept(tmp_path) == {"2025": {"10", "11"}}

    def test_a_new_season_file_is_created_and_the_swept_teams_add_up_between_runs(self, tmp_path):
        merge_season(tmp_path, "2023", [_row("feb:1", "10", "2023")], swept=["10", "11"])
        merge_season(tmp_path, "2023", [_row("feb:5", "12", "2023")], swept=["12"])
        assert read_swept(tmp_path) == {"2023": {"10", "11", "12"}} and len(read_rosters(tmp_path)) == 2

    def test_the_same_merge_twice_changes_no_byte(self, tmp_path):
        merge_season(tmp_path, "2025", [_row("feb:1", "10")], swept=["10"])
        before = (tmp_path / "2025.json").read_bytes()
        assert merge_season(tmp_path, "2025", [_row("feb:1", "10")], swept=["10"]) is False and (tmp_path / "2025.json").read_bytes() == before

    def test_nothing_swept_and_no_rows_writes_nothing(self, tmp_path):
        assert merge_season(tmp_path, "2025", [], swept=[]) is False and not list(tmp_path.glob("*.json"))
