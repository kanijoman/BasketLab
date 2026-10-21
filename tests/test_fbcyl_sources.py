"""FBCYL on the live-preparation side (issue #445): packages, round bundles and the rule evaluator read FBCYL collections.

They raised ``NotImplementedError`` ("FBCYL has a different feed"). Each game of a ``FBCYL_*`` collection is now read with a projection of its
own, adapted to the FEB document (``fbcyl_adapter``) and found by ``stats.teams.teamIdExtern``; only FBCYL collections of the same competition
and season feed the teams.
"""
import copy
import gzip
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from db_helpers import new_mock_db

from src.live_prep.db_source import build_package_from_db
from src.live_prep.eval_source import games_from_mongo
from src.live_prep.game_sources import source_collections
from src.live_prep.round_packages import build_round_packages_from_db

RAW = json.loads(gzip.open(Path(__file__).parent / "fixtures" / "fbcyl_game_ok.json.gz").read())
HOME, AWAY = "39675", "40288"
COL = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"
OTHER = "FBCYL_1ª_FASE-GRUPO_A-2_2026_"
OLD = "FBCYL_1ª_FASE-GRUPO_A-1_2025_"
FEB = "SEGUNDA_FEB_2026_2027_Liga_Regular_A"


def game(uuid, when="Oct 4, 2026, 2:30:00 PM", match_id=264330, swap=None):
    doc = copy.deepcopy(RAW)
    doc["uuid"], doc["stats"]["time"], doc["stats"]["idMatchExtern"] = uuid, when, match_id
    doc["_id"] = uuid
    if swap:                        # the same game played by two other teams (stable ids replaced)
        for team, new in zip(doc["stats"]["teams"], swap):
            team["teamIdExtern"] = new
            for p in team["players"]:
                p["teamId"] = new
    return doc


class Handler:
    def __init__(self, collections):
        self.db = new_mock_db()
        for name, docs in collections.items():
            if docs:
                self.db[name].insert_many([copy.deepcopy(d) for d in docs])
        self.repository = MagicMock()
        self.repository.connection.get_collection.side_effect = lambda name: self.db[name]
        self.repository.connection.get_database.return_value = self.db


@pytest.fixture
def world():
    return {
        COL: [game("u1", "Oct 4, 2026, 2:30:00 PM", 1), game("u2", "Oct 11, 2026, 2:30:00 PM", 2)],
        OTHER: [game("u3", "Oct 10, 2026, 5:00:00 PM", 3, swap=(HOME, 77777))],
        OLD: [game("u4", "Oct 4, 2025, 2:30:00 PM", 4)],
        FEB: [{"_id": 1, "HEADER": {"TEAM": [{"id": HOME}]}}],
    }


class TestSources:
    def test_the_own_collection_comes_first_then_the_fbcyl_ones_of_the_same_season_with_a_team(self, world):
        sources = source_collections(Handler(world), COL, [HOME, AWAY])
        assert sources[0] == (COL, True)
        assert {n for n, _ in sources} == {COL, OTHER}      # not last season's, not FEB's
        assert dict(sources)[OTHER] is False

    def test_a_game_of_another_fbcyl_group_is_only_taken_for_the_teams_asked(self, world):
        sources = source_collections(Handler(world), COL, [AWAY])
        assert OTHER not in {n for n, _ in sources}      # the other group has no game of AWAY (its teams are HOME and 77777)


