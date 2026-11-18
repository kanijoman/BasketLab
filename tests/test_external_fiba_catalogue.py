"""The FIBA events of the catalogue (#887, D3b): ``python run_fiba_catalogue.py --year 2025`` adds, PAUSED, an entry for every event of that year that exists on the site (as ``run_fbcyl_catalogue.py`` does for FBCYL).

Which events FIBA has is not guessed: each candidate is asked (the event page) and only the ones that exist and list games are added. Youth championships of U16 and U18 are ``formacion`` with their age group; U19, U20 and the
absolute national teams are senior (decided 13/11/2026 and 18/11/2026, #918). Nothing is activated: an entry is ``active: false`` until somebody turns it on, and what is already in the catalogue is never touched.
"""
import json

import pytest

from src.external.fiba_catalogue import candidate_events, new_entries
from src.external.fiba_client import FibaFetchError, FibaNotFound
from src.services.competition_catalogue import external_entries, load_catalogue

TODAY = "18/11/2026"


class Site:
    """The events the fake site has (``{slug: number of games}``); the rest are a 404, and ``broken`` ones fail."""

    def __init__(self, events, broken=()):
        self.events, self.broken, self.asked = dict(events), set(broken), []

    def event_games(self, slug):
        self.asked.append(slug)
        if slug in self.broken:
            raise FibaFetchError("503")
        if slug not in self.events:
            raise FibaNotFound(slug)
        return [{"game_id": i, "teams": [{"code": "AAA"}, {"code": "BBB"}]} for i in range(self.events[slug])]


class TestTheCandidates:
    def test_a_year_has_the_youth_championships_of_both_sexes_the_world_cup_and_the_absolute_events(self):
        slugs = [c["event"] for c in candidate_events([2025])]
        assert len(slugs) == 10 and len(set(slugs)) == 10
        assert {"fiba-u16-eurobasket-2025", "fiba-u16-womens-eurobasket-2025", "fiba-u18-eurobasket-2025", "fiba-u18-womens-eurobasket-2025", "fiba-u20-eurobasket-2025", "fiba-u20-womens-eurobasket-2025",
                "fiba-u19-basketball-world-cup-2025", "fiba-u19-womens-basketball-world-cup-2025", "fiba-eurobasket-2025", "fiba-womens-eurobasket-2025"} == set(slugs)

    def test_u16_and_u18_are_formacion_with_their_age_group_and_the_rest_senior(self):
        by = {c["event"]: c for c in candidate_events([2025])}
        assert (by["fiba-u18-eurobasket-2025"]["category"], by["fiba-u18-eurobasket-2025"]["age_group"]) == ("formacion", "U18")
        assert (by["fiba-u16-womens-eurobasket-2025"]["category"], by["fiba-u16-womens-eurobasket-2025"]["age_group"]) == ("formacion", "U16")
        for slug in ("fiba-u20-eurobasket-2025", "fiba-u19-basketball-world-cup-2025", "fiba-eurobasket-2025", "fiba-womens-eurobasket-2025"):
            assert "category" not in by[slug] and "age_group" not in by[slug]

    def test_the_gender_comes_from_the_name_of_the_event_and_the_names_are_readable(self):
        by = {c["event"]: c for c in candidate_events([2025])}
        assert (by["fiba-u18-eurobasket-2025"]["gender"], by["fiba-u18-womens-eurobasket-2025"]["gender"]) == ("M", "F")
        assert by["fiba-u18-eurobasket-2025"]["competition"] == "U18 EuroBasket" and by["fiba-u18-womens-eurobasket-2025"]["competition"] == "U18 EuroBasket Women"
        assert by["fiba-eurobasket-2025"]["competition"] == "EuroBasket" and by["fiba-womens-eurobasket-2025"]["competition"] == "EuroBasket Women"
        assert by["fiba-u19-basketball-world-cup-2025"]["competition"] == "U19 World Cup" and by["fiba-u18-eurobasket-2025"]["label"] == "FIBA U18 EuroBasket"

    def test_every_year_asked_for_gives_its_own_events_in_a_stable_order(self):
        first = candidate_events([2024, 2025])
        assert len(first) == 20 and first == candidate_events([2024, 2025]) and first[0]["season_value"] == "2024" and first[-1]["season_value"] == "2025"


