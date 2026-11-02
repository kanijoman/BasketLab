"""The names of the teams of a competition (#706).

Bug: ``get_all_teams`` listed FBCYL teams from ``teams.name``, a path FBCYL games do not have (theirs is ``stats.teams.name``), so the list was always empty and the team filter of the
player tables (``GET /collections/?collection=``) had nothing to choose from in any FBCYL competition. The names the web now reads from the rows of the competition are the same set.
"""
import sys
from pathlib import Path

import mongomock
import pymongo
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import fbcyl_games  # noqa: E402
import games  # noqa: E402
from src.local_data.export import export_collection  # noqa: E402

FEB = "L_F_-2_2025_2026_Liga_Regular_B"
FBCYL = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"


@pytest.fixture()
def handler(monkeypatch):
    from src.api import deps

    monkeypatch.setattr(pymongo, "MongoClient", mongomock.MongoClient)
    deps._create_handler.cache_clear()
    handler = deps._create_handler()
    db = handler.connection.client["BASKETBALL"]
    db[FEB].insert_many(games.build_games())
    db[FBCYL].insert_many(fbcyl_games.build_games())
    yield handler
    deps._create_handler.cache_clear()


def test_the_teams_of_an_fbcyl_competition_are_listed_regression(handler):
    assert handler.get_all_teams(FBCYL) == ["ALFA", "BRAVO", "CARLOS", "DELTA"]


@pytest.mark.parametrize("name", [FEB, FBCYL])
def test_the_names_of_the_api_are_the_names_of_the_rows_of_the_competition(handler, name):
    rows = export_collection(handler.connection.client["BASKETBALL"][name], name)["team_rows"]
    assert handler.get_all_teams(name) == sorted({row["team_name"] for row in rows})


@pytest.mark.parametrize("name", [FEB, FBCYL])
def test_the_teams_of_the_report_index_are_those_of_the_api_with_their_ids(handler, tmp_path, name):
    from src.live_prep.package_sealing import ScopedSealer
    from src.local_data.web_data import publish_web_data
    import json

    manifest = publish_web_data(handler, tmp_path, ScopedSealer("a-master-secret-for-the-tests"), [name])
    index = json.loads((tmp_path / manifest["reports"][0]["file"]).read_text(encoding="utf-8"))
    assert {(r["team_id"], r["team"]) for r in index["reports"]} == {(t["id"], t["name"]) for t in handler.get_teams_with_ids(name)}
