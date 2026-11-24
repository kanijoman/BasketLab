"""The Euroleague competitions of the catalogue (#1038, D6a of epic #872): ``python run_euroleague_catalogue.py`` adds, PAUSED, an entry for every season of the EuroLeague and the EuroCup since 2017/18 and of the
U18 Next Generation Tournament since 2019/20 that the API lists with games.

The first season of each is where the play by play of the API agrees with the official box (the spike of 23/11/2026: all the games measured from 2017/18 for the two senior competitions and from 2019/20 for the
U18 tournaments; before, the intents of two do not add up). The U18 tournaments are many a season (qualifiers and finals, each with its own code): one entry per season gathers them all. Nothing is activated.
"""
import json

import pytest

from euroleague_helpers import fixture

from src.external.euroleague_catalogue import FIRST_YEARS, new_entries
from src.external.euroleague_client import EuroleagueFetchError, EuroleagueNotFound
from src.external.euroleague_page import EuroleaguePageError, parse_seasons
from src.services.competition_catalogue import external_collections, external_entries, load_catalogue

TODAY = "24/11/2026"


def seasons(code, first, last):
    return [{"code": f"{code}{y}", "year": y, "name": f"{code} {y}"} for y in range(first, last + 1)]


class Site:
    """A fake API: the seasons of each competition and, for the ones it has, the games of each season (the rest are a 404)."""

    def __init__(self, by_competition, games=None, broken=(), empty=()):
        self.by, self.games_of, self.broken, self.empty, self.asked = by_competition, games, set(broken), set(empty), []

    def seasons(self, competition):
        return self.by[competition]

    def games(self, competition, season):
        self.asked.append(season)
        if season in self.broken:
            raise EuroleagueFetchError("503")
        if season in self.empty:
            raise EuroleaguePageError("no games")
        if self.games_of is not None and season not in self.games_of:
            raise EuroleagueNotFound(season)
        return [{"game_code": 1}]


def one_entry():
    return new_entries(Site({"E": seasons("E", 2025, 2025), "U": [], "J": []}), [], TODAY)[0][0]


ALL = {"E": seasons("E", 2010, 2026), "U": seasons("U", 2012, 2026), "J": parse_seasons(fixture("seasons_J"))}


class TestWhatIsAdded:
    def test_there_is_an_entry_per_season_since_the_first_reliable_one_all_paused_and_in_order(self):
        entries, report = new_entries(Site(ALL), [], TODAY)
        assert FIRST_YEARS == {"E": 2017, "U": 2017, "J": 2019}
        by = {c: [e["season_value"] for e in entries if e["euroleague"]["competition"] == c] for c in "EUJ"}
        assert by["E"] == [str(y) for y in range(2017, 2027)] and by["U"] == [str(y) for y in range(2017, 2027)]
        assert by["J"] == [str(y) for y in range(2019, 2027)] and min(by["J"]) == "2019"
        assert all(e["active"] is False and e["league"] == "euroleague" and e["gender"] == "M" for e in entries)
        assert report == {"already": [], "empty": [], "failed": {}}

    def test_an_entry_says_what_it_is(self):
        entries, _ = new_entries(Site(ALL), [], TODAY)
        first = entries[0]
        assert (first["competition"], first["division"], first["season_label"], first["season_value"], first["euroleague"]) == ("EuroLeague", "EuroLeague", "2017/2018", "2017", {"competition": "E"})
        assert TODAY in first["note"]
        assert {e["competition"] for e in entries} == {"EuroLeague", "EuroCup", "U18 Next Generation"}

    def test_the_seasons_before_the_first_reliable_one_are_not_even_asked_for(self):
        site = Site(ALL)
        new_entries(site, [], TODAY)
        assert "E2016" not in site.asked and "U2016" not in site.asked

    def test_what_the_catalogue_already_has_is_not_added_or_asked_for_again(self):
        entries, _ = new_entries(Site(ALL), [], TODAY)
        again, report = new_entries(Site(ALL), entries, TODAY)
        assert again == [] and len(report["already"]) == len(entries)

    def test_a_season_without_games_is_reported_not_added(self):
        entries, report = new_entries(Site(ALL, empty={"E2026"}), [], TODAY)
        assert "E2026" in report["empty"] and not any(e["competition"] == "EuroLeague" and e["season_value"] == "2026" for e in entries)

    def test_a_season_that_fails_is_reported_with_its_reason_and_the_rest_goes_on(self):
        entries, report = new_entries(Site(ALL, broken={"U2020"}), [], TODAY)
        assert report["failed"] == {"U2020": "503"} and len(entries) > 20

    def test_the_u18_tournaments_of_a_season_are_one_entry(self):
        entries, _ = new_entries(Site(ALL), [], TODAY)
        assert len([e for e in entries if e["euroleague"]["competition"] == "J" and e["season_value"] == "2025"]) == 1


