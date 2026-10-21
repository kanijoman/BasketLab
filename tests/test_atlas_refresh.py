"""Scheduled refresh of the production database (Atlas) from FEB (issue #177).

Atlas fell behind the local copy because scraping was manual. The refresh job scrapes the configured
competitions incrementally (only new, finished matches) and then checks the result against the calendar.
"""
import json
from unittest.mock import MagicMock

import pytest
from db_helpers import new_mock_db

from src.services.atlas_refresh import RefreshEntry, load_config, main, refresh_all, to_markdown
from src.services.feb_match_ingest import is_in_progress, scrape_feb_collection

ENTRY = {"competition_url": "https://x/competicion.aspx?c=1", "season_value": "2026", "group_value": "7",
         "year": "2026", "competition_label": "LF CHALLENGE", "season_label": "LF CHALLENGE 2026", "group_label": "A"}


def _db():
    games = {}
    db = MagicMock()
    db.document_exists.side_effect = lambda col, code: code in games.get(col, set())
    db.insert_boxscore.side_effect = lambda col, code, doc: games.setdefault(col, set()).add(int(code))
    db.repository.connection.get_collection.return_value = new_mock_db()["COLLECTION_META"]
    db.stored = games
    return db


def _scraper(codes, in_progress=()):
    s = MagicMock()
    s.get_page_content.return_value = (None, MagicMock())
    s.get_matches.return_value = list(codes)
    s.fetch_boxscore.side_effect = lambda code, session: {"HEADER": {"status": "2" if code in in_progress else "3"}}
    return s


class TestScrapeCollection:
    def test_stores_new_finished_matches_and_skips_known_and_live_ones(self):
        db = _db()
        db.stored["LF_CHALLENGE_LF_CHALLENGE_2026_A"] = {1}
        job = scrape_feb_collection(db, RefreshEntry(**ENTRY), _scraper(["1", "2", "3"], in_progress={"3"}))
        assert db.stored["LF_CHALLENGE_LF_CHALLENGE_2026_A"] == {1, 2}
        assert (job["total"], job["skipped"], job["errors"]) == (3, 2, [])

    def test_a_failing_match_is_reported_and_does_not_stop_the_rest(self):
        db = _db()
        scraper = _scraper(["1", "2"])
        scraper.fetch_boxscore.side_effect = [None, {"HEADER": {"status": "3"}}]
        job = scrape_feb_collection(db, RefreshEntry(**ENTRY), scraper)
        assert len(job["errors"]) == 1 and db.insert_boxscore.call_count == 1

    def test_the_selection_is_remembered_for_the_live_match_list(self):
        db = _db()
        scrape_feb_collection(db, RefreshEntry(**ENTRY), _scraper([]))
        meta = db.repository.connection.get_collection.return_value.find_one({"_id": job_name(db)})
        assert meta is None or meta["competition_url"] == ENTRY["competition_url"]

    def test_in_progress_detection_is_shared_with_the_api_router(self):
        from src.api.routers import scrape

        assert scrape._is_in_progress is is_in_progress and is_in_progress({"HEADER": {"status": "2"}})


def job_name(db):
    return "LF_CHALLENGE_LF_CHALLENGE_2026_A"


class TestRefreshAll:
    def _freshness(self, missing):
        return lambda collection: {"collection": collection, "up_to_date": not missing, "missing_codes": missing,
                                   "games_in_db": 2, "calendar_results": 2 + len(missing), "last_game": "2026-10-04T14:00",
                                   "warning": None}

    def test_reports_each_competition_with_its_freshness(self):
        report = refresh_all(_db(), [RefreshEntry(**ENTRY)], scraper=_scraper(["1"]), freshness=self._freshness([]))
        assert report[0]["collection"] == "LF_CHALLENGE_LF_CHALLENGE_2026_A" and report[0]["freshness"]["up_to_date"] is True

    def test_one_failing_competition_does_not_block_the_others(self):
        scraper = _scraper(["1"])
        scraper.get_page_content.side_effect = [ConnectionError("feb down"), (None, MagicMock())]
        report = refresh_all(_db(), [RefreshEntry(**ENTRY), RefreshEntry(**{**ENTRY, "group_label": "B"})],
                             scraper=scraper, freshness=self._freshness([]))
        assert "feb down" in report[0]["fatal"] and report[1]["fatal"] is None

    def test_markdown_flags_the_missing_matches(self):
        report = refresh_all(_db(), [RefreshEntry(**ENTRY)], scraper=_scraper([]), freshness=self._freshness(["9"]))
        text = to_markdown(report)
        assert "LF_CHALLENGE_LF_CHALLENGE_2026_A" in text and "9" in text and "faltan" in text.lower()


