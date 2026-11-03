"""The single catalogue of competitions (issue #724, step 2): ``config/competitions.json`` says, once per competition, what is scraped, what is published and what is recorded.

Before it, adding a competition meant editing four files that drifted apart (``atlas_refresh.json``, ``local_refresh.json``, the ``competitions`` of ``package_publish.json`` and
the calendars of ``feb_watchlist.json``). The refresh, the packages and the recorder read this file; ``active: false`` pauses a competition (it is neither scraped, published nor
recorded; its data stays), and removing an entry never deletes data (that is the purge, a separate and confirmed order).
"""
import json
from pathlib import Path

import pytest

from src.services.competition_catalogue import (
    DEFAULT_CATALOGUE, load_catalogue, package_catalog, package_entries, record_calendars, refresh_entries,
)

ROOT = Path(__file__).resolve().parents[1]
URL = "https://baloncestoenvivo.feb.es/calendario.aspx?g=1&t=2026&nm=primerafeb"


def _entry(**over):
    base = {"competition": "PRIMERA FEB", "season_label": "2026/2027", "season_value": "2026", "year": "2026", "competition_url": URL, "groups": "all", "recheck_days": 3,
            "level": 2, "gender": "M"}
    return {**base, **over}


def _write(tmp_path, *entries):
    path = tmp_path / "competitions.json"
    path.write_text(json.dumps({"competitions": list(entries)}), encoding="utf-8")
    return path


class TestLoad:
    def test_a_valid_entry_loads_with_active_by_default(self, tmp_path):
        [entry] = load_catalogue(_write(tmp_path, _entry()))
        assert entry["competition"] == "PRIMERA FEB" and entry["active"] is True

    @pytest.mark.parametrize("bad, message", [
        ({"competition": ""}, "competition"),
        ({"competition_url": ""}, "competition_url"),
        ({"season_label": ""}, "season_label"),
        ({"season_value": ""}, "season_value"),
        ({"groups": "some"}, "groups"),
        ({"active": "yes"}, "active"),
        ({"recheck_days": -1}, "recheck_days"),
        ({"record": "not a list"}, "record"),
        ({"level": "two"}, "level"),
        ({"gender": "X"}, "gender"),
    ])
    def test_a_bad_entry_names_its_position_and_the_field(self, tmp_path, bad, message):
        with pytest.raises(ValueError, match=rf"#1.*{message}"):
            load_catalogue(_write(tmp_path, _entry(**bad)))

    def test_a_competition_is_listed_once_per_season(self, tmp_path):
        with pytest.raises(ValueError, match="twice"):
            load_catalogue(_write(tmp_path, _entry(), _entry(competition="primera  FEB")))        # case and spaces do not make another competition
        load_catalogue(_write(tmp_path, _entry(), _entry(season_label="2025/2026", season_value="2025")))   # another season is another entry

    def test_a_single_group_needs_its_group_fields_and_all_groups_must_not_have_them(self, tmp_path):
        with pytest.raises(ValueError, match="group_value"):
            load_catalogue(_write(tmp_path, _entry(groups="")))
        with pytest.raises(ValueError, match="excludes"):
            load_catalogue(_write(tmp_path, _entry(group_value="1", group_label="A")))
        [entry] = load_catalogue(_write(tmp_path, _entry(groups="", group_value="90060", group_label='Liga Regular "A-B"')))
        assert entry["group_value"] == "90060"


