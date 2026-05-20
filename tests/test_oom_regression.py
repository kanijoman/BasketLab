"""OOM regression tests for Rankings and Possessions flows.

Verifies:
1. team_utils.get_available_teams_from_collection() uses a MongoDB projection
   (does NOT load PLAYBYPLAY/BOXSCORE full docs into memory).
2. repository_possession.get_team_possession_stats() passes a minimal
   projection to get_games_for_team() (not None).
3. _aggregate_game_possession() produces a correct weighted avg_duration
   (O(1) accumulator, replaces the old O(N) list).
4. PlayerStatsService.load_season_data() caches results — the DB is queried
   at most once for the same collection + filters within 5 minutes.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from utils.team_utils import get_available_teams_from_collection
from database.repository_possession import _aggregate_game_possession, _empty_possession_result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _feb_doc_with_boxscore(team_code: str, team_name: str, team_id: str) -> dict:
    """Minimal FEB doc that contains BOXSCORE.TEAM.TOTAL + full PLAYBYPLAY fat payload."""
    return {
        "BOXSCORE": {
            "TEAM": [
                {"TOTAL": {"teamCode": team_code, "name": team_name, "id": team_id}},
            ]
        },
        # Simulate fat payload that should NOT be loaded
        "PLAYBYPLAY": {"LINES": [{"action": "x"} for _ in range(500)]},
    }


def _fbcyl_doc(team_name: str, team_id_extern, team_id_intern) -> dict:
    """Minimal FBCYL doc with moves array that should NOT be loaded."""
    return {
        "stats": {
            "teams": [
                {"name": team_name, "teamIdExtern": team_id_extern, "teamIdIntern": team_id_intern}
            ]
        },
        "moves": [{"action": "x"} for _ in range(500)],
    }


def _make_db_handler(collection_name: str, docs: list):
    """Fake db_handler whose .connection.get_collection() returns a mock collection."""
    conn = MagicMock()
    conn.is_connected.return_value = True
    col = MagicMock()
    # find() returns docs regardless of args — we'll inspect call args
    col.find.return_value = iter(docs)
    conn.get_collection.return_value = col
    db_handler = MagicMock()
    db_handler.connection = conn
    return db_handler, col


# ---------------------------------------------------------------------------
# Test 1 — team_utils: find() called with non-None projection
# ---------------------------------------------------------------------------

class TestTeamUtilsProjection:
    """get_available_teams_from_collection must NOT call find({}) without projection."""

    def test_feb_find_called_with_projection(self):
        docs = [_feb_doc_with_boxscore("ABC", "Team ABC", "t1")]
        handler, col = _make_db_handler("FEB_LF2_2025_A", docs)

        get_available_teams_from_collection(handler, "FEB_LF2_2025_A")

        assert col.find.called, "find() must be called"
        args, kwargs = col.find.call_args
        projection = args[1] if len(args) > 1 else kwargs.get("projection")
        assert projection is not None, "find() must include a projection to restrict fields"
        # Projection must NOT include PLAYBYPLAY
        assert "PLAYBYPLAY" not in str(projection), \
            "Projection must exclude PLAYBYPLAY to avoid OOM"

    def test_fbcyl_find_called_with_projection(self):
        docs = [_fbcyl_doc("Team X", 101, 202)]
        handler, col = _make_db_handler("FBCYL_2025_A", docs)

        get_available_teams_from_collection(handler, "FBCYL_2025_A")

        assert col.find.called
        args, kwargs = col.find.call_args
        projection = args[1] if len(args) > 1 else kwargs.get("projection")
        assert projection is not None, "FBCYL find() must include a projection"
        assert "moves" not in str(projection), \
            "Projection must exclude 'moves' to avoid OOM"

    def test_feb_teams_correctly_extracted_with_projection(self):
        """Projection does not break team discovery."""
        doc = _feb_doc_with_boxscore("XYZ", "Team XYZ", "t99")
        handler, col = _make_db_handler("FEB_LF2_2025_A", [doc])
        col.find.return_value = iter([doc])

        result = get_available_teams_from_collection(handler, "FEB_LF2_2025_A")

        names = [t["name"] for t in result]
        assert "Team XYZ" in names

    def test_fbcyl_teams_correctly_extracted_with_projection(self):
        doc = _fbcyl_doc("Team FBCYL", 55, 66)
        handler, col = _make_db_handler("FBCYL_2025_A", [doc])
        col.find.return_value = iter([doc])

        result = get_available_teams_from_collection(handler, "FBCYL_2025_A")

        names = [t["name"] for t in result]
        assert "Team FBCYL" in names

    def test_empty_collection_returns_empty_list(self):
        handler, col = _make_db_handler("FEB_LF2_2025_A", [])
        col.find.return_value = iter([])
        result = get_available_teams_from_collection(handler, "FEB_LF2_2025_A")
        assert result == []


# ---------------------------------------------------------------------------
# Test 2 — possession mixin: get_games_for_team called with projection != None
# ---------------------------------------------------------------------------

class TestPossessionProjection:
    """get_team_possession_stats must pass a projection to get_games_for_team."""

    def _make_fake_repo(self, collection_name: str = "FEB_LF2_2025_A") -> MagicMock:
        from database.repository_possession import PossessionRepositoryMixin

        class FakePossRepo(PossessionRepositoryMixin):
            def __init__(self):
                self.connection = MagicMock()
                self.connection.is_connected.return_value = True
                self._get_games_calls = []

            def get_games_for_team(self, col, team_id, only_with_playbyplay=False, projection=None):
                self._get_games_calls.append({"projection": projection})
                return []  # empty → skip analysis

        return FakePossRepo()

    def test_feb_projection_is_not_none(self):
        repo = self._make_fake_repo()
        repo.get_team_possession_stats("FEB_LF2_2025_A", "t1")
        assert repo._get_games_calls, "get_games_for_team must be called"
        proj = repo._get_games_calls[0]["projection"]
        assert proj is not None, "Projection must not be None for FEB possession query"

    def test_fbcyl_projection_is_not_none(self):
        repo = self._make_fake_repo()
        repo.get_team_possession_stats("FBCYL_2025_A", "t1")
        assert repo._get_games_calls
        proj = repo._get_games_calls[0]["projection"]
        assert proj is not None, "Projection must not be None for FBCYL possession query"

    def test_feb_projection_includes_playbyplay_lines(self):
        repo = self._make_fake_repo()
        repo.get_team_possession_stats("FEB_LF2_2025_A", "t1")
        proj = repo._get_games_calls[0]["projection"]
        assert "PLAYBYPLAY.LINES" in proj, "FEB projection must include PLAYBYPLAY.LINES"

    def test_fbcyl_projection_includes_moves(self):
        repo = self._make_fake_repo()
        repo.get_team_possession_stats("FBCYL_2025_A", "t1")
        proj = repo._get_games_calls[0]["projection"]
        assert "moves" in proj, "FBCYL projection must include moves"


# ---------------------------------------------------------------------------
# Test 3 — _aggregate_game_possession: weighted avg (O(1) accumulator)
# ---------------------------------------------------------------------------

class TestAggregateGamePossession:
    """_aggregate_game_possession returns a correct weighted duration tuple."""

    def _game_stats(self, avg_dur: float, total: int,
                    fast=(5, 10), med=(3, 8), slow=(2, 6)) -> dict:
        return {
            "avg_duration": avg_dur,
            "total_possessions": total,
            "possessions_by_duration": {
                "<=8s":  {"count": fast[0], "total_points": fast[1]},
                "8-16s": {"count": med[0],  "total_points": med[1]},
                ">16s":  {"count": slow[0], "total_points": slow[1]},
            },
        }

    def test_weighted_duration_is_avg_times_total(self):
        gs = self._game_stats(avg_dur=10.0, total=20)
        weighted, _, _, _ = _aggregate_game_possession(gs)
        assert weighted == pytest.approx(200.0)

    def test_fast_bucket_passthrough(self):
        gs = self._game_stats(avg_dur=5.0, total=10, fast=(4, 12))
        _, fast, _, _ = _aggregate_game_possession(gs)
        assert fast["count"] == 4
        assert fast["total_points"] == 12

    def test_medium_bucket_passthrough(self):
        gs = self._game_stats(avg_dur=5.0, total=10, med=(3, 9))
        _, _, med, _ = _aggregate_game_possession(gs)
        assert med["count"] == 3
        assert med["total_points"] == 9

    def test_slow_bucket_passthrough(self):
        gs = self._game_stats(avg_dur=5.0, total=10, slow=(2, 4))
        _, _, _, slow = _aggregate_game_possession(gs)
        assert slow["count"] == 2
        assert slow["total_points"] == 4

    def test_weighted_avg_over_two_games(self):
        """Accumulated weighted avg must equal sum(dur*poss)/sum(poss)."""
        g1 = self._game_stats(avg_dur=8.0, total=10)
        g2 = self._game_stats(avg_dur=12.0, total=20)
        w1, _, _, _ = _aggregate_game_possession(g1)
        w2, _, _, _ = _aggregate_game_possession(g2)
        total_w = w1 + w2   # 80 + 240 = 320
        total_p = g1["total_possessions"] + g2["total_possessions"]  # 30
        avg = total_w / total_p  # 320/30 ≈ 10.667
        assert avg == pytest.approx(10.666666, rel=1e-3)

    def test_zero_total_possessions_gives_zero_weight(self):
        gs = self._game_stats(avg_dur=5.0, total=0)
        weighted, _, _, _ = _aggregate_game_possession(gs)
        assert weighted == 0.0


# ---------------------------------------------------------------------------
# Test 4 — PlayerStatsService TTLCache: DB called at most once per key
# ---------------------------------------------------------------------------

class TestPlayerStatsCacheTTL:
    """load_season_data must cache results and not re-query the DB for the same params."""

    def _make_svc(self, players=None):
        from services.player_stats_service import PlayerStatsService

        handler = MagicMock()
        handler.get_player_stats.return_value = players or []
        handler.get_team_stats.return_value = []
        handler.get_opponent_stats.return_value = []
        return PlayerStatsService(handler), handler

    def test_second_call_same_params_does_not_hit_db(self):
        svc, handler = self._make_svc()
        svc.load_season_data("FEB_LF2_2025_A")
        svc.load_season_data("FEB_LF2_2025_A")
        handler.get_player_stats.assert_called_once()

    def test_different_collection_hits_db_again(self):
        svc, handler = self._make_svc()
        svc.load_season_data("FEB_LF2_2025_A")
        svc.load_season_data("FBCYL_2025_A")
        assert handler.get_player_stats.call_count == 2

    def test_different_venue_filter_hits_db_again(self):
        svc, handler = self._make_svc()
        svc.load_season_data("FEB_LF2_2025_A", venue_filter=None)
        svc.load_season_data("FEB_LF2_2025_A", venue_filter=True)
        assert handler.get_player_stats.call_count == 2

    def test_cache_returns_same_data(self):
        players = [{"player_id": "p1", "player_name": "Test"}]
        svc, handler = self._make_svc(players=players)
        r1 = svc.load_season_data("FEB_LF2_2025_A")
        r2 = svc.load_season_data("FEB_LF2_2025_A")
        assert r1 == r2

    def test_cache_miss_after_different_team_filter(self):
        svc, handler = self._make_svc()
        svc.load_season_data("FEB_LF2_2025_A", team_filter="Team A")
        svc.load_season_data("FEB_LF2_2025_A", team_filter="Team B")
        assert handler.get_player_stats.call_count == 2
