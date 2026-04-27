"""Extended dispersion / consistency tests (FASE 1).

Covers:
- IFQ (lineup quality factor) computation in LineupService
- FBCYL per-game pipeline helper functions (enrich_fbcyl_team_row, enrich_fbcyl_player_row)
- FBCYL team consistency via TeamStatsService
- FBCYL player consistency via PlayerStatsService
- Derived dispersion indexes (volatilidad_triple, sostenibilidad_efg)
- API-level tests for /consistency endpoints (gap from prior test suite)
- Weekly report consistency PNG generation
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import mongomock
import pytest

# Ensure src/ is on the path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from database.aggregation.fbcyl_per_game_pipeline import (
    build_fbcyl_team_per_game_pipeline,
    build_fbcyl_player_per_game_pipeline,
    enrich_fbcyl_team_row,
    enrich_fbcyl_player_row,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fbcyl_game(team_a_name: str, team_b_name: str,
                a_pts: int, b_pts: int,
                a_fg3m: int = 3, a_fg3a: int = 8,
                a_fg2m: int = 10, a_fg2a: int = 20,
                a_ft: int = 4, a_fta: int = 5,
                a_orb: int = 3, a_drb: int = 7,
                a_ast: int = 5, a_tov: int = 4,
                a_blk: int = 1, a_stl: int = 2,
                a_timePlayed: int = 30) -> dict:
    """Build a minimal FBCYL game document."""
    def _team(name, pts, fg3m, fg3a, fg2m, fg2a, ft, fta, orb, drb, ast, tov, blk, stl):
        return {
            "name": name,
            "teamIdExtern": hash(name),
            "teamIdIntern": hash(name) + 1,
            "players": [
                {
                    "uuid": f"player-{name}-1",
                    "name": f"Player1 {name}",
                    "timePlayed": a_timePlayed,
                    "data": {
                        "score": pts, "valoration": 10,
                        "shotsOfThreeSuccessful": fg3m, "shotsOfThreeAttempted": fg3a,
                        "shotsOfTwoSuccessful": fg2m, "shotsOfTwoAttempted": fg2a,
                        "shotsOfOneSuccessful": ft, "shotsOfOneAttempted": fta,
                        "offensiveRebound": orb, "defensiveRebound": drb,
                        "rebounds": orb + drb,
                        "assists": ast, "lost": tov, "block": blk, "steals": stl,
                        "faults": 2,
                    }
                }
            ],
            "data": {
                "score": pts,
                "shotsOfThreeSuccessful": fg3m, "shotsOfThreeAttempted": fg3a,
                "shotsOfTwoSuccessful": fg2m, "shotsOfTwoAttempted": fg2a,
                "shotsOfOneSuccessful": ft, "shotsOfOneAttempted": fta,
                "offensiveRebound": orb, "defensiveRebound": drb,
                "rebounds": orb + drb,
                "assists": ast, "lost": tov, "block": blk, "steals": stl,
                "faults": 2,
            }
        }

    return {
        "stats": {
            "time": "Jan 10, 2025 6:00:00 PM",
            "startDate": "2025-01-10",
            "teams": [
                _team(team_a_name, a_pts, a_fg3m, a_fg3a, a_fg2m, a_fg2a,
                      a_ft, a_fta, a_orb, a_drb, a_ast, a_tov, a_blk, a_stl),
                _team(team_b_name, b_pts, 2, 7, 8, 18, 5, 7, 2, 8, 4, 3, 0, 1),
            ]
        }
    }


def _make_fbcyl_db_with_games(n: int, collection: str = "FBCYL_SE_2025_A") -> MagicMock:
    """Insert n near-identical FBCYL games into a mongomock/mock handler."""
    client = mongomock.MongoClient()
    db = client["basketlab_test"]
    for i in range(n):
        doc = _fbcyl_game("Equipo A", "Equipo B",
                          a_pts=60 + i, b_pts=55 + i,
                          a_fg3m=3 + (i % 3), a_fg3a=8,
                          a_fg2m=10 - (i % 3), a_fg2a=20)
        db[collection].insert_one(doc)
    conn = MagicMock()
    conn.is_connected.return_value = True
    conn.get_collection.side_effect = lambda name: db[name]
    handler = MagicMock()
    handler.is_connected.return_value = True
    handler.connection = conn
    return handler


# ===========================================================================
# 1. IFQ computation in LineupService
# ===========================================================================

class TestIFQ:
    def test_ifq_computed_from_game_log(self):
        """IFQ = mean(net_rating) / std(net_rating) over game log entries."""
        from services.lineup_service import LineupService

        game_log = [
            {"net_rating": 10.0}, {"net_rating": 20.0}, {"net_rating": 15.0},
        ]
        fake_lineup = {
            "players": ["A", "B"], "player_names": ["A", "B"],
            "net_rating": 15.0, "player_photo_urls": [None, None],
            "game_log": game_log,
        }
        handler = MagicMock()
        handler.get_lineup_analysis.return_value = [fake_lineup]

        svc = LineupService(handler)
        results = svc.get_lineup_analysis("FEB_LF2_2025_A", "1", "Team",
                                          include_game_log=False)
        assert len(results) == 1
        row = results[0]
        assert "ifq" in row
        import numpy as np
        expected_std = float(np.std([10.0, 20.0, 15.0]))
        expected_ifq = round(15.0 / expected_std, 2)
        assert row["ifq"] == expected_ifq

    def test_ifq_none_when_std_zero(self):
        """IFQ is None when all net_rating values are identical (std = 0)."""
        from services.lineup_service import LineupService

        game_log = [{"net_rating": 10.0}] * 5
        fake_lineup = {
            "players": ["A"], "net_rating": 10.0,
            "player_photo_urls": [None], "game_log": game_log,
        }
        handler = MagicMock()
        handler.get_lineup_analysis.return_value = [fake_lineup]

        svc = LineupService(handler)
        results = svc.get_lineup_analysis("FEB_LF2_2025_A", "1", "Team",
                                          include_game_log=False)
        assert results[0]["ifq"] is None

    def test_ifq_none_when_fewer_than_3_appearances(self):
        """IFQ is None when lineup appears in fewer than 3 games."""
        from services.lineup_service import LineupService

        fake_lineup = {
            "players": ["A"], "net_rating": 5.0,
            "player_photo_urls": [None],
            "game_log": [{"net_rating": 5.0}, {"net_rating": 8.0}],
        }
        handler = MagicMock()
        handler.get_lineup_analysis.return_value = [fake_lineup]

        svc = LineupService(handler)
        results = svc.get_lineup_analysis("FEB_LF2_2025_A", "1", "Team",
                                          include_game_log=False)
        assert results[0]["ifq"] is None

    def test_game_log_stripped_when_not_requested(self):
        """game_log must NOT appear in results when include_game_log=False."""
        from services.lineup_service import LineupService

        game_log = [{"net_rating": 10.0}, {"net_rating": 20.0}, {"net_rating": 15.0}]
        fake_lineup = {
            "players": ["A"], "net_rating": 15.0,
            "player_photo_urls": [None], "game_log": game_log,
        }
        handler = MagicMock()
        handler.get_lineup_analysis.return_value = [fake_lineup]

        svc = LineupService(handler)
        results = svc.get_lineup_analysis("FEB_LF2_2025_A", "1", "Team",
                                          include_game_log=False)
        assert "game_log" not in results[0]

    def test_game_log_present_when_requested(self):
        """game_log must be kept in results when include_game_log=True."""
        from services.lineup_service import LineupService

        game_log = [{"net_rating": 10.0}, {"net_rating": 20.0}, {"net_rating": 15.0}]
        fake_lineup = {
            "players": ["A"], "net_rating": 15.0,
            "player_photo_urls": [None], "game_log": copy.deepcopy(game_log),
        }
        handler = MagicMock()
        handler.get_lineup_analysis.return_value = [fake_lineup]

        svc = LineupService(handler)
        results = svc.get_lineup_analysis("FEB_LF2_2025_A", "1", "Team",
                                          include_game_log=True)
        assert "game_log" in results[0]


# ===========================================================================
# 2. FBCYL per-game enrichment helpers
# ===========================================================================

class TestEnrichFBCYLTeamRow:
    def _raw(self):
        return {
            "team_name": "Equipo A",
            "points": 70, "opponent_points": 60,
            "fg2_made": 12, "fg2_attempts": 24,
            "fg3_made": 4,  "fg3_attempts": 10,
            "ft_made": 6,   "ft_attempts": 8,
            "off_rebounds": 5, "def_rebounds": 15, "total_rebounds": 20,
            "assists": 10, "steals": 5, "turnovers": 8, "blocks": 2,
            "opp_fg2_made": 10, "opp_fg2_attempts": 22,
            "opp_fg3_made": 3,  "opp_fg3_attempts": 9,
            "opp_ft_attempts": 7, "opp_off_rebounds": 3, "opp_def_rebounds": 14,
            "opp_assists": 8, "opp_steals": 4, "opp_turnovers": 6, "opp_blocks": 1,
            "opp_points": 60,
        }

    def test_efg_computed(self):
        row = enrich_fbcyl_team_row(self._raw())
        # eFG = (FGM + 0.5*3PM) / FGA * 100 = (16 + 2) / 34 * 100
        assert row["efg_pct_game"] == pytest.approx((16 + 2) / 34 * 100, abs=0.1)

    def test_possessions_computed(self):
        row = enrich_fbcyl_team_row(self._raw())
        # poss = FGA + 0.45*FTA + TOV - ORB = 34 + 3.6 + 8 - 5 = 40.6
        assert row["possessions"] == pytest.approx(34 + 0.45 * 8 + 8 - 5, abs=0.1)

    def test_net_game_is_oer_minus_der(self):
        row = enrich_fbcyl_team_row(self._raw())
        assert row["net_game"] == pytest.approx(row["oer_game"] - row["der_game"], abs=0.01)

    def test_zero_fga_gives_none_efg(self):
        raw = self._raw()
        raw["fg2_attempts"] = 0
        raw["fg3_attempts"] = 0
        row = enrich_fbcyl_team_row(raw)
        assert row["efg_pct_game"] is None

    def test_three_point_rate_computed(self):
        row = enrich_fbcyl_team_row(self._raw())
        # 3PR = fg3a / fga * 100 = 10/34 * 100
        assert row["three_point_rate_game"] == pytest.approx(10 / 34 * 100, abs=0.1)


class TestEnrichFBCYLPlayerRow:
    def _raw(self):
        return {
            "player_id": "uuid-1",
            "team_name": "Equipo A",
            "pts": 18, "minutes": 30,
            "p1a": 4, "p1m": 3,
            "p2a": 10, "p2m": 4,
            "p3a": 6,  "p3m": 2,
            "ro": 2, "rd": 5, "rt": 7,
            "assist": 3, "to": 2, "bs": 1, "st": 2, "pf": 3,
        }

    def test_fg3_pct_computed(self):
        row = enrich_fbcyl_player_row(self._raw())
        assert row["fg3_pct_game"] == pytest.approx(2 / 6 * 100, abs=0.1)

    def test_efg_computed(self):
        row = enrich_fbcyl_player_row(self._raw())
        # eFG = (fg2m + 1.5*fg3m) / fga = (4 + 3) / 16 * 100
        assert row["efg_pct_game"] == pytest.approx((4 + 3) / 16 * 100, abs=0.1)

    def test_zero_fga_gives_none(self):
        raw = self._raw()
        raw["p2a"] = 0
        raw["p3a"] = 0
        row = enrich_fbcyl_player_row(raw)
        assert row["efg_pct_game"] is None


# ===========================================================================
# 3. TeamStatsService FBCYL consistency
# ===========================================================================

class TestFBCYLTeamConsistency:
    def test_returns_own_and_rival_keys_for_fbcyl(self):
        """FBCYL consistency returns both own/rival dicts (not empty {} anymore)."""
        from services.team_stats_service import TeamStatsService

        handler = _make_fbcyl_db_with_games(5, "FBCYL_SE_2025_A")
        svc = TeamStatsService(handler)
        result = svc.get_consistency("FBCYL_SE_2025_A")
        assert "own" in result
        assert "rival" in result

    def test_own_contains_team_data_for_fbcyl(self):
        """At least one team should have CV metrics after 5 games."""
        from services.team_stats_service import TeamStatsService

        handler = _make_fbcyl_db_with_games(5, "FBCYL_SE_2025_A")
        svc = TeamStatsService(handler)
        result = svc.get_consistency("FBCYL_SE_2025_A")
        own = result["own"]
        assert len(own) > 0
        for team_stats in own.values():
            for stat_data in team_stats.values():
                if isinstance(stat_data, dict) and "cv" in stat_data:
                    assert stat_data["n"] >= 3
                    assert stat_data["cv"] >= 0.0

    def test_volatilidad_triple_present_for_fbcyl(self):
        """volatilidad_triple should appear in own map for FBCYL."""
        from services.team_stats_service import TeamStatsService

        handler = _make_fbcyl_db_with_games(5, "FBCYL_SE_2025_A")
        svc = TeamStatsService(handler)
        result = svc.get_consistency("FBCYL_SE_2025_A")
        own = result["own"]
        # At least one team should have the derived index
        has_vol = any("volatilidad_triple" in ts for ts in own.values())
        assert has_vol

    def test_empty_collection_returns_empty(self):
        """No games → empty dict returned, no exception raised."""
        from services.team_stats_service import TeamStatsService

        handler = _make_fbcyl_db_with_games(0, "FBCYL_SE_2025_A")
        svc = TeamStatsService(handler)
        result = svc.get_consistency("FBCYL_SE_2025_A")
        assert result == {}


# ===========================================================================
# 4. PlayerStatsService FBCYL consistency
# ===========================================================================

class TestFBCYLPlayerConsistency:
    def test_returns_player_dict_for_fbcyl(self):
        """FBCYL player consistency returns {player_uuid: {stat_key: {...}}}."""
        from services.player_stats_service import PlayerStatsService

        handler = _make_fbcyl_db_with_games(5, "FBCYL_SE_2025_A")
        svc = PlayerStatsService(handler)
        result = svc.get_consistency("FBCYL_SE_2025_A")
        assert isinstance(result, dict)
        # Each value is a dict of stat_key → {mean, std, cv, n}
        for player_data in result.values():
            for stat_data in player_data.values():
                assert "mean" in stat_data
                assert "std" in stat_data
                assert "cv" in stat_data

    def test_cv_non_negative_for_fbcyl(self):
        """CV values must be non-negative."""
        from services.player_stats_service import PlayerStatsService

        handler = _make_fbcyl_db_with_games(5, "FBCYL_SE_2025_A")
        svc = PlayerStatsService(handler)
        result = svc.get_consistency("FBCYL_SE_2025_A")
        for player_data in result.values():
            for stat_data in player_data.values():
                assert stat_data["cv"] >= 0


# ===========================================================================
# 5. Derived dispersion indexes (FEB)
# ===========================================================================

class TestDerivedIndexes:
    def _build_own_map(self):
        """Minimal own_map with two teams for index computation."""
        from services.team_stats_service import _add_derived_indexes
        own_map = {
            "Team A": {
                "fg3_percentage":        {"mean": 35.0, "std": 8.0, "cv": 22.9, "n": 10},
                "fg3_attempts_per_game": {"mean": 18.0, "std": 3.0, "cv": 16.7, "n": 10},
                "efg_percentage":        {"mean": 52.0, "std": 5.0, "cv": 9.6,  "n": 10},
            },
            "Team B": {
                "fg3_percentage":        {"mean": 30.0, "std": 4.0, "cv": 13.3, "n": 10},
                "fg3_attempts_per_game": {"mean": 10.0, "std": 2.0, "cv": 20.0, "n": 10},
                "efg_percentage":        {"mean": 48.0, "std": 4.0, "cv": 8.3,  "n": 10},
            },
        }
        return own_map

    def test_volatilidad_triple_computed(self):
        from services.team_stats_service import _add_derived_indexes
        own_map = self._build_own_map()
        _add_derived_indexes(own_map)
        # Team A: std(fg3_pct)=8 × mean(fg3a)=18 = 144
        assert own_map["Team A"]["volatilidad_triple"]["value"] == pytest.approx(144.0, abs=0.01)
        # Team B: std(fg3_pct)=4 × mean(fg3a)=10 = 40
        assert own_map["Team B"]["volatilidad_triple"]["value"] == pytest.approx(40.0, abs=0.01)

    def test_sostenibilidad_efg_relative_to_league(self):
        from services.team_stats_service import _add_derived_indexes
        own_map = self._build_own_map()
        _add_derived_indexes(own_map)
        # league mean eFG = (52 + 48) / 2 = 50
        assert own_map["Team A"]["sostenibilidad_efg"]["value"] == pytest.approx(2.0, abs=0.01)
        assert own_map["Team B"]["sostenibilidad_efg"]["value"] == pytest.approx(-2.0, abs=0.01)

    def test_no_error_when_fields_missing(self):
        from services.team_stats_service import _add_derived_indexes
        own_map = {"Team C": {"points_per_game": {"mean": 70.0, "std": 5.0, "cv": 7.1, "n": 10}}}
        _add_derived_indexes(own_map)  # must not raise
        assert "volatilidad_triple" not in own_map["Team C"]


# ---------------------------------------------------------------------------
# Phantom-player regression (FBCYL timePlayed=40 + all stats=0)
# ---------------------------------------------------------------------------

def _phantom_player_doc(collection: str = "FBCYL_SE_2025_A") -> dict:
    """Game document containing one real player + one phantom (timePlayed=40, stats=0)."""
    return {
        "stats": {
            "time": "Jan 10, 2025 6:00:00 PM",
            "startDate": "2025-01-10",
            "teams": [
                {
                    "name": "Real Team",
                    "teamIdExtern": 1,
                    "players": [
                        {   # Real player: played 28 minutes, has stats
                            "uuid": "real-player",
                            "actorId": "actor-real",
                            "name": "Real Player",
                            "timePlayed": 28,
                            "data": {
                                "score": 12, "valoration": 15,
                                "shotsOfTwoSuccessful": 4, "shotsOfTwoAttempted": 8,
                                "shotsOfThreeSuccessful": 1, "shotsOfThreeAttempted": 3,
                                "shotsOfOneSuccessful": 2, "shotsOfOneAttempted": 3,
                                "offensiveRebound": 1, "defensiveRebound": 3,
                                "assists": 2, "lost": 1, "block": 0, "steals": 1,
                                "faults": 2, "faultReceived": 3,
                            },
                        },
                        {   # Phantom: registered but never played; system assigns 40 min
                            "uuid": "phantom-player",
                            "actorId": "actor-phantom",
                            "name": "Phantom Player",
                            "timePlayed": 40,
                            "data": {
                                "score": 0, "valoration": 0,
                                "shotsOfTwoSuccessful": 0, "shotsOfTwoAttempted": 0,
                                "shotsOfThreeSuccessful": 0, "shotsOfThreeAttempted": 0,
                                "shotsOfOneSuccessful": 0, "shotsOfOneAttempted": 0,
                                "offensiveRebound": 0, "defensiveRebound": 0,
                                "assists": 0, "lost": 0, "block": 0, "steals": 0,
                                "faults": 0, "faultReceived": 0,
                            },
                        },
                    ],
                    "data": {"score": 12, "shotsOfTwoSuccessful": 4, "shotsOfTwoAttempted": 8,
                             "shotsOfThreeSuccessful": 1, "shotsOfThreeAttempted": 3,
                             "shotsOfOneSuccessful": 2, "shotsOfOneAttempted": 3,
                             "offensiveRebound": 1, "defensiveRebound": 3,
                             "assists": 2, "lost": 1, "block": 0, "steals": 1, "faults": 2},
                },
                {
                    "name": "Opponent",
                    "teamIdExtern": 2,
                    "players": [
                        {"uuid": "opp-p1", "actorId": "actor-opp", "name": "Opp Player",
                         "timePlayed": 35,
                         "data": {"score": 10, "valoration": 8,
                                  "shotsOfTwoSuccessful": 3, "shotsOfTwoAttempted": 7,
                                  "shotsOfThreeSuccessful": 1, "shotsOfThreeAttempted": 4,
                                  "shotsOfOneSuccessful": 2, "shotsOfOneAttempted": 2,
                                  "offensiveRebound": 1, "defensiveRebound": 4,
                                  "assists": 3, "lost": 2, "block": 1, "steals": 0,
                                  "faults": 3, "faultReceived": 2}},
                    ],
                    "data": {"score": 10, "shotsOfTwoSuccessful": 3, "shotsOfTwoAttempted": 7,
                             "shotsOfThreeSuccessful": 1, "shotsOfThreeAttempted": 4,
                             "shotsOfOneSuccessful": 2, "shotsOfOneAttempted": 2,
                             "offensiveRebound": 1, "defensiveRebound": 4,
                             "assists": 3, "lost": 2, "block": 1, "steals": 0, "faults": 3},
                },
            ],
        }
    }


class TestPhantomPlayerFilterRegression:
    """Regression: FBCYL phantom player (timePlayed=40, all stats=0) must be excluded.

    Bug: players inscribed to a match but who never played appear in raw FBCYL
    data with timePlayed=40 and every activity stat set to 0.  The system was
    incorrectly counting them as having played a full 40-minute game.
    Fix: filter them out in both FBCYL pipelines and in repository_inout.py.
    """

    def _run_player_per_game(self, doc: dict, collection: str = "FBCYL_SE_2025_A"):
        client = mongomock.MongoClient()
        db = client["basketlab_test"]
        db[collection].insert_one(doc)
        pipeline = build_fbcyl_player_per_game_pipeline()
        return list(db[collection].aggregate(pipeline))

    def test_real_player_is_kept(self):
        """A player with timePlayed=28 and non-zero stats must appear in results."""
        results = self._run_player_per_game(_phantom_player_doc())
        names = {r["player_name"] for r in results}
        assert "Real Player" in names, f"Real player must be retained; got: {names}"

    def test_phantom_player_is_excluded_regression(self):
        """Regression: phantom player (timePlayed=40, all stats=0) must NOT appear."""
        results = self._run_player_per_game(_phantom_player_doc())
        names = {r["player_name"] for r in results}
        assert "Phantom Player" not in names, (
            f"Phantom player (timePlayed=40, stats=0) was not filtered out; got: {names}"
        )

    def test_real_player_with_40min_is_kept(self):
        """A player who genuinely played 40 minutes with non-zero stats must be kept."""
        doc = _phantom_player_doc()
        # Make the real player's timePlayed = 40 (legitimate full-game performance)
        doc["stats"]["teams"][0]["players"][0]["timePlayed"] = 40
        results = self._run_player_per_game(doc)
        names = {r["player_name"] for r in results}
        assert "Real Player" in names, (
            "A player with timePlayed=40 but actual stats must NOT be filtered out"
        )


# ===========================================================================
# 6. API-level consistency endpoint tests
# ===========================================================================

@pytest.fixture
def consistency_api_client(feb_game_doc):
    """TestClient with mocked DB for the team/player consistency endpoints."""
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.deps import get_db

    client = mongomock.MongoClient()
    db_mock = client["basketlab_test"]
    db_mock["FEB_LF2_2025_A"].insert_one(dict(feb_game_doc))

    conn_mock = MagicMock()
    conn_mock.get_collection.side_effect = lambda name: db_mock[name]

    handler = MagicMock()
    handler.is_connected.return_value = True
    handler.connection = conn_mock

    app.dependency_overrides[get_db] = lambda: handler
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestConsistencyAPIEndpoints:
    def test_team_consistency_returns_200(self, consistency_api_client):
        resp = consistency_api_client.get("/api/v1/teams/FEB_LF2_2025_A/consistency")
        assert resp.status_code == 200

    def test_team_consistency_has_own_rival_keys(self, consistency_api_client):
        resp = consistency_api_client.get("/api/v1/teams/FEB_LF2_2025_A/consistency")
        body = resp.json()
        # FEB consistency returns {own: {...}, rival: {...}} or {} if not enough data
        assert isinstance(body, dict)
        if body:
            assert "own" in body
            assert "rival" in body

    def test_player_consistency_returns_200(self, consistency_api_client):
        resp = consistency_api_client.get("/api/v1/players/FEB_LF2_2025_A/consistency")
        assert resp.status_code == 200

    def test_player_consistency_returns_dict(self, consistency_api_client):
        resp = consistency_api_client.get("/api/v1/players/FEB_LF2_2025_A/consistency")
        body = resp.json()
        assert isinstance(body, dict)


# ===========================================================================
# 7. build_consistency_rows helper
# ===========================================================================

class TestBuildConsistencyRows:
    def test_rows_match_teams(self):
        from services._weekly_report_helpers import build_consistency_rows
        own_map = {
            "Team A": {"net_rating": {"mean": 5.0, "std": 4.0, "cv": 80.0, "n": 10}},
            "Team B": {"net_rating": {"mean": 3.0, "std": 1.0, "cv": 33.3, "n": 10}},
        }
        rows, colors = build_consistency_rows(own_map)
        assert len(rows) == 2
        assert len(colors) == 2

    def test_empty_own_map_returns_empty(self):
        from services._weekly_report_helpers import build_consistency_rows
        rows, colors = build_consistency_rows({})
        assert rows == []
        assert colors == []

    def test_sorted_by_net_rating_cv_ascending(self):
        from services._weekly_report_helpers import build_consistency_rows
        own_map = {
            "Volatile": {"net_rating": {"mean": 2.0, "std": 5.0, "cv": 250.0, "n": 10}},
            "Stable":   {"net_rating": {"mean": 5.0, "std": 1.0, "cv": 20.0, "n": 10}},
        }
        rows, _ = build_consistency_rows(own_map)
        # First row (most consistent) should be "Stable"
        assert rows[0][0] == "Stable"
