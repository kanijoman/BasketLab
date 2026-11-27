"""FEB answers 5xx (#1146): the scheduled refresh of 26/11 and 27/11 went red because two groups of FEB returned 500 on the calendar page, and a 500 was never retried.

* The web client retries a 5xx (like a timeout) a few times before giving up, and remembers that the last failure was the server's (``last_status``).
* A competition whose discovery fails because FEB answers 5xx is **deferred**, not an error: it says so in the summary and the next run asks again. FEB down for good must still show:
  after ``MAX_OUTAGE_RUNS`` runs in a row the deferral becomes an error. The count is kept in the refresh state of the stored collections (days only, as the rest of it).
"""
from datetime import datetime
from unittest.mock import MagicMock

import pytest
import requests
from test_competition_refresh import ENTRY, _db, _scraper

from src.scraper.web_client import FebServerError, WebClient
from src.services import competition_refresh as cr
from src.services.competition_refresh import RefreshEntry, needs_attention, refresh_all, to_markdown
from src.services.refresh_state import MAX_OUTAGE_RUNS, load_state

NOW = datetime(2026, 11, 27, 12, 0)
NAME = "LF_CHALLENGE_LF_CHALLENGE_2026_A"


def _response(status):
    response = requests.Response()
    response.status_code = status
    response._content = b"<html></html>"
    response.url = "https://baloncestoenvivo.feb.es/resultados.aspx"
    return response


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda seconds: None)


def _real_scraper(status):
    """The REAL scraper (and web client) over a fake HTTP boundary: every page answers ``status``."""
    from src.scraper import FEBWebScraper

    scraper = FEBWebScraper()
    scraper.web_client.session = MagicMock()
    scraper.web_client.session.get.side_effect = lambda *a, **k: _response(status)
    scraper.web_client.session.post.side_effect = lambda *a, **k: _response(status)
    return scraper


class TestTheWebClientRetriesTheServer:
    def _client(self, *statuses):
        client = WebClient()
        client.session = MagicMock()
        client.session.post.side_effect = [_response(s) for s in statuses]
        client.session.get.side_effect = [_response(s) for s in statuses]
        return client

    def test_a_500_that_goes_away_is_retried_regression(self):
        client = self._client(500, 500, 200)

        assert client.post("https://x/resultados.aspx", {}).status_code == 200
        assert client.last_status is None

    def test_a_get_with_a_503_is_retried_too(self):
        assert self._client(503, 200).get("https://x/a").status_code == 200

    def test_a_500_that_stays_gives_up_and_says_it_was_the_server(self):
        client = self._client(500, 500, 500)

        assert client.post("https://x/resultados.aspx", {}) is None
        assert client.last_status == 500 and client.session.post.call_count == 3

    def test_a_404_is_not_retried_nor_a_server_failure(self):
        client = self._client(404, 200)

        assert client.get("https://x/BoxScore/1") is None
        assert client.session.get.call_count == 1 and client.last_status == 404


