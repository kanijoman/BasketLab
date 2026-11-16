"""The single catalogue of competitions (issue #724, step 2): ``config/competitions.json`` says, once per competition, what is scraped, what is published and what is recorded.

Before it, adding a competition meant editing four files that drifted apart (the old refresh config, ``local_refresh.json``, the ``competitions`` of ``package_publish.json`` and
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


def _fbcyl(**over):
    base = {"league": "fbcyl", "competition": "1ª FASE-GRUPO A-1", "season_label": "2026", "season_value": "2026",
            "fbcyl": {"competition_id": "7298", "category": "1129", "gender": "F", "territory": "1"}}
    return {**base, **over}


class TestFbcyl:
    """FBCYL competitions are listed in the catalogue too: which groups to scrape is said here (issue #724); they have no packages, calendar or recorder."""

    def test_a_valid_fbcyl_entry_loads_without_a_url_or_groups(self, tmp_path):
        [entry] = load_catalogue(_write(tmp_path, _fbcyl()))
        assert entry["league"] == "fbcyl" and entry["fbcyl"]["competition_id"] == "7298" and entry["active"] is True

    @pytest.mark.parametrize("bad, message", [
        ({"fbcyl": {"category": "1129"}}, "competition_id"),
        ({"fbcyl": {"competition_id": "7298"}}, "category"),
        ({"fbcyl": "7298"}, "fbcyl"),
        ({"league": "other"}, "league"),
    ])
    def test_a_bad_fbcyl_entry_names_its_position_and_the_field(self, tmp_path, bad, message):
        with pytest.raises(ValueError, match=rf"#1.*{message}"):
            load_catalogue(_write(tmp_path, _fbcyl(**bad)))

    def test_two_groups_of_the_same_season_are_two_entries_and_the_same_group_twice_is_not(self, tmp_path):
        other = _fbcyl(competition="1ª FASE-GRUPO A-2", fbcyl={"competition_id": "7299", "category": "1129", "gender": "F", "territory": "1"})
        assert len(load_catalogue(_write(tmp_path, _fbcyl(), other))) == 2
        with pytest.raises(ValueError, match="twice"):
            load_catalogue(_write(tmp_path, _fbcyl(), _fbcyl()))

    def test_the_refresh_scrapes_them_and_the_packages_and_the_recorder_ignore_them(self, tmp_path):
        catalogue = load_catalogue(_write(tmp_path, _entry(record=["a"]), _fbcyl()))
        refresh = refresh_entries(catalogue)
        assert [e.league for e in refresh] == ["feb", "fbcyl"]
        assert refresh[1].fbcyl == {"competition_id": "7298", "category": "1129", "gender": "F", "territory": "1"}
        assert (refresh[1].competition_label, refresh[1].season_value) == ("1ª FASE-GRUPO A-1", "2026")
        assert [e.competition_label for e in package_entries(catalogue)] == ["PRIMERA FEB"]
        assert [c["competition"] for c in package_catalog(catalogue)] == ["PRIMERA FEB"]
        assert record_calendars(catalogue) == ["a"]


class TestPackagesFlag:
    """``packages: false`` (#875): a competition the staff does not play (the youth championships of Mercado) is scraped and published to the web, never given live packages."""

    def test_it_is_scraped_and_known_by_the_web_but_gets_no_packages(self, tmp_path):
        youth = _entry(competition="C ESP CLUBES JR FEM", gender="F", level=None, packages=False)
        catalogue = load_catalogue(_write(tmp_path, _entry(), youth))
        assert [e.competition_label for e in refresh_entries(catalogue)] == ["PRIMERA FEB", "C ESP CLUBES JR FEM"]
        assert [e.competition_label for e in package_entries(catalogue)] == ["PRIMERA FEB"]
        assert {c["competition"]: c["gender"] for c in package_catalog(catalogue)} == {"PRIMERA FEB": "M", "C ESP CLUBES JR FEM": "F"}   # the gender of the manifest still comes from here

    def test_it_is_never_recorded_even_with_calendars(self, tmp_path):
        catalogue = load_catalogue(_write(tmp_path, _entry(competition="C ESP CLUBES JR FEM", packages=False, record=["x"])))
        assert record_calendars(catalogue) == []

    def test_an_older_season_without_packages_never_replaces_the_current_one_in_the_catalog_of_the_packages_regression(self, tmp_path):
        """Bug found adding the history of #876: ``package_catalog`` lets the last active entry of a competition win, so a 2025/26 entry listed after the 2026/27 one took its clubs and rules away."""
        now = _entry(clubs=["1008857"], rule_config={"formation_min_on_court": 0})
        older = _entry(season_label="2025/2026", season_value="2025", year="2025", packages=False)
        for order in ((now, older), (older, now)):
            chosen = package_catalog(load_catalogue(_write(tmp_path, *order)))
            assert [c["clubs"] for c in chosen] == [["1008857"]] and chosen[0]["rule_config"]["formation_min_on_court"] == 0

    def test_it_must_be_true_or_false(self, tmp_path):
        with pytest.raises(ValueError, match="packages"):
            load_catalogue(_write(tmp_path, _entry(packages="no")))


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


# the seasons of the history and youth championships loaded so far (#876): one batch of seasons at a time, so the refresh of FEB keeps its time
LOADED_SEASONS = {"2022", "2023", "2024", "2025"}


class TestTheRealCatalogue:
    """What the repository's file says: it replaces the four files without changing what they made."""

    def test_it_loads_with_the_feb_competitions_complete_and_the_fbcyl_groups_to_scrape(self):
        catalogue = load_catalogue(ROOT / DEFAULT_CATALOGUE)
        feb = [e for e in catalogue if e["league"] == "feb" and e.get("packages", True)]
        assert len(feb) == 8 and all(e["active"] for e in feb)
        assert all(e["groups"] == "all" for e in feb)                             # every competition complete, 3a FEB included (the archive has no 512 MB limit)
        assert all(e["recheck_days"] == 3 for e in feb)                           # the refresh of web-data looks again at the last days
        assert all("packages_groups" not in e or e["packages_groups"] == [] for e in feb)     # and the packages of every group of 3a FEB too (decided 03/11/2026)

    def test_the_youth_championships_of_mercado_are_six_per_season_for_both_genders_and_have_no_packages(self):
        youth = [e for e in load_catalogue(ROOT / DEFAULT_CATALOGUE) if e["league"] == "feb" and not e.get("packages", True) and ("C ESP" in e["competition"] or "SSAA" in e["competition"])]
        assert {e["competition"] for e in youth} == {"C ESP CLUBES JR FEM", "C ESP CLUBES JR MASC", "C ESP CLUBES CAD FEM", "C ESP CLUBES CAD MASC", "CE SSAA Cadete Fem.", "CE SSAA Cadete Mas."}
        assert {e["season_value"] for e in youth} == {"2020", "2021", "2022", "2023", "2024", "2025"}       # 2019/20 had no championship
        assert len(youth) == 36 and all(e["groups"] == "all" and e["record"] == [] for e in youth)
        assert {e["gender"] for e in youth if "Fem" in e["competition"] or "FEM" in e["competition"]} == {"F"}
        assert {e["gender"] for e in youth if "Mas" in e["competition"] or "MASC" in e["competition"]} == {"M"}

    def test_the_old_youth_seasons_are_loaded_in_batches_so_the_refresh_of_feb_keeps_its_time(self):
        youth = [e for e in load_catalogue(ROOT / DEFAULT_CATALOGUE) if e["league"] == "feb" and not e.get("packages", True) and ("C ESP" in e["competition"] or "SSAA" in e["competition"])]
        assert {e["season_value"] for e in youth if e["active"]} == LOADED_SEASONS

    def test_the_senior_history_has_every_edition_that_exists_and_no_packages(self):
        history = [e for e in load_catalogue(ROOT / DEFAULT_CATALOGUE) if e["league"] == "feb" and not e.get("packages", True) and e["gender"] and "C ESP" not in e["competition"] and "SSAA" not in e["competition"]]
        seasons = {}
        for e in history:
            seasons.setdefault(e["competition"], set()).add(e["season_value"])
        every = {"2020", "2021", "2022", "2023", "2024", "2025"}
        assert seasons == {"LF ENDESA": every, "PRIMERA FEB": every, "SEGUNDA FEB": every, "L.F.-2": every, "TERCERA FEB": every,
                           "LF CHALLENGE": every - {"2020"}, "COPA ESPAÑA": {"2024", "2025"}, "LIGA U": {"2025"}}      # the page falls back to another season when an edition does not exist
        assert all(e["groups"] == "all" and e["record"] == [] for e in history)

    def test_only_the_seasons_of_the_batches_loaded_so_far_are_active_and_the_big_tercera_waits_for_its_own_batches(self):
        """Batch 1 of #876 (2023 and 2022); each new batch changes ``LOADED_SEASONS`` here and in the youth test above, and nothing else."""
        history = [e for e in load_catalogue(ROOT / DEFAULT_CATALOGUE) if e["league"] == "feb" and not e.get("packages", True) and "C ESP" not in e["competition"] and "SSAA" not in e["competition"]]
        senior = ("LF ENDESA", "PRIMERA FEB", "SEGUNDA FEB", "L.F.-2", "LF CHALLENGE")
        assert {(e["competition"], e["season_value"]) for e in history if e["active"]} == (
            {(c, y) for c in senior for y in sorted(LOADED_SEASONS)} | {("COPA ESPAÑA", "2024"), ("COPA ESPAÑA", "2025"), ("LIGA U", "2025")})
        assert not any(e["active"] for e in history if e["competition"] == "TERCERA FEB")

    def test_the_fbcyl_groups_keep_primera_nacional_femenina_a_1_and_a_2_and_add_the_autonomic_cadete_junior_and_senior_ones(self):
        fbcyl = [e for e in load_catalogue(ROOT / DEFAULT_CATALOGUE) if e["league"] == "fbcyl"]
        assert [(e["competition"], e["fbcyl"]["competition_id"]) for e in fbcyl[:2]] == [("1ª FASE-GRUPO A-1", "7298"), ("1ª FASE-GRUPO A-2", "7299")]        # the two that were there, untouched
        assert {e["fbcyl"]["territory"] for e in fbcyl} == {"1"}                                                  # autonomic only (#920): no provincial, no escolar
        assert {e["fbcyl"]["gender"] for e in fbcyl} == {"M", "F"}                                                # men and women
        assert {(e["season_value"], e["active"]) for e in fbcyl} == {("2026", True), ("2025", False), ("2024", False)}      # 2026 loads, the older seasons wait for their batch
        assert not any(any(w in e["note"].upper() for w in ("INF", "MINI", "ESCOLAR", "PROVINCIAL")) for e in fbcyl)     # nothing below cadete

    def test_the_collection_of_a_1_is_the_one_already_stored(self):
        from src.database import get_collection_name

        a1 = next(e for e in refresh_entries(load_catalogue(ROOT / DEFAULT_CATALOGUE)) if e.league == "fbcyl")
        assert get_collection_name(f"FBCYL_{a1.competition_label}", a1.season_value, "") == "FBCYL_1ª_FASE-GRUPO_A-1_2026_"

    def test_the_other_files_no_longer_hold_what_the_catalogue_says(self):
        assert "competitions" not in json.loads((ROOT / "config" / "package_publish.json").read_text(encoding="utf-8"))
        assert "calendars" not in json.loads((ROOT / "config" / "feb_watchlist.json").read_text(encoding="utf-8"))
        assert not (ROOT / "config" / "local_refresh.json").exists()