class TestViews:
    def test_the_refresh_takes_the_active_entries_with_what_the_scraper_needs(self, tmp_path):
        path = _write(tmp_path, _entry(), _entry(competition="LF ENDESA", competition_url=URL.replace("primerafeb", "lfendesa"), active=False))
        entries = refresh_entries(load_catalogue(path))
        assert [e.competition_label for e in entries] == ["PRIMERA FEB"]
        e = entries[0]
        assert (e.season_value, e.season_label, e.year, e.groups, e.recheck_days, e.competition_url) == ("2026", "2026/2027", "2026", "all", 3, URL)

    def test_a_single_group_goes_to_the_refresh_with_its_fields(self, tmp_path):
        [e] = refresh_entries(load_catalogue(_write(tmp_path, _entry(groups="", group_value="90060", group_label='Liga Regular "A-B"'))))
        assert (e.groups, e.group_value, e.group_label) == ("", "90060", 'Liga Regular "A-B"')

    def test_the_packages_know_each_competition_by_name_with_level_gender_clubs_and_rules(self, tmp_path):
        path = _write(tmp_path, _entry(clubs=["1"], rule_config={"formation_min_on_court": 0}), _entry(competition="LF ENDESA", level=1, gender="F"))
        competitions = {c["competition"]: c for c in package_catalog(load_catalogue(path))}
        assert competitions["PRIMERA FEB"]["level"] == 2 and competitions["PRIMERA FEB"]["clubs"] == ["1"]
        assert competitions["PRIMERA FEB"]["rule_config"] == {"formation_min_on_court": 0}
        assert competitions["LF ENDESA"]["gender"] == "F"

    def test_pausing_a_competition_keeps_what_the_packages_know_of_it_and_the_active_season_wins(self, tmp_path):
        old = _entry(season_label="2025/2026", season_value="2025", active=False, clubs=["old"])
        [competition] = package_catalog(load_catalogue(_write(tmp_path, _entry(clubs=["new"]), old)))
        assert competition["clubs"] == ["new"]                                      # one per competition: the active season
        [paused] = package_catalog(load_catalogue(_write(tmp_path, _entry(active=False, clubs=["only"]))))
        assert paused["clubs"] == ["only"]                                          # older seasons are still read, so they keep their level and gender

    def test_the_packages_are_made_for_the_active_entries_narrowed_to_their_groups(self, tmp_path):
        path = _write(tmp_path, _entry(packages_groups=["A-B"]), _entry(competition="LF ENDESA", active=False))
        [entry] = package_entries(load_catalogue(path))
        assert entry.competition_label == "PRIMERA FEB" and entry.group_filter == ["A-B"]
        assert [e.group_filter for e in refresh_entries(load_catalogue(path))] == [[]]          # the refresh scrapes every group

    def test_the_recorder_gets_the_calendars_of_the_active_entries_in_order_without_repeats(self, tmp_path):
        path = _write(tmp_path, _entry(record=["a", "b"]), _entry(competition="LF ENDESA", record=["b", "c"]), _entry(competition="OFF", active=False, record=["z"]))
        assert record_calendars(load_catalogue(path)) == ["a", "b", "c"]

    def test_a_paused_competition_is_neither_scraped_nor_published_nor_recorded(self, tmp_path):
        catalogue = load_catalogue(_write(tmp_path, _entry(active=False, record=["a"])))
        assert refresh_entries(catalogue) == [] and package_entries(catalogue) == [] and record_calendars(catalogue) == []


class TestTheRealCatalogue:
    """What the repository's file says: it replaces the four files without changing what they made."""

    def test_it_loads_and_every_competition_has_a_scrape_a_level_and_a_gender(self):
        catalogue = load_catalogue(ROOT / DEFAULT_CATALOGUE)
        assert len(catalogue) == 8 and all(e["active"] for e in catalogue)
        assert all(e["groups"] == "all" for e in catalogue)                       # every competition complete, 3a FEB included (the archive has no 512 MB limit)
        assert all(e["recheck_days"] == 3 for e in catalogue)                     # the refresh of web-data looks again at the last days

    def test_the_old_atlas_refresh_has_no_competition_the_catalogue_lacks(self):
        from src.services.atlas_refresh import load_config

        names = {e.competition_label for e in refresh_entries(load_catalogue(ROOT / DEFAULT_CATALOGUE))}
        assert {e.competition_label for e in load_config(ROOT / "config" / "atlas_refresh.json")} <= names

    def test_the_other_files_no_longer_hold_what_the_catalogue_says(self):
        assert "competitions" not in json.loads((ROOT / "config" / "package_publish.json").read_text(encoding="utf-8"))
        assert "calendars" not in json.loads((ROOT / "config" / "feb_watchlist.json").read_text(encoding="utf-8"))
        assert not (ROOT / "config" / "local_refresh.json").exists()