class TestAnOutageIsDeferredNotAnError:
    def _outage(self):
        scraper = _scraper(["1", "2"])
        scraper.get_matches.side_effect = FebServerError("FEB answered 500 selecting the group")
        return scraper

    def _run(self, db, scraper):
        return refresh_all(db, [RefreshEntry(**ENTRY)], scraper=scraper, freshness=lambda c: {"collection": c, "up_to_date": True, "missing_codes": [], "games_in_db": 2,
                           "calendar_results": 2, "last_game": "2026-11-20T12:00", "warning": None}, now=lambda: NOW)

    def test_a_competition_whose_calendar_returns_500_is_deferred_and_the_run_stays_green_regression(self):
        db = _db()
        report = self._run(db, self._outage())

        assert report[0]["deferred"] and report[0]["reason"] == "feb_unavailable" and report[0]["fatal"] is None
        assert not needs_attention(report)
        assert "la FEB no responde" in to_markdown(report) and "Aplazadas por tiempo" not in to_markdown(report)

    def test_the_other_competitions_are_refreshed_as_always(self):
        db = _db()
        scraper = _scraper(["1"])
        scraper.get_matches.side_effect = [FebServerError("500"), ["1"]]
        entries = [RefreshEntry(**{**ENTRY, "group_label": "A"}), RefreshEntry(**{**ENTRY, "group_label": "B", "group_value": "8"})]
        report = refresh_all(db, entries, scraper=scraper, freshness=lambda c: {"collection": c, "up_to_date": True, "missing_codes": [], "games_in_db": 1, "calendar_results": 1,
                             "last_game": "2026-11-20T12:00", "warning": None}, now=lambda: NOW)

        assert [bool(r.get("deferred")) for r in report] == [True, False] and not needs_attention(report)

    def test_the_outage_is_counted_by_runs_and_becomes_an_error_after_the_limit(self):
        db = _db()
        for run in range(1, MAX_OUTAGE_RUNS + 1):
            report = self._run(db, self._outage())
            assert load_state(db, NAME)["feb_down"]["runs"] == run
            assert bool(report[0].get("deferred")) is (run < MAX_OUTAGE_RUNS)
        assert report[0]["fatal"] and "no responde desde hace" in report[0]["fatal"] and needs_attention(report)

    def test_a_good_run_clears_the_count(self):
        db = _db()
        for _ in range(3):
            self._run(db, self._outage())
        self._run(db, _scraper(["1"]))

        assert "feb_down" not in load_state(db, NAME)

    def test_an_error_that_is_not_the_servers_is_still_an_error(self):
        scraper = _scraper(["1"])
        scraper.get_matches.side_effect = Exception("the page changed")
        report = self._run(_db(), scraper)

        assert report[0]["fatal"] and not report[0].get("deferred") and needs_attention(report)

    def test_a_5xx_while_listing_the_groups_defers_the_stored_collections_with_the_real_scraper_regression(self):
        """CodeRabbit (#1197): the discovery is the REAL scraper over a fake HTTP boundary (a 500 from every page), not a replaced ``expand_entries``: ``get_groups_for_season`` used to swallow
        the error and return ``[]``, which ended as «FEB no lista grupos» and a red run."""
        db = _db()
        self._run(db, _scraper(["1"]))                                                         # the collection of the competition exists
        entry = RefreshEntry(**{**ENTRY, "groups": "all", "group_label": "", "group_value": ""})

        report = refresh_all(db, [entry], scraper=_real_scraper(500), now=lambda: NOW)

        assert report[0]["deferred"] and report[0]["reason"] == "feb_unavailable" and not needs_attention(report)
        assert load_state(db, NAME)["feb_down"]["runs"] == 1

    def test_a_404_while_listing_the_groups_is_not_an_outage(self):
        db = _db()
        self._run(db, _scraper(["1"]))
        entry = RefreshEntry(**{**ENTRY, "groups": "all", "group_label": "", "group_value": ""})

        report = refresh_all(db, [entry], scraper=_real_scraper(404), now=lambda: NOW)

        assert report[0]["fatal"] and not report[0].get("deferred") and "feb_down" not in load_state(db, NAME)


class TestTheRealScraperSaysWhenItWasTheServer:
    URL = "https://baloncestoenvivo.feb.es/calendario/lfendesa/4/2026"

    @pytest.mark.parametrize("call", [
        lambda scraper: scraper.get_page_content("2026"),
        lambda scraper: scraper.get_groups_for_season(TestTheRealScraperSaysWhenItWasTheServer.URL, "2026"),
    ])
    def test_a_5xx_is_a_feb_server_error(self, call):
        with pytest.raises(FebServerError):
            call(_real_scraper(503).web_scraper)

    def test_a_4xx_is_not(self):
        assert _real_scraper(404).web_scraper.get_groups_for_season(self.URL, "2026") == []


class TestAFailureWhilePersistingTheOutageDoesNotStopTheRun:
    def test_a_mongo_error_saving_the_counter_is_that_competitions_error_only_regression(self, monkeypatch):
        """CodeRabbit (#1197): ``_outage`` runs inside an ``except`` and its own failure escaped ``refresh_all``: the rest of the competitions were never refreshed."""
        db = _db()
        scraper = _scraper(["1"])
        scraper.get_matches.side_effect = [FebServerError("500"), ["1"]]
        monkeypatch.setattr(cr, "save_state", MagicMock(side_effect=RuntimeError("mongo down")))
        entries = [RefreshEntry(**{**ENTRY, "group_label": "A"}), RefreshEntry(**{**ENTRY, "group_label": "B", "group_value": "8"})]

        report = refresh_all(db, entries, scraper=scraper, freshness=lambda c: {"collection": c, "up_to_date": True, "missing_codes": [], "games_in_db": 1, "calendar_results": 1,
                             "last_game": "2026-11-20T12:00", "warning": None}, now=lambda: NOW)

        assert len(report) == 2 and report[0]["fatal"] and "mongo down" in report[0]["fatal"] and report[1]["job"] is not None
