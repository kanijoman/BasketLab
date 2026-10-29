"""Late corrections of FEB (#646): the refresh also looks again at the games of the last days it already has.

The incremental scrape skips every game it stores (``document_exists``), so a game that FEB corrects after the fact (a box score fixed the day after, a
play-by-play completed) stayed wrong forever. A competition entry may ask (``recheck_days``) to download again the stored games whose date is inside that
window and to REPLACE the ones that changed, by match code (never duplicating, never deleting: a failed or unfinished download keeps what is stored).
Off by default: only the refresh that builds ``web-data`` (``config/local_refresh.json``) asks for it.
"""
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from db_helpers import new_mock_db

from src.database.repository import BasketballRepository
from src.services.atlas_refresh import RefreshEntry, load_config, to_markdown
from src.services.feb_match_ingest import scrape_feb_collection

COLLECTION = "LF_CHALLENGE_LF_CHALLENGE_2026_A"
ENTRY = {"competition_url": "https://x/competicion.aspx?c=1", "season_value": "2026", "group_value": "7", "year": "2026",
         "competition_label": "LF CHALLENGE", "season_label": "LF CHALLENGE 2026", "group_label": "A"}
NOW = datetime(2026, 10, 29, 12, 0)


def _game(starttime: str, points: str = "70", status: str = "3") -> dict:
    return {"HEADER": {"starttime": starttime, "status": status}, "BOXSCORE": {"TEAM": [{"TOTAL": {"pts": points}}]}, "PLAYBYPLAY": {"LINES": []}, "SHOTCHART": {}}


@pytest.fixture()
def repo():
    conn = MagicMock()
    conn.is_connected.return_value = True
    conn.get_collection.side_effect = lambda name: db[name]
    db = new_mock_db("recheck")
    return BasketballRepository(conn), db


class _Handler:
    """What the ingest needs of ``MongoDBHandler``, over a real repository on mongomock."""

    def __init__(self, repository):
        self.repository = repository

    def document_exists(self, collection, code):
        return self.repository.document_exists(collection, code)

    def insert_boxscore(self, collection, code, doc):
        return self.repository.insert_boxscore(collection, code, doc)

    def get_match_for_recheck(self, collection, code):
        return self.repository.get_match_for_recheck(collection, code)

    def replace_boxscore(self, collection, code, doc):
        return self.repository.replace_boxscore(collection, code, doc)


def _scraper(downloads: dict):
    s = MagicMock()
    s.get_page_content.return_value = (None, MagicMock())
    s.get_matches.return_value = list(downloads)
    s.fetch_boxscore.side_effect = lambda code, session: downloads[code]
    return s


def _ingest(repo, downloads, days=3, **entry):
    handler = _Handler(repo[0])
    return scrape_feb_collection(handler, RefreshEntry(**ENTRY, recheck_days=days, **entry), _scraper(downloads), now=NOW), handler


def _stored(repo, code):
    return repo[1][COLLECTION].find_one({"_id": int(code)})


def _seed(repo, code, game):
    repo[0].insert_boxscore(COLLECTION, code, dict(game))


def test_a_corrected_game_inside_the_window_is_replaced_by_its_match_code(repo):
    _seed(repo, "1", _game("28-10-2026 - 20:30", points="70"))
    job, _ = _ingest(repo, {"1": _game("28-10-2026 - 20:30", points="72")})
    assert _stored(repo, "1")["BOXSCORE"]["TEAM"][0]["TOTAL"]["pts"] == "72"
    assert repo[1][COLLECTION].count_documents({}) == 1                        # replaced, not duplicated
    assert (job["corrected"], job["rechecked"]) == (1, 1)


def test_the_replacement_keeps_the_id_and_recomputes_what_the_database_derives(repo):
    _seed(repo, "1", _game("28-10-2026 - 20:30"))
    _ingest(repo, {"1": _game("28-10-2026 - 20:30", points="75")})
    doc = _stored(repo, "1")
    assert doc["_id"] == 1


def test_a_game_that_did_not_change_is_left_alone(repo):
    _seed(repo, "1", _game("28-10-2026 - 20:30"))
    before = _stored(repo, "1")
    job, _ = _ingest(repo, {"1": _game("28-10-2026 - 20:30")})
    assert _stored(repo, "1") == before and (job["corrected"], job["rechecked"]) == (0, 1)


