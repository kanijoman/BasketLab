"""Regression tests for scraper metadata injection.

Verifies that:
- FEB documents receive the five ``_*`` metadata fields derived from HEADER.
- ``_season`` is correctly derived from ``HEADER.starttime`` (Sep–Aug boundary).
- ``HEADER.round`` with embedded quotes/whitespace is normalised to a clean group letter.
- FBCYL documents receive the six ``_*`` metadata fields when ``league_ctx`` is supplied.
- FBCYL documents without ``league_ctx`` are unmodified (backward-compat).
"""

import pytest


# ---------------------------------------------------------------------------
# _derive_season helper (FEBApiClient static method)
# ---------------------------------------------------------------------------

class TestDeriveSeason:
    """FEBApiClient._derive_season — season start year from HEADER.starttime."""

    @pytest.fixture
    def derive(self):
        from src.scraper.api_client import FEBApiClient
        return FEBApiClient._derive_season

    def test_october_returns_same_year_regression(self, derive):
        """Season 2025/26 starts in October 2025 → _season=='2025'."""
        assert derive("05-10-2025 - 12:30") == "2025"

    def test_september_returns_same_year(self, derive):
        """September is still the same season start year."""
        assert derive("15-09-2024 - 18:00") == "2024"

    def test_february_returns_prior_year_regression(self, derive):
        """February 2026 belongs to the 2025/26 season → _season=='2025'."""
        assert derive("14-02-2026 - 19:30") == "2025"

    def test_august_returns_prior_year(self, derive):
        """August is the end of the previous season."""
        assert derive("31-08-2025 - 20:00") == "2024"

    def test_january_returns_prior_year(self, derive):
        assert derive("10-01-2026 - 17:00") == "2025"

    def test_malformed_string_returns_empty(self, derive):
        """Invalid format must not raise — returns empty string."""
        assert derive("not-a-date") == ""

    def test_empty_string_returns_empty(self, derive):
        assert derive("") == ""


# ---------------------------------------------------------------------------
# _inject_feb_metadata (FEBApiClient static method)
# ---------------------------------------------------------------------------

class TestInjectFebMetadata:
    """FEBApiClient._inject_feb_metadata — in-place mutation of FEB doc."""

    @pytest.fixture
    def inject(self):
        from src.scraper.api_client import FEBApiClient
        return FEBApiClient._inject_feb_metadata

    def _make_doc(self):
        return {
            "HEADER": {
                "CompID": "218",
                "competition": "L.F.-2",
                "round": '"B"                 ',  # raw value from FEB API
                "starttime": "05-10-2025 - 12:30",
            }
        }

    def test_league_field_is_feb_regression(self, inject):
        doc = self._make_doc()
        inject(doc)
        assert doc["_league"] == "FEB"

    def test_comp_id_extracted_regression(self, inject):
        doc = self._make_doc()
        inject(doc)
        assert doc["_comp_id"] == "218"

    def test_competition_name_extracted(self, inject):
        doc = self._make_doc()
        inject(doc)
        assert doc["_competition"] == "L.F.-2"

    def test_group_normalised_regression(self, inject):
        """round='\"B\"                 ' must normalise to 'B'."""
        doc = self._make_doc()
        inject(doc)
        assert doc["_group"] == "B"

    def test_season_derived_from_starttime_regression(self, inject):
        doc = self._make_doc()
        inject(doc)
        assert doc["_season"] == "2025"

    def test_all_five_fields_present(self, inject):
        doc = self._make_doc()
        inject(doc)
        for field in ("_league", "_comp_id", "_competition", "_group", "_season"):
            assert field in doc, f"Missing field: {field}"

    def test_missing_header_does_not_raise(self, inject):
        """Document without HEADER must not raise — fields set to empty string."""
        doc: dict = {}
        inject(doc)
        assert doc["_league"] == "FEB"
        assert doc["_comp_id"] == ""
        assert doc["_group"] == ""
        assert doc["_season"] == ""


# ---------------------------------------------------------------------------
# FBCYLWebScraper.get_match_complete_data with league_ctx
# ---------------------------------------------------------------------------

class TestFBCYLGetMatchCompleteData:
    """get_match_complete_data — league_ctx kwarg injects _* metadata."""

    @pytest.fixture
    def scraper_with_stub(self, monkeypatch):
        """Return a FBCYLWebScraper whose HTTP methods are stubbed."""
        from src.scraper.fbcyl_scraper import FBCYLWebScraper
        from src.scraper.web_client import WebClient

        scraper = FBCYLWebScraper(WebClient())

        # Stub network calls to return minimal dicts
        monkeypatch.setattr(scraper, "get_match_json_moves", lambda uuid: {"move": "stub"})
        monkeypatch.setattr(scraper, "get_match_json_stats", lambda uuid: {"stat": "stub"})
        return scraper

    _CTX = {
        "gender": "Femenino",
        "territory": "0",
        "category": "Senior",
        "competition_id": "12345",
        "season": "2025",
    }

    def test_league_ctx_injects_all_fields_regression(self, scraper_with_stub):
        doc = scraper_with_stub.get_match_complete_data("abc123", league_ctx=self._CTX)
        assert doc is not None
        for field in ("_league", "_gender", "_territory", "_category", "_competition", "_season"):
            assert field in doc, f"Missing field: {field}"

    def test_league_field_is_fbcyl(self, scraper_with_stub):
        doc = scraper_with_stub.get_match_complete_data("abc123", league_ctx=self._CTX)
        assert doc["_league"] == "FBCYL"

    def test_season_from_ctx_regression(self, scraper_with_stub):
        doc = scraper_with_stub.get_match_complete_data("abc123", league_ctx=self._CTX)
        assert doc["_season"] == "2025"

    def test_no_league_ctx_no_metadata_regression(self, scraper_with_stub):
        """Calling without league_ctx must not add any _* fields — backward-compat."""
        doc = scraper_with_stub.get_match_complete_data("abc123")
        assert doc is not None
        assert "_league" not in doc
        assert "_season" not in doc

    def test_uuid_and_data_always_present(self, scraper_with_stub):
        doc = scraper_with_stub.get_match_complete_data("myuuid", league_ctx=self._CTX)
        assert doc["uuid"] == "myuuid"
        assert doc["moves"] == {"move": "stub"}
        assert doc["stats"] == {"stat": "stub"}

    def test_returns_none_when_both_apis_fail(self, monkeypatch):
        from src.scraper.fbcyl_scraper import FBCYLWebScraper
        from src.scraper.web_client import WebClient

        scraper = FBCYLWebScraper(WebClient())
        monkeypatch.setattr(scraper, "get_match_json_moves", lambda uuid: None)
        monkeypatch.setattr(scraper, "get_match_json_stats", lambda uuid: None)
        assert scraper.get_match_complete_data("fail", league_ctx=self._CTX) is None
