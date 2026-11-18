"""The catalogue gives the external sources (ACB, FIBA, NCAA) a place of their own and keeps them out of everything FEB runs on (#884, block D0 of epic #872).

An external competition is a competition of ``config/competitions.json`` whose ``league`` is its source. It carries ``division``, ``gender`` and, for the sources that need it, ``conference`` (NCAA is one competition per
conference, never a flat list). What it must never do is get into the refresh of the FEB archive or the live packages: those read the catalogue, so the tests build the REAL catalogue plus one external entry per source and
ask each consumer for its entries with and without them.
"""
import json
from pathlib import Path

import pytest

from src.services.competition_catalogue import (
    DEFAULT_CATALOGUE, EXTERNAL_LEAGUES, external_entries, fbcyl_groups, load_catalogue, package_catalog, package_entries, record_calendars, refresh_entries,
)
from src.services.competition_refresh import load_config

ROOT = Path(__file__).resolve().parents[1]


def _external(source: str, **over):
    base = {"competition": f"{source.upper()} test", "season_label": "2026/2027", "season_value": "2026", "league": source, "division": "D1" if source == "ncaa" else "Top", "gender": "M"}
    if source == "ncaa":
        base["conference"] = "SEC"
    if source == "fiba":
        base["fiba"] = {"event": "fiba-test-event-2026"}
    return {**base, **over}


def _write(tmp_path, *entries, with_real=False):
    real = json.loads((ROOT / DEFAULT_CATALOGUE).read_text(encoding="utf-8"))["competitions"] if with_real else []
    path = tmp_path / "competitions.json"
    path.write_text(json.dumps({"competitions": [*real, *entries]}), encoding="utf-8")
    return path


class TestTheFibaEvent:
    """A FIBA competition is an EVENT of its site (``fiba-u18-eurobasket-2025``): the entry says which, or the source would not know what to ask for (#887, D3b)."""

    def test_the_entry_says_its_event_and_may_cap_the_games_of_a_run(self, tmp_path):
        [entry] = load_catalogue(_write(tmp_path, _external("fiba", fiba={"event": " fiba-u18-eurobasket-2025 ", "max_games": 40})))
        assert entry["fiba"] == {"event": "fiba-u18-eurobasket-2025", "max_games": 40}

    @pytest.mark.parametrize("bad", [None, "fiba-u18", {}, {"event": ""}, {"event": "  "}, {"event": 5}, {"event": "x", "max_games": 0}, {"event": "x", "max_games": -3}, {"event": "x", "max_games": "ten"}, {"event": "x", "max_games": True}])
    def test_an_entry_without_a_usable_event_or_with_a_bad_cap_is_refused_naming_its_position_and_field(self, tmp_path, bad):
        entry = _external("fiba")
        entry["fiba"] = bad
        with pytest.raises(ValueError, match=r"#1.*fiba"):
            load_catalogue(_write(tmp_path, entry))

    def test_the_other_sources_do_not_need_it_and_do_not_keep_one(self, tmp_path):
        entries = load_catalogue(_write(tmp_path, _external("acb"), _external("ncaa")))
        assert all("fiba" not in e for e in entries)


def test_the_categories_of_the_feb_and_fbcyl_publication_know_nothing_of_the_external_competitions(tmp_path):
    """``competition_categories`` is read by ``web-data`` for its own collections: an external entry must not make up a key of FBCYL (``FBCYL_U18_EuroBasket_2025_``) out of its name (#887)."""
    from src.services.competition_category import competition_categories

    catalogue = load_catalogue(_write(tmp_path, _external("fiba", competition="Test Cup U18", category="formacion", age_group="U18", label="FIBA Test Cup U18"), with_real=True))
    found = competition_categories(["FBCYL_Test_Cup_U18_2026_", "FIBA_Test_Cup_U18_2026_", "FBCYL_1ª_FASE-GRUPO_A-1_2026_"], catalogue)
    assert "FBCYL_Test_Cup_U18_2026_" not in found and "FIBA_Test_Cup_U18_2026_" not in found


def test_the_external_sources_are_acb_fiba_and_ncaa():
    assert EXTERNAL_LEAGUES == ("acb", "fiba", "ncaa")


