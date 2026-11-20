"""The ACB editions of the catalogue (#886, D2c of epic #872): ``python run_acb_catalogue.py`` adds, PAUSED, an entry for every edition of the Liga Endesa since 2019/20 that the site lists.

Which editions ACB has is not guessed (the id of an edition is the site's, not a formula): the API says the year of each one, and each is asked for its clubs before it goes in. Nothing is activated: an
entry is ``active: false`` until somebody turns it on, and what is already in the catalogue is never touched.
"""
import json
from pathlib import Path

import pytest

from src.external.acb_catalogue import FIRST_YEAR, LIGA_ENDESA, new_entries
from src.external.acb_client import AcbFetchError, AcbNotFound
from src.services.competition_catalogue import external_entries, load_catalogue

TODAY = "20/11/2026"
FIX = Path(__file__).parent / "fixtures" / "acb"
EDITIONS = {2019 + i: 84 + i for i in range(8)}                    # what the real API says: 2019/20 is the edition 84 ... 2026/27 the 91


class Site:
    """A fake ACB: the editions it lists (``{year: edition id}``), the clubs of each (``{edition id: number}``; the rest are a 404) and the ones that fail."""

    def __init__(self, clubs, editions=None, broken=()):
        self._editions = dict(EDITIONS if editions is None else editions)
        self.clubs, self.broken, self.asked = dict(clubs), set(broken), []

    def editions(self, competition_id=1):
        return dict(self._editions)

    def teams(self, edition_id, competition_id=1):
        self.asked.append(edition_id)
        if edition_id in self.broken:
            raise AcbFetchError("503")
        if edition_id not in self.clubs:
            raise AcbNotFound(str(edition_id))
        return [{"clubId": i + 1, "fullName": f"Club {i}"} for i in range(self.clubs[edition_id])]


ALL = {ed: 18 for ed in EDITIONS.values()}


class TestWhatIsAdded:
    def test_there_is_an_entry_per_edition_since_2019_20_all_paused_and_in_order(self):
        entries, report = new_entries(Site(ALL), [], TODAY)
        assert [e["season_value"] for e in entries] == [str(y) for y in range(2019, 2027)] and FIRST_YEAR == 2019
        assert [e["acb"]["edition_id"] for e in entries] == list(range(84, 92))
        assert all(e["active"] is False and e["league"] == "acb" and e["acb"]["competition_id"] == LIGA_ENDESA == 1 for e in entries)
        assert report == {"already": [], "empty": [], "missing": [], "failed": {}}

    def test_an_entry_says_what_it_is(self):
        [entry, *_], _ = new_entries(Site(ALL), [], TODAY)
        assert (entry["competition"], entry["division"], entry["gender"], entry["season_label"], entry["label"]) == ("Liga Endesa", "Liga Endesa", "M", "2019/2020", "ACB Liga Endesa")
        assert "18" in entry["note"] and TODAY in entry["note"]

    def test_the_editions_before_2019_20_are_not_asked_for(self):
        site = Site({**ALL, 83: 18}, editions={**EDITIONS, 2018: 83})
        entries, _ = new_entries(site, [], TODAY)
        assert 83 not in site.asked and len(entries) == 8

    def test_an_entry_is_a_valid_one_of_the_catalogue_and_paused(self, tmp_path):
        entries, _ = new_entries(Site(ALL), [], TODAY)
        path = tmp_path / "competitions.json"
        path.write_text(json.dumps({"competitions": entries}), encoding="utf-8")
        loaded = load_catalogue(path)
        assert len(loaded) == 8 and external_entries(loaded) == [] and all(e["acb"] == {"competition_id": 1, "edition_id": e["acb"]["edition_id"]} for e in loaded)

    def test_what_is_already_in_the_catalogue_is_not_added_again_nor_touched_nor_asked_for(self):
        existing = [{"competition": "Liga Endesa", "league": "acb", "acb": {"competition_id": 1, "edition_id": 91}, "active": True}]
        site = Site(ALL)
        entries, report = new_entries(site, existing, TODAY)
        assert [e["acb"]["edition_id"] for e in entries] == list(range(84, 91)) and report["already"] == [91] and 91 not in site.asked

    def test_running_it_twice_adds_nothing_the_second_time(self):
        first, _ = new_entries(Site(ALL), [], TODAY)
        second, report = new_entries(Site(ALL), first, TODAY)
        assert second == [] and report["already"] == list(range(84, 92))

    def test_an_edition_with_no_clubs_is_empty_one_that_is_not_there_is_missing_and_one_that_fails_is_reported_and_the_others_still_go_in(self):
        site = Site({**ALL, 84: 0}, broken={85})
        del site.clubs[86]
        entries, report = new_entries(site, [], TODAY)
        assert [e["acb"]["edition_id"] for e in entries] == [87, 88, 89, 90, 91]
        assert report["empty"] == [84] and report["missing"] == [86] and report["failed"] == {85: "503"}

    def test_a_site_that_lists_no_editions_adds_nothing(self):
        entries, report = new_entries(Site({}, editions={}), [], TODAY)
        assert entries == [] and report["missing"] == []


class TestTheCommand:
    """``run_acb_catalogue.py``: appends the entries to ``config/competitions.json`` as the file is written, so the diff has only what was added."""

    @pytest.fixture()
    def cli(self):
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import run_acb_catalogue

        return run_acb_catalogue

    def _catalogue(self, tmp_path):
        existing = {"competitions": [{"competition": "LF ENDESA", "season_label": "2026/2027", "season_value": "2026", "year": "2026", "competition_url": "https://example.test/lf",
                                      "groups": "all", "recheck_days": 3, "active": True, "level": 1, "gender": "F", "record": []}]}
        path = tmp_path / "competitions.json"
        path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def test_it_appends_the_new_entries_and_leaves_the_rest_of_the_file_as_it_was(self, cli, tmp_path):
        path = self._catalogue(tmp_path)
        before = json.loads(path.read_text(encoding="utf-8"))
        assert cli.main(["--catalogue", str(path)], client=Site(ALL), today=TODAY) == 0
        after = json.loads(path.read_text(encoding="utf-8"))["competitions"]
        assert after[:1] == before["competitions"] and len(after) == 9 and all(e["active"] is False for e in after[1:])
        assert cli.main(["--catalogue", str(path)], client=Site(ALL), today=TODAY) == 0 and len(json.loads(path.read_text(encoding="utf-8"))["competitions"]) == 9      # twice: nothing new

    def test_a_dry_run_writes_nothing_and_a_failed_edition_is_an_exit_code_1(self, cli, tmp_path):
        path = self._catalogue(tmp_path)
        original = path.read_text(encoding="utf-8")
        assert cli.main(["--catalogue", str(path), "--dry-run"], client=Site(ALL), today=TODAY) == 0 and path.read_text(encoding="utf-8") == original
        assert cli.main(["--catalogue", str(path)], client=Site(ALL, broken={85}), today=TODAY) == 1 and len(json.loads(path.read_text(encoding="utf-8"))["competitions"]) == 8      # the rest went in


def test_the_real_answer_of_the_api_gives_the_editions_by_year():
    """The editions of the real API (``tests/fixtures/acb/teams.json``) are listed by their ``seasonStartYear``: the id is the site's, not a formula."""
    from src.external.acb_client import editions_of

    editions = editions_of(json.loads((FIX / "teams.json").read_text(encoding="utf-8")))
    assert editions[2019] == 84 and editions[2026] == 91 and all(isinstance(k, int) and isinstance(v, int) for k, v in editions.items()) and len(editions) >= 8