class TestPackages:
    def test_a_package_of_a_fbcyl_match_is_built_with_the_stable_team_ids(self, world):
        package = build_package_from_db(Handler(world), COL, HOME, AWAY, "2026")
        assert package.team["id"] == HOME and package.rival["id"] == AWAY
        assert package.team["name"].startswith("UNIVERSIDAD DE BURGOS")
        assert package.baselines["sample_games"]["league"] == 2 and package.baselines["sample_games"]["own"] == 3   # 2 here + 1 of the other group

    def test_the_players_of_both_teams_have_their_baselines(self, world):
        package = build_package_from_db(Handler(world), COL, HOME, AWAY, "2026")
        assert package.tables["players"] and package.tables["rival_players"]
        assert all(p["team_id"] == HOME for p in package.tables["players"].values())

    def test_there_are_no_zone_tables_without_a_shot_chart(self, world):
        package = build_package_from_db(Handler(world), COL, HOME, AWAY, "2026")
        assert not any(cell["a"] for cell in package.tables["zones"]["league"].values())

    def test_the_package_serialises_and_the_engine_can_use_it(self, world):
        from src.live_core.advice import AdviceEngine
        from src.live_core.package import PreparationPackage

        package = build_package_from_db(Handler(world), COL, HOME, AWAY, "2026")
        assert PreparationPackage.loads(package.dumps()) == package
        assert AdviceEngine.from_package(package) is not None

    def test_a_collection_without_games_gives_a_package_without_history_not_an_error(self):
        package = build_package_from_db(Handler({COL: []}), COL, HOME, AWAY, "2026")
        assert package.baselines["sample_games"]["own"] == 0


class TestRounds:
    def test_a_round_bundle_has_both_sides_of_the_match(self, world):
        match = {"code": "9", "start": "2026-10-25T16:00", "round": 5, "home": {"id": HOME, "name": "UNIVERSIDAD DE BURGOS"}, "away": {"id": AWAY, "name": "CAÑADIO"}}
        built = build_round_packages_from_db(Handler(world), COL, [match], season="2026")
        assert [(b["own_id"], b["rival_id"]) for b in built] == [(HOME, AWAY), (AWAY, HOME)]
        assert all(b["package"].baselines["sample_games"]["league"] == 2 for b in built)


class TestEvaluator:
    def test_the_games_come_adapted_and_in_date_order(self, world):
        games = list(games_from_mongo(Handler(world), COL))
        assert [g["_id"] for g in games] == ["1", "2"]
        assert [g["HEADER"]["starttime"] for g in games] == ["04-10-2026 - 14:30", "11-10-2026 - 14:30"]
        assert games[0]["HEADER"]["source"] == "fbcyl" and games[0]["PLAYBYPLAY"]["LINES"]

    def test_a_game_without_moves_is_left_out(self, world):
        world[COL].append({**game("u5", "Oct 5, 2026, 2:30:00 PM", 5), "moves": []})
        assert [g["_id"] for g in games_from_mongo(Handler(world), COL)] == ["1", "2"]

    def test_the_rule_evaluator_replays_a_fbcyl_season(self, world):
        from src.live_prep.rule_evaluation import evaluate

        evaluation = evaluate(games_from_mongo(Handler(world), COL), collection=COL, season="2026")
        assert evaluation.params["games"] == 2 and evaluation.team_games


class TestRouter:
    def test_the_endpoint_accepts_a_fbcyl_collection(self, world, monkeypatch):
        from fastapi.testclient import TestClient

        from src.api.app import app
        from src.api.deps import get_db
        from src.api.routers import live_package

        handler = Handler(world)
        handler.get_teams_with_ids = lambda collection: [{"id": HOME, "name": "UNIVERSIDAD DE BURGOS"}, {"id": AWAY, "name": "CAÑADIO"}]
        monkeypatch.setattr(live_package, "ROSTER_SOURCE", lambda ids: (_ for _ in ()).throw(AssertionError("FBCYL has no FEB roster")))
        live_package.JOBS.clear()
        app.dependency_overrides[get_db] = lambda: handler
        try:
            client = TestClient(app)
            body = {"collection": COL, "team_id": HOME, "rival_id": AWAY, "passphrase": "clave-segura-1"}
            assert client.post("/api/v1/live/package", json=body).status_code == 202
        finally:
            app.dependency_overrides.clear()
            live_package.JOBS.clear()