class TestAsEntriesOfTheCatalogue:
    def _load(self, tmp_path, entries):
        path = tmp_path / "competitions.json"
        path.write_text(json.dumps({"competitions": entries}), encoding="utf-8")
        return load_catalogue(path)

    def test_an_entry_is_a_valid_one_and_paused(self, tmp_path):
        entries, _ = new_entries(Site(ALL), [], TODAY)
        catalogue = self._load(tmp_path, entries)
        assert len(catalogue) == len(entries) and external_entries(catalogue) == []

    def test_once_active_its_collection_carries_the_source_and_the_competition(self, tmp_path):
        entries, _ = new_entries(Site(ALL), [], TODAY)
        catalogue = self._load(tmp_path, [{**e, "active": True} for e in entries if e["season_value"] == "2025"])
        assert sorted(external_collections(catalogue)) == ["EUROLEAGUE_EuroCup_2025_", "EUROLEAGUE_EuroLeague_2025_", "EUROLEAGUE_U18_Next_Generation_2025_"]

    @pytest.mark.parametrize("bad", [None, {}, {"competition": "X"}, {"competition": ""}, {"competition": "E", "max_games": 0}, {"competition": "E", "max_games": True}, "E"])
    def test_an_entry_without_a_known_competition_code_is_refused(self, tmp_path, bad):
        entry = one_entry()
        with pytest.raises(ValueError, match="euroleague"):
            self._load(tmp_path, [{**entry, "euroleague": bad}])

    def test_two_entries_of_the_same_competition_and_season_are_a_duplicate(self, tmp_path):
        entry = one_entry()
        with pytest.raises(ValueError, match="twice"):
            self._load(tmp_path, [entry, dict(entry)])


class TestTheCommand:
    """``run_euroleague_catalogue.py``: appends the entries to ``config/competitions.json`` as the file is written, so the diff has only what was added."""

    @pytest.fixture()
    def cli(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import run_euroleague_catalogue

        return run_euroleague_catalogue

    def _catalogue(self, tmp_path):
        path = tmp_path / "competitions.json"
        path.write_text(json.dumps({"competitions": []}, indent=2) + "\n", encoding="utf-8")
        return path

    def test_it_appends_the_new_entries_paused_and_a_second_run_adds_nothing(self, cli, tmp_path):
        path = self._catalogue(tmp_path)
        assert cli.main(["--catalogue", str(path)], client=Site(ALL), today=TODAY) == 0
        added = json.loads(path.read_text(encoding="utf-8"))["competitions"]
        assert len(added) == 10 + 10 + 8 and all(e["active"] is False for e in added)
        assert cli.main(["--catalogue", str(path)], client=Site(ALL), today=TODAY) == 0 and len(json.loads(path.read_text(encoding="utf-8"))["competitions"]) == len(added)

    def test_a_dry_run_writes_nothing_and_a_failed_season_is_an_exit_code_1(self, cli, tmp_path):
        path = self._catalogue(tmp_path)
        original = path.read_text(encoding="utf-8")
        assert cli.main(["--catalogue", str(path), "--dry-run"], client=Site(ALL), today=TODAY) == 0 and path.read_text(encoding="utf-8") == original
        assert cli.main(["--catalogue", str(path)], client=Site(ALL, broken={"U2020"}), today=TODAY) == 1 and len(json.loads(path.read_text(encoding="utf-8"))["competitions"]) == 27