def test_a_game_outside_the_window_is_not_even_downloaded(repo):
    _seed(repo, "1", _game("10-10-2026 - 20:30"))
    scraper_calls = []
    s = _scraper({"1": _game("10-10-2026 - 20:30", points="99")})
    s.fetch_boxscore.side_effect = lambda code, session: scraper_calls.append(code) or _game("10-10-2026 - 20:30", points="99")
    scrape_feb_collection(_Handler(repo[0]), RefreshEntry(**ENTRY, recheck_days=3), s, now=NOW)
    assert scraper_calls == [] and _stored(repo, "1")["BOXSCORE"]["TEAM"][0]["TOTAL"]["pts"] == "70"


def test_the_window_is_in_days_and_its_edge_is_in(repo):
    _seed(repo, "1", _game("26-10-2026 - 12:00"))                              # exactly 3 days before NOW
    _seed(repo, "2", _game("26-10-2026 - 11:59"))                              # a minute older
    job, _ = _ingest(repo, {"1": _game("26-10-2026 - 12:00", points="71"), "2": _game("26-10-2026 - 11:59", points="71")})
    assert (job["rechecked"], job["corrected"]) == (1, 1)


def test_without_recheck_days_nothing_stored_is_downloaded_again_the_default(repo):
    _seed(repo, "1", _game("28-10-2026 - 20:30"))
    job, _ = _ingest(repo, {"1": _game("28-10-2026 - 20:30", points="99")}, days=0)
    assert _stored(repo, "1")["BOXSCORE"]["TEAM"][0]["TOTAL"]["pts"] == "70" and job.get("rechecked", 0) == 0


@pytest.mark.parametrize("download", [None, _game("28-10-2026 - 20:30", points="1", status="2")], ids=["no data", "unfinished"])
def test_a_download_that_fails_or_is_unfinished_keeps_what_is_stored(repo, download):
    _seed(repo, "1", _game("28-10-2026 - 20:30"))
    job, _ = _ingest(repo, {"1": download})
    assert _stored(repo, "1")["BOXSCORE"]["TEAM"][0]["TOTAL"]["pts"] == "70" and job["corrected"] == 0


def test_a_failing_recheck_is_reported_and_does_not_stop_the_new_games(repo):
    _seed(repo, "1", _game("28-10-2026 - 20:30"))
    s = _scraper({"1": None, "2": _game("29-10-2026 - 11:00")})
    s.fetch_boxscore.side_effect = [RuntimeError("feb down"), _game("29-10-2026 - 11:00")]
    job = scrape_feb_collection(_Handler(repo[0]), RefreshEntry(**ENTRY, recheck_days=3), s, now=NOW)
    assert repo[1][COLLECTION].count_documents({}) == 2 and len(job["errors"]) == 1


def test_a_stored_game_without_a_readable_date_is_not_rechecked(repo):
    repo[1][COLLECTION].insert_one({"_id": 1, "HEADER": {}, "BOXSCORE": {}})
    job, _ = _ingest(repo, {"1": _game("28-10-2026 - 20:30", points="99")})
    assert job["rechecked"] == 0


def test_recheck_days_is_validated_and_the_refresh_config_for_web_data_asks_for_it(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"scrapes": [{**ENTRY, "recheck_days": -1}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="recheck_days"):
        load_config(bad)
    root = Path(__file__).resolve().parent.parent / "config"
    assert all(e.recheck_days > 0 for e in load_config(root / "local_refresh.json"))      # the refresh of web-data looks again at the last days
    assert all(e.recheck_days == 0 for e in load_config(root / "atlas_refresh.json"))      # the production refresh is not changed


def test_the_report_says_how_many_games_were_corrected():
    report = [{"collection": COLLECTION, "fatal": None, "freshness": {"games_in_db": 5, "last_game": "x", "up_to_date": True},
               "job": {"total": 5, "done": 5, "skipped": 4, "errors": [], "rechecked": 3, "corrected": 1}}]
    assert "corregidos: 1" in to_markdown(report)
