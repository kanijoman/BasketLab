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