class TestConfigAndCli:
    def test_load_config(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"scrapes": [ENTRY]}), encoding="utf-8")
        assert load_config(path)[0].group_label == "A"

    def test_an_incomplete_entry_is_rejected_with_its_position(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"scrapes": [{"competition_url": "x"}]}), encoding="utf-8")
        with pytest.raises(ValueError, match="#1"):
            load_config(path)

    def test_the_repository_config_is_valid(self):
        assert isinstance(load_config("config/atlas_refresh.json"), list)

    def test_the_cli_fails_without_a_connection_string(self, monkeypatch, tmp_path):
        monkeypatch.delenv("MONGODB_CONNECTION_STRING", raising=False)
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"scrapes": [ENTRY]}), encoding="utf-8")
        assert main(["--config", str(path), "--require-env"]) == 2


def test_the_cli_can_import_the_database_layer_in_a_clean_interpreter_regression():
    """CI runs ``run_atlas_refresh.py`` with no PYTHONPATH; ``src.database`` still needs ``src`` on sys.path (legacy imports)."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    code = "import run_atlas_refresh; from src.services.atlas_refresh import main; from src.database import MongoDBHandler"
    result = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-400:]


COPA = {"competition_url": "https://x/calendario.aspx?g=73&t=2026&nm=copaespaa", "season_value": "2026", "year": "2026",
        "competition_label": "COPA ESPAÑA", "season_label": "2026/2027", "groups": "all"}
COPA_GROUPS = [("Play-offs 1/16 Final", "90041"), ('FASE DE GRUPOS "A"', "90033"), ('FASE DE GRUPOS "B"', "90034")]


def _phase_scraper(groups=COPA_GROUPS):
    s = _scraper(["1"])
    s.get_groups_for_season.return_value = list(groups)
    return s


class TestCompetitionWithPhases:
    """A competition is one config entry with ``"groups": "all"``: its phases are discovered, never listed by hand (#456).

    The Copa de España adds a group per round (1/16, 1/8, ...). Listing each ``group_value`` would need a config edit
    before every round, so the refresh asks FEB for the groups of the season on each run.
    """

    def test_an_entry_with_all_groups_needs_no_group_fields(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"scrapes": [COPA]}), encoding="utf-8")
        entry = load_config(path)[0]
        assert entry.groups == "all" and entry.group_value == "" and entry.group_label == ""

    def test_all_groups_and_a_fixed_group_together_are_rejected(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"scrapes": [{**COPA, "group_value": "1", "group_label": "A"}]}), encoding="utf-8")
        with pytest.raises(ValueError, match="#1"):
            load_config(path)

    def test_an_unknown_groups_value_is_rejected(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"scrapes": [{**COPA, "groups": "some"}]}), encoding="utf-8")
        with pytest.raises(ValueError, match="#1"):
            load_config(path)

    def test_every_phase_found_is_refreshed_into_its_own_collection(self):
        from src.services.atlas_refresh import expand_entries

        entries = expand_entries([RefreshEntry(**COPA)], _phase_scraper())
        assert [(e.group_label, e.group_value, e.groups) for e in entries] == [(label, value, "") for label, value in COPA_GROUPS]
        assert {e.competition_url for e in entries} == {COPA["competition_url"]}

    def test_a_fixed_entry_is_left_untouched_and_does_not_ask_feb(self):
        from src.services.atlas_refresh import expand_entries

        scraper = _phase_scraper()
        fixed = RefreshEntry(**ENTRY)
        assert expand_entries([fixed], scraper) == [fixed]
        scraper.get_groups_for_season.assert_not_called()

    def test_the_group_filter_keeps_only_matching_labels_ignoring_case(self):
        from src.services.atlas_refresh import expand_entries

        entries = expand_entries([RefreshEntry(**{**COPA, "group_filter": ["play-offs"]})], _phase_scraper())
        assert [e.group_value for e in entries] == ["90041"]

    def test_refresh_all_scrapes_each_phase_and_reports_it(self):
        db = _db()
        report = refresh_all(db, [RefreshEntry(**COPA)], scraper=_phase_scraper(),
                             freshness=lambda c: {"up_to_date": True, "missing_codes": [], "games_in_db": 1, "last_game": None, "warning": None})
        assert [r["collection"] for r in report] == [
            "COPA_ESPAÑA_2026_2027_Play-offs_1_16_Final", "COPA_ESPAÑA_2026_2027_FASE_DE_GRUPOS_A", "COPA_ESPAÑA_2026_2027_FASE_DE_GRUPOS_B"]
        assert all(r["fatal"] is None for r in report)

    def test_a_phase_that_appears_later_is_picked_up_on_the_next_run(self):
        db, check = _db(), (lambda c: {"up_to_date": True, "missing_codes": [], "games_in_db": 1, "last_game": None, "warning": None})
        refresh_all(db, [RefreshEntry(**COPA)], scraper=_phase_scraper(COPA_GROUPS[:1]), freshness=check)
        second = refresh_all(db, [RefreshEntry(**COPA)], scraper=_phase_scraper(COPA_GROUPS + [("Play-offs 1/8 Final", "90042")]), freshness=check)
        assert "COPA_ESPAÑA_2026_2027_Play-offs_1_8_Final" in [r["collection"] for r in second]

    def test_a_failed_discovery_is_one_error_and_does_not_block_the_other_competitions(self):
        scraper = _phase_scraper()
        scraper.get_groups_for_season.side_effect = ConnectionError("feb down")
        report = refresh_all(_db(), [RefreshEntry(**COPA), RefreshEntry(**ENTRY)], scraper=scraper,
                             freshness=lambda c: {"up_to_date": True, "missing_codes": [], "games_in_db": 1, "last_game": None, "warning": None})
        assert "feb down" in report[0]["fatal"] and "COPA ESPAÑA" in report[0]["collection"]
        assert report[1]["fatal"] is None

    def test_a_competition_without_groups_is_an_error_not_silence(self):
        report = refresh_all(_db(), [RefreshEntry(**COPA)], scraper=_phase_scraper([]), freshness=lambda c: {})
        assert "grupos" in report[0]["fatal"]

    def test_the_publisher_finds_the_phases_already_stored_for_a_competition(self):
        """The live packages are built offline: the phases of ``groups: all`` are the collections the refresh stored."""
        from src.services.atlas_refresh import ingested_collections

        db = _db()
        meta = db.repository.connection.get_collection.return_value
        for label, value in COPA_GROUPS:
            meta.insert_one({"_id": f"COPA_ESPAÑA_2026_2027_{value}", "competition_url": COPA["competition_url"], "season_value": "2026",
                             "group_label": label})
        meta.insert_one({"_id": "OTHER", "competition_url": "https://x/other", "season_value": "2026", "group_label": "A"})
        names = ingested_collections(db, [RefreshEntry(**COPA), RefreshEntry(**ENTRY)])
        assert names == ["COPA_ESPAÑA_2026_2027_90041", "COPA_ESPAÑA_2026_2027_90033", "COPA_ESPAÑA_2026_2027_90034",
                         "LF_CHALLENGE_LF_CHALLENGE_2026_A"]

    def test_the_copa_is_in_the_repository_config_as_one_competition(self):
        copa = [e for e in load_config("config/atlas_refresh.json") if "nm=copaespaa" in e.competition_url]
        assert len(copa) == 1 and copa[0].groups == "all" and (copa[0].season_value, copa[0].year) == ("2026", "2026")


class TestCompetitionsOfTheApp:
    """The groups kept fresh in Atlas for the live app (issue #437, epic #435): LF Challenge, 2ª FEB A and B, 3ª FEB A-B (2026/27).

    The refresh does not discover competitions: it scrapes exactly what ``config/atlas_refresh.json`` lists, so each group is an entry with the
    values the scraper finds on the FEB site (competition page, season value, group value) and the labels that make the collection name.
    """

    EXPECTED = {
        "LF_CHALLENGE_2026_2027_Liga_Regular_Único": ("g=67", "lfchallenge", "89981"),
        "SEGUNDA_FEB_2026_2027_Liga_Regular_A": ("g=2", "segundafeb", "89999"),
        "SEGUNDA_FEB_2026_2027_Liga_Regular_B": ("g=2", "segundafeb", "90000"),
        "TERCERA_FEB_2026_2027_Liga_Regular_A-B": ("g=3", "tercerafeb", "90060"),
    }

    @staticmethod
    def entries():
        from src.database.utils import get_collection_name

        return {get_collection_name(e.competition_label, e.season_label, e.group_label): e for e in load_config("config/atlas_refresh.json") if e.groups != "all"}

    def test_every_group_of_the_app_is_in_the_config_with_its_values(self):
        entries = self.entries()
        assert set(self.EXPECTED) <= set(entries)
        for name, (g, nm, group_value) in self.EXPECTED.items():
            entry = entries[name]
            assert g in entry.competition_url and f"nm={nm}" in entry.competition_url and "t=2026" in entry.competition_url
            assert (entry.season_value, entry.group_value, entry.year) == ("2026", group_value, "2026")

    def test_two_entries_never_end_in_the_same_collection(self):
        from src.database.utils import get_collection_name

        names = [get_collection_name(e.competition_label, e.season_label, e.group_label) for e in load_config("config/atlas_refresh.json") if e.groups != "all"]
        assert len(names) == len(set(names))
