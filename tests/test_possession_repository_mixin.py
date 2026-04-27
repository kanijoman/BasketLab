"""Tests for PossessionRepositoryMixin.get_team_possession_stats.

Target file: src/database/repository_possession.py (11% coverage, 40 missing).
All 40 lines are inside get_team_possession_stats.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from database.repository_possession import PossessionRepositoryMixin


# ---------------------------------------------------------------------------
# Minimal concrete class that inherits the mixin
# ---------------------------------------------------------------------------

class FakeRepo(PossessionRepositoryMixin):
    """Minimal concrete repository for testing the mixin."""

    def __init__(self, connection, games=None):
        self.connection = connection
        self._games = games or []

    def get_games_for_team(self, collection_name, team_id, only_with_playbyplay=False):
        return self._games


def _connected():
    m = MagicMock()
    m.is_connected.return_value = True
    return m


def _disconnected():
    m = MagicMock()
    m.is_connected.return_value = False
    return m


# ---------------------------------------------------------------------------
# Connection guard
# ---------------------------------------------------------------------------

class TestConnectionGuard:
    def test_not_connected_returns_empty_dict(self):
        repo = FakeRepo(_disconnected())
        result = repo.get_team_possession_stats("FEB_LF2_2025_A", "t1")
        assert result == {}


# ---------------------------------------------------------------------------
# No games
# ---------------------------------------------------------------------------

class TestNoGames:
    def test_empty_games_returns_zero_possessions(self):
        repo = FakeRepo(_connected(), games=[])
        result = repo.get_team_possession_stats("FEB_LF2_2025_A", "t1")
        assert result["total_possessions"] == 0
        assert result["games_analyzed"] == 0
        assert result["avg_duration"] == 0.0

    def test_empty_games_has_three_duration_buckets(self):
        repo = FakeRepo(_connected(), games=[])
        result = repo.get_team_possession_stats("FEB_LF2_2025_A", "t1")
        pbd = result["possessions_by_duration"]
        assert set(pbd.keys()) == {"<=8s", "8-16s", ">16s"}

    def test_empty_games_buckets_all_zero(self):
        repo = FakeRepo(_connected(), games=[])
        result = repo.get_team_possession_stats("FEB_LF2_2025_A", "t1")
        for bucket in result["possessions_by_duration"].values():
            assert bucket["count"] == 0
            assert bucket["total_points"] == 0
            assert bucket["oer"] == 0.0


# ---------------------------------------------------------------------------
# Games with mocked PossessionAnalyzer
# ---------------------------------------------------------------------------

def _make_game_stats(total=5, avg_dur=8.0,
                     short_c=2, short_pts=4,
                     mid_c=2, mid_pts=3,
                     long_c=1, long_pts=1):
    return {
        "total_possessions": total,
        "avg_duration": avg_dur,
        "possessions_by_duration": {
            "<=8s":  {"count": short_c, "total_points": short_pts},
            "8-16s": {"count": mid_c,   "total_points": mid_pts},
            ">16s":  {"count": long_c,  "total_points": long_pts},
        },
    }


class TestWithGames:
    def _repo(self, game_stats_list):
        conn = _connected()
        games = [{"_id": f"g{i}"} for i in range(len(game_stats_list))]
        repo = FakeRepo(conn, games=games)
        return repo, game_stats_list

    def _run(self, repo, game_stats_list, collection="FEB_LF2_2025_A", team_id="t1"):
        def fake_analyzer_init(game, is_fbcyl=False):
            m = MagicMock()
            idx = games_data.pop(0)
            m.calculate_possessions.return_value = idx
            return m

        games_data = list(game_stats_list)

        with patch("database.repository_possession.PossessionAnalyzer") as MockAnal:
            MockAnal.side_effect = lambda game, is_fbcyl=False: (
                lambda d: (
                    setattr(d, "calculate_possessions", lambda tid: games_data.pop(0))
                    or d
                )
            )(MockAnal.return_value) if False else (
                lambda: (
                    lambda m: (setattr(m, "calculate_possessions", lambda tid: games_data.pop(0)) or m)
                )(MagicMock())
            )()
            # Simpler: patch PossessionAnalyzer class properly
            pass

        # Use a different approach: patch the module-level import
        call_counter = {"n": 0}
        _stats = list(game_stats_list)

        class FakeAnalyzer:
            def __init__(self, game, is_fbcyl=False):
                pass
            def calculate_possessions(self, team_id):
                return _stats[call_counter["n"] - 1] if call_counter["n"] > 0 else _stats[0]

        # Patch at the right location
        with patch("database.repository_possession.PossessionAnalyzer") as MockPA:
            instances = [MagicMock() for _ in _stats]
            for i, st in enumerate(_stats):
                instances[i].calculate_possessions.return_value = st
            MockPA.side_effect = instances
            result = repo.get_team_possession_stats(collection, team_id)

        return result

    def test_single_game_totals(self):
        gs = _make_game_stats(total=5, avg_dur=10.0, short_c=2, short_pts=4,
                               mid_c=2, mid_pts=3, long_c=1, long_pts=1)
        conn = _connected()
        repo = FakeRepo(conn, games=[{"_id": "g1"}])
        with patch("database.playbyplay_analyzer.PossessionAnalyzer") as MockPA:
            inst = MagicMock()
            inst.calculate_possessions.return_value = gs
            MockPA.return_value = inst
            result = repo.get_team_possession_stats("FEB_LF2_2025_A", "t1")

        assert result["total_possessions"] == 5
        assert result["games_analyzed"] == 1

    def test_two_games_aggregate(self):
        gs1 = _make_game_stats(total=5, avg_dur=8.0, short_c=2, short_pts=4,
                                mid_c=2, mid_pts=3, long_c=1, long_pts=1)
        gs2 = _make_game_stats(total=6, avg_dur=9.0, short_c=3, short_pts=6,
                                mid_c=2, mid_pts=4, long_c=1, long_pts=2)
        conn = _connected()
        repo = FakeRepo(conn, games=[{"_id": "g1"}, {"_id": "g2"}])
        with patch("database.playbyplay_analyzer.PossessionAnalyzer") as MockPA:
            inst1, inst2 = MagicMock(), MagicMock()
            inst1.calculate_possessions.return_value = gs1
            inst2.calculate_possessions.return_value = gs2
            MockPA.side_effect = [inst1, inst2]
            result = repo.get_team_possession_stats("FEB_LF2_2025_A", "t1")

        assert result["total_possessions"] == 11
        assert result["games_analyzed"] == 2
        assert result["possessions_by_duration"]["<=8s"]["count"] == 5

    def test_oer_calculation(self):
        gs = _make_game_stats(total=4, avg_dur=8.0, short_c=4, short_pts=8,
                               mid_c=0, mid_pts=0, long_c=0, long_pts=0)
        conn = _connected()
        repo = FakeRepo(conn, games=[{"_id": "g1"}])
        with patch("database.playbyplay_analyzer.PossessionAnalyzer") as MockPA:
            inst = MagicMock()
            inst.calculate_possessions.return_value = gs
            MockPA.return_value = inst
            result = repo.get_team_possession_stats("FEB_LF2_2025_A", "t1")

        # OER = (points / count) * 100 = (8/4)*100 = 200
        assert pytest.approx(result["possessions_by_duration"]["<=8s"]["oer"]) == 200.0

    def test_zero_count_bucket_oer_is_zero(self):
        gs = _make_game_stats(total=2, avg_dur=6.0, short_c=2, short_pts=4,
                               mid_c=0, mid_pts=0, long_c=0, long_pts=0)
        conn = _connected()
        repo = FakeRepo(conn, games=[{"_id": "g1"}])
        with patch("database.playbyplay_analyzer.PossessionAnalyzer") as MockPA:
            inst = MagicMock()
            inst.calculate_possessions.return_value = gs
            MockPA.return_value = inst
            result = repo.get_team_possession_stats("FEB_LF2_2025_A", "t1")

        assert result["possessions_by_duration"]["8-16s"]["oer"] == 0.0

    def test_analyzer_exception_skipped(self):
        conn = _connected()
        repo = FakeRepo(conn, games=[{"_id": "g1"}, {"_id": "g2"}])
        gs_good = _make_game_stats(total=5, avg_dur=8.0, short_c=2, short_pts=4,
                                    mid_c=2, mid_pts=3, long_c=1, long_pts=1)
        with patch("database.playbyplay_analyzer.PossessionAnalyzer") as MockPA:
            inst_bad = MagicMock()
            inst_bad.calculate_possessions.side_effect = Exception("parse error")
            inst_good = MagicMock()
            inst_good.calculate_possessions.return_value = gs_good
            MockPA.side_effect = [inst_bad, inst_good]
            result = repo.get_team_possession_stats("FEB_LF2_2025_A", "t1")

        assert result["games_analyzed"] == 1

    def test_fbcyl_collection_name_detected(self):
        gs = _make_game_stats()
        conn = _connected()
        repo = FakeRepo(conn, games=[{"_id": "g1"}])
        with patch("database.playbyplay_analyzer.PossessionAnalyzer") as MockPA:
            inst = MagicMock()
            inst.calculate_possessions.return_value = gs
            MockPA.return_value = inst
            # FBCYL collection name → is_fbcyl=True
            result = repo.get_team_possession_stats("FBCYL_SeniorA_2025", "t1")
            # Verify PossessionAnalyzer was called with is_fbcyl=True
            MockPA.assert_called_once_with({"_id": "g1"}, is_fbcyl=True)
