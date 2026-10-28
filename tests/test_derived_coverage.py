"""Games without ``DERIVED`` are said, not silently left out (issue #630).

«Análisis pbp» counts only the games that carry ``DERIVED`` (the other tabs read the box score), so a team showed 3 games there and 4 in the rest while 7 games of the
competition had no ``DERIVED``. The coverage of a collection says how many games are pending and which; a failure to compute ``DERIVED`` at insertion leaves a trace.
"""
import logging
from unittest.mock import MagicMock

import pytest
from db_helpers import new_mock_db
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_db
from src.services.derived_coverage_service import DerivedCoverageService
from src.services.pbp_extended_stats_service import ORIGIN_MIN_VERSION


def _feb(code, version=None):
    game = {"_id": code, "HEADER": {"TEAM": [{"id": "A", "name": "Local"}, {"id": "B", "name": "Visitante"}]}}
    if version is not None:
        game["DERIVED"] = {"v": version}
    return game


def _fbcyl(code, version=None):
    game = {"_id": f"{code:024x}", "moves": [], "stats": {"teams": [{"teamIdExtern": 1, "name": "Universidad de León"}, {"teamIdExtern": 2, "name": "Villamuriel"}]}}
    if version is not None:
        game["DERIVED"] = {"v": version}
    return game


def _service(*games):
    db = new_mock_db("coverage")
    if games:
        db["G"].insert_many(list(games))
    handler = MagicMock()
    handler.repository.connection.get_collection.side_effect = lambda name: db[name]
    return handler, DerivedCoverageService(handler)


def test_a_collection_with_every_game_processed_has_nothing_pending():
    _, service = _service(_feb(1, ORIGIN_MIN_VERSION), _feb(2, ORIGIN_MIN_VERSION))
    assert service.get("G") == {"collection": "G", "min_version": ORIGIN_MIN_VERSION, "total": 2, "pending": 0, "pending_games": []}


def test_a_game_without_derived_or_with_an_older_version_is_pending_and_says_whose_it_is_regression():
    """The Challenge 2026/27 of the report: 31 games, the 7 newest without the field. A game of an older ``DERIVED`` version is excluded from the tables too."""
    _, service = _service(_feb(1, ORIGIN_MIN_VERSION), _feb(2), _feb(3, ORIGIN_MIN_VERSION - 1))
    report = service.get("G")
    assert (report["total"], report["pending"]) == (3, 2)
    assert {g["code"]: g["teams"] for g in report["pending_games"]} == {"2": ["Local", "Visitante"], "3": ["Local", "Visitante"]}


def test_fbcyl_games_are_covered_too():
    _, service = _service(_fbcyl(1, ORIGIN_MIN_VERSION), _fbcyl(2))
    report = service.get("G")
    assert report["pending"] == 1 and report["pending_games"][0]["teams"] == ["Universidad de León", "Villamuriel"]


def test_an_empty_or_unknown_collection_has_nothing_pending():
    _, service = _service()
    assert service.get("G")["pending"] == 0 and service.get("OTHER")["total"] == 0


def test_a_long_list_of_pending_games_is_capped_but_counted():
    _, service = _service(*[_feb(n) for n in range(1, 81)])
    report = service.get("G")
    assert report["pending"] == 80 and len(report["pending_games"]) == 50


def test_the_endpoint_gives_the_same_report():
    handler, _ = _service(_feb(1, ORIGIN_MIN_VERSION), _feb(2))
    app.dependency_overrides[get_db] = lambda: handler
    try:
        out = TestClient(app).get("/api/v1/possessions/G/derived-coverage").json()
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert (out["total"], out["pending"], out["pending_games"][0]["code"]) == (2, 1, "2")


def test_a_failure_to_compute_derived_at_insertion_leaves_a_trace_with_the_match_code_regression(monkeypatch, caplog):
    """``_attach_derived_fields`` caught every exception and returned: a game stored without the field and no log of why (#630)."""
    import src.pbp.game_derived as game_derived
    from src.database.repository import _attach_derived_fields

    monkeypatch.setattr(game_derived, "derive_game_fields", MagicMock(side_effect=KeyError("BOXSCORE")))
    game = {"_id": 2524483}
    with caplog.at_level(logging.WARNING, logger="src.database.repository"):
        _attach_derived_fields(game)
    assert "DERIVED" not in game                                       # it still never fails the insert
    assert any("2524483" in r.getMessage() and "KeyError" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("derived, traced", [(None, True), ({"v": 6, "TEAM": []}, False)])
def test_a_game_derive_cannot_read_is_traced_too_and_a_good_one_is_not(monkeypatch, caplog, derived, traced):
    import src.pbp.game_derived as game_derived
    from src.database.repository import _attach_derived_fields

    monkeypatch.setattr(game_derived, "derive_game_fields", MagicMock(return_value=derived))
    game = {"_id": 77}
    with caplog.at_level(logging.WARNING, logger="src.database.repository"):
        _attach_derived_fields(game)
    assert any("77" in r.getMessage() for r in caplog.records) is traced
    assert ("DERIVED" in game) is (not traced)