class TestWhatIsAdded:
    def test_only_the_events_that_exist_and_list_games_are_added_all_paused(self):
        site = Site({"fiba-u18-eurobasket-2025": 56, "fiba-eurobasket-2025": 76, "fiba-u16-eurobasket-2025": 0})
        entries, report = new_entries(site, [], [2025], TODAY)
        assert {e["fiba"]["event"] for e in entries} == {"fiba-u18-eurobasket-2025", "fiba-eurobasket-2025"} and len(entries) == 2
        assert all(e["active"] is False for e in entries)
        assert "fiba-u16-eurobasket-2025" in report["empty"] and len(report["missing"]) == 7

    def test_an_entry_is_a_valid_one_of_the_catalogue(self, tmp_path):
        entries, _ = new_entries(Site({"fiba-u18-eurobasket-2025": 56, "fiba-u20-womens-eurobasket-2025": 56, "fiba-eurobasket-2025": 76}), [], [2025], TODAY)
        path = tmp_path / "competitions.json"
        path.write_text(json.dumps({"competitions": entries}), encoding="utf-8")
        loaded = load_catalogue(path)
        assert len(loaded) == 3 and external_entries(loaded) == []                       # paused: nothing to refresh yet
        by = {e["fiba"]["event"]: e for e in loaded}
        assert (by["fiba-u18-eurobasket-2025"]["category"], by["fiba-u18-eurobasket-2025"]["age_group"], by["fiba-u18-eurobasket-2025"]["gender"]) == ("formacion", "U18", "M")
        assert by["fiba-u20-womens-eurobasket-2025"]["gender"] == "F" and by["fiba-u20-womens-eurobasket-2025"].get("category") in (None, "senior")

    def test_the_note_says_how_many_games_the_event_lists_and_when(self):
        [entry], _ = new_entries(Site({"fiba-u18-eurobasket-2025": 56}), [], [2025], TODAY)
        assert "56" in entry["note"] and TODAY in entry["note"]

    def test_what_is_already_in_the_catalogue_is_not_added_again_nor_touched(self):
        site = Site({"fiba-u18-eurobasket-2025": 56, "fiba-eurobasket-2025": 76})
        existing = [{"competition": "U18 EuroBasket", "league": "fiba", "fiba": {"event": "fiba-u18-eurobasket-2025"}, "active": True}]
        entries, report = new_entries(site, existing, [2025], TODAY)
        assert [e["fiba"]["event"] for e in entries] == ["fiba-eurobasket-2025"] and "fiba-u18-eurobasket-2025" in report["already"]
        assert "fiba-u18-eurobasket-2025" not in site.asked                                  # and the site is not even asked about it

    def test_running_it_twice_adds_nothing_the_second_time(self):
        site = Site({"fiba-u18-eurobasket-2025": 56})
        first, _ = new_entries(site, [], [2025], TODAY)
        second, _ = new_entries(site, first, [2025], TODAY)
        assert len(first) == 1 and second == []

    def test_an_event_that_fails_to_answer_is_reported_and_the_others_still_go_in(self):
        site = Site({"fiba-u18-eurobasket-2025": 56, "fiba-eurobasket-2025": 76}, broken={"fiba-u16-eurobasket-2025"})
        entries, report = new_entries(site, [], [2025], TODAY)
        assert len(entries) == 2 and report["failed"] == {"fiba-u16-eurobasket-2025": "503"}

    def test_an_event_whose_games_are_only_the_shell_of_a_page_is_an_event_with_no_games_yet(self):
        class Shell(Site):
            def event_games(self, slug):
                super().event_games(slug)
                return [{"game_id": i, "teams": [], "slug": None, "finished": False} for i in range(20)]
        entries, report = new_entries(Shell({"fiba-u19-basketball-world-cup-2026": 20}), [], [2026], TODAY)
        assert entries == [] and "fiba-u19-basketball-world-cup-2026" in report["empty"]

    def test_the_games_an_event_lists_are_the_ones_with_teams(self):
        class Mixed(Site):
            def event_games(self, slug):
                super().event_games(slug)
                return [{"game_id": 1, "teams": [{"code": "A"}, {"code": "B"}]}, {"game_id": 2, "teams": []}]
        [entry], _ = new_entries(Mixed({"fiba-eurobasket-2025": 2}), [], [2025], TODAY)
        assert " 1 games listed" in entry["note"]

    def test_a_year_with_nothing_adds_nothing(self):
        entries, report = new_entries(Site({}), [], [2031], TODAY)
        assert entries == [] and len(report["missing"]) == 10


