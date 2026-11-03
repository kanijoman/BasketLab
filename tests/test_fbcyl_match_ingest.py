"""The incremental FBCYL ingestion of one competition group (issue #724): shared by the scrape API and by the refresh job, as the FEB one is.

The refresh takes FBCYL competitions from the catalogue (``config/competitions.json``), so the scrape of a group cannot live only in the router.
"""
from unittest.mock import MagicMock

from src.services.fbcyl_match_ingest import scrape_fbcyl_collection, store_fbcyl_match

PARAMS = {"competition_id": "7298", "season": "2026", "gender": "F", "territory": "1", "category": "1129", "competition_label": "1ª FASE-GRUPO A-1"}


def _db(existing=()):
    db = MagicMock()
    db.document_exists.side_effect = lambda collection, uuid: uuid in existing
    return db


def _scraper(uuids, data=None):
    scraper = MagicMock()
    scraper.get_matches.return_value = list(uuids)
    scraper.get_match_complete_data.side_effect = lambda uuid, league_ctx=None: (data or {}).get(uuid, {"uuid": uuid, "stats": {}, "moves": {}})
    return scraper


class TestStoreOne:
    def test_a_stored_match_is_skipped_without_downloading_it(self):
        job = {"done": 0, "skipped": 0, "errors": []}
        scraper = _scraper([])
        store_fbcyl_match(job, _db({"u1"}), scraper, "COL", "u1", {})
        assert (job["skipped"], job["done"]) == (1, 1)
        scraper.get_match_complete_data.assert_not_called()

    def test_a_match_without_data_is_an_error_and_a_failure_does_not_stop_the_count(self):
        job = {"done": 0, "skipped": 0, "errors": []}
        scraper = MagicMock()
        scraper.get_match_complete_data.return_value = None
        store_fbcyl_match(job, _db(), scraper, "COL", "u1", {})
        scraper.get_match_complete_data.side_effect = RuntimeError("boom")
        store_fbcyl_match(job, _db(), scraper, "COL", "u2", {})
        assert job["done"] == 2 and len(job["errors"]) == 2 and "u2" in job["errors"][1]


class TestScrapeGroup:
    def test_it_stores_what_is_new_under_the_collection_of_the_group_with_its_league_context(self):
        db, scraper = _db({"old"}), _scraper(["old", "new1", "new2"])
        job = scrape_fbcyl_collection(db, PARAMS, scraper)
        assert job["collection"].startswith("FBCYL_1") and job["collection"].endswith("_FASE-GRUPO_A-1_2026_")
        assert (job["total"], job["done"], job["skipped"], job["errors"]) == (3, 3, 1, [])
        stored = [c.args[1] for c in db.insert_fbcyl_match.call_args_list]
        assert stored == ["new1", "new2"]
        assert scraper.get_match_complete_data.call_args.kwargs["league_ctx"] == {
            "gender": "F", "territory": "1", "category": "1129", "competition_id": "7298", "season": "2026"}
        scraper.get_matches.assert_called_once_with("7298")

    def test_a_group_with_no_matches_is_not_an_error(self):
        job = scrape_fbcyl_collection(_db(), PARAMS, _scraper([]))
        assert (job["total"], job["done"], job["errors"]) == (0, 0, [])

    def test_the_job_given_is_the_one_filled_so_the_api_can_watch_it(self):
        job = {"status": "queued"}
        assert scrape_fbcyl_collection(_db(), PARAMS, _scraper(["u"]), job) is job and job["done"] == 1