class TestLoad:
    @pytest.mark.parametrize("source", EXTERNAL_LEAGUES)
    def test_an_external_entry_loads_with_its_source_and_needs_no_scraping_url(self, tmp_path, source):
        [entry] = load_catalogue(_write(tmp_path, _external(source)))
        assert entry["league"] == source and entry["source"] == source          # the source is the league: one name for where the rows come from (``_league`` of the canonical document)
        assert entry["division"] and entry["gender"] == "M" and entry["active"] is True

    @pytest.mark.parametrize("bad, message", [
        ({"division": ""}, "division"),
        ({"division": None}, "division"),
        ({"gender": "X"}, "gender"),
        ({"competition": ""}, "competition"),
        ({"season_value": ""}, "season_value"),
    ])
    def test_a_bad_external_entry_names_its_position_and_the_field(self, tmp_path, bad, message):
        with pytest.raises(ValueError, match=rf"#1.*{message}"):
            load_catalogue(_write(tmp_path, _external("acb", **bad)))

    def test_an_external_entry_must_say_its_gender(self, tmp_path):
        entry = _external("fiba")
        del entry["gender"]
        with pytest.raises(ValueError, match=r"#1.*gender"):
            load_catalogue(_write(tmp_path, entry))

    def test_ncaa_needs_its_conference_and_the_sources_that_do_not_need_it_may_leave_it_out(self, tmp_path):
        entry = _external("ncaa")
        del entry["conference"]
        with pytest.raises(ValueError, match=r"#1.*conference"):
            load_catalogue(_write(tmp_path, entry))
        with pytest.raises(ValueError, match=r"#1.*conference"):
            load_catalogue(_write(tmp_path, _external("ncaa", conference="  ")))
        load_catalogue(_write(tmp_path, _external("acb")))                                              # ACB has no conferences
        load_catalogue(_write(tmp_path, _external("fiba", conference="Group A")))                       # and if a source gives one it is kept

    def test_ncaa_is_one_competition_per_conference_and_the_same_conference_twice_is_a_duplicate(self, tmp_path):
        both = [_external("ncaa", conference="SEC"), _external("ncaa", conference="Ivy League")]       # the same name and season in two conferences: two competitions
        assert [e["conference"] for e in load_catalogue(_write(tmp_path, *both))] == ["SEC", "Ivy League"]
        with pytest.raises(ValueError, match="twice"):
            load_catalogue(_write(tmp_path, *both, _external("ncaa", conference="sec")))                # case does not make another conference

    def test_an_unknown_source_is_still_refused(self, tmp_path):
        with pytest.raises(ValueError, match="league"):
            load_catalogue(_write(tmp_path, _external("acb", league="euroleague")))

    def test_the_catalogue_of_the_repository_still_loads_with_external_entries_next_to_it(self, tmp_path):
        entries = load_catalogue(_write(tmp_path, *[_external(s) for s in EXTERNAL_LEAGUES], with_real=True))
        assert {e["league"] for e in entries} >= {"feb", "fbcyl", *EXTERNAL_LEAGUES}


class TestTheExternalSourcesStayOutOfWhatFebRunsOn:
    """The refresh of the archive (3 times a day, FEB and FBCYL), the live packages and the recorder read the catalogue; none may pick up an external competition, even an active one with ``packages`` and ``record`` set."""

    @pytest.fixture()
    def both(self, tmp_path):
        """The real catalogue alone and the same plus an ACTIVE external competition per source, set up as if it wanted packages and recording."""
        extra = [_external(s, packages=True, record=["https://example.test/calendar"], groups="all", competition_url="https://example.test/x", recheck_days=1) for s in EXTERNAL_LEAGUES]
        return load_catalogue(_write(tmp_path, with_real=True)), load_catalogue(_write(tmp_path, *extra, with_real=True)), _write(tmp_path, *extra, with_real=True)

    def test_the_refresh_of_the_archive_does_not_scrape_them(self, both):
        plain, with_external, _ = both
        assert refresh_entries(with_external) == refresh_entries(plain)

    def test_the_config_loader_of_the_refresh_job_does_not_return_them(self, both):
        plain, _, path = both
        assert load_config(path) == refresh_entries(plain)

    def test_the_live_packages_are_not_made_for_them(self, both):
        plain, with_external, _ = both
        assert package_entries(with_external) == package_entries(plain)
        assert package_catalog(with_external) == package_catalog(plain)

    def test_the_recorder_and_the_fbcyl_calendar_do_not_follow_them(self, both):
        plain, with_external, _ = both
        assert record_calendars(with_external) == record_calendars(plain)
        assert fbcyl_groups(with_external) == fbcyl_groups(plain)

    def test_they_are_listed_apart_for_the_jobs_that_do_read_them(self, both):
        _, with_external, _ = both
        assert [e["league"] for e in external_entries(with_external)] == list(EXTERNAL_LEAGUES)

    def test_a_paused_external_competition_is_not_listed(self, tmp_path):
        entries = load_catalogue(_write(tmp_path, _external("acb"), _external("fiba", active=False)))
        assert [e["league"] for e in external_entries(entries)] == ["acb"]