class TestTheCommand:
    """``run_fiba_catalogue.py``: appends the entries to ``config/competitions.json`` as the file is written (two spaces, accents as they are), so the diff has only what was added."""

    @pytest.fixture()
    def cli(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import run_fiba_catalogue
        return run_fiba_catalogue

    def _catalogue(self, tmp_path):
        existing = {"competitions": [{"competition": "LF ENDESA", "season_label": "2026/2027", "season_value": "2026", "year": "2026", "competition_url": "https://example.test/lf",
                                      "groups": "all", "recheck_days": 3, "active": True, "level": 1, "gender": "F", "record": []}]}
        path = tmp_path / "competitions.json"
        path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def test_it_appends_the_new_entries_and_leaves_the_rest_of_the_file_as_it_was(self, cli, tmp_path):
        path = self._catalogue(tmp_path)
        before = json.loads(path.read_text(encoding="utf-8"))
        assert cli.main(["--year", "2025", "--catalogue", str(path)], client=Site({"fiba-u18-eurobasket-2025": 56}), today=TODAY) == 0
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        assert data["competitions"][0] == before["competitions"][0]                                  # what was there is not touched
        assert [e["competition"] for e in data["competitions"]] == ["LF ENDESA", "U18 EuroBasket"] and data["competitions"][1]["active"] is False
        assert json.dumps(data, ensure_ascii=False, indent=2) + "\n" == text                       # in the format of the file: the diff is only what was added

    def test_it_changes_nothing_with_dry_run_and_says_what_it_would_add(self, cli, tmp_path, capsys):
        path = self._catalogue(tmp_path)
        before = path.read_text(encoding="utf-8")
        assert cli.main(["--year", "2025", "--catalogue", str(path), "--dry-run"], client=Site({"fiba-u18-eurobasket-2025": 56}), today=TODAY) == 0
        assert path.read_text(encoding="utf-8") == before and "fiba-u18-eurobasket-2025" in capsys.readouterr().out

    def test_running_it_twice_changes_nothing_the_second_time(self, cli, tmp_path):
        path = self._catalogue(tmp_path)
        site = Site({"fiba-u18-eurobasket-2025": 56})
        cli.main(["--year", "2025", "--catalogue", str(path)], client=site, today=TODAY)
        once = path.read_text(encoding="utf-8")
        cli.main(["--year", "2025", "--catalogue", str(path)], client=site, today=TODAY)
        assert path.read_text(encoding="utf-8") == once

    def test_the_catalogue_it_leaves_still_loads(self, cli, tmp_path):
        path = self._catalogue(tmp_path)
        cli.main(["--year", "2025", "--catalogue", str(path)], client=Site({"fiba-u18-eurobasket-2025": 56, "fiba-eurobasket-2025": 76}), today=TODAY)
        assert len(load_catalogue(path)) == 3

    def test_a_failure_of_the_site_is_said_and_exits_with_an_error_after_writing_what_it_could(self, cli, tmp_path, capsys):
        path = self._catalogue(tmp_path)
        code = cli.main(["--year", "2025", "--catalogue", str(path)], client=Site({"fiba-u18-eurobasket-2025": 56}, broken={"fiba-eurobasket-2025"}), today=TODAY)
        assert code == 1 and "fiba-eurobasket-2025" in capsys.readouterr().out and len(json.loads(path.read_text(encoding="utf-8"))["competitions"]) == 2
