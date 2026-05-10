"""Tests for MultiPhaseService — TDD red phase.

Covers:
- Combined team stats across two collections (totals merged by team name)
- Combined player stats across two collections
- Breakdown view returns per-phase data keyed by collection name
- Empty collection list returns empty results
- Sibling collection detection on CollectionService
- Multi-phase router HTTP contract (GET endpoints, query param parsing)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from services.multi_phase_service import MultiPhaseService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _team_row(
    team_name: str,
    games: int = 10,
    pts: float = 750.0,
    pts_pg: float = 75.0,
) -> Dict:
    """Minimal team-stats row as returned by the MongoDB pipeline."""
    return {
        "_id": team_name,
        "team_name": team_name,
        "games_played": games,
        "points_scored": pts,
        "points_per_game": pts_pg,
        "fg2_made": 200,
        "fg2_attempts": 400,
        "fg3_made": 50,
        "fg3_attempts": 150,
        "ft_made": 80,
        "ft_attempts": 100,
        "rebounds_off": 80,
        "rebounds_def": 220,
        "total_rebounds": 300,
        "assists": 150,
        "steals": 50,
        "turnovers": 100,
        "blocks": 30,
        "personal_fouls": 160,
    }


def _player_row(player_name: str, team_name: str, games: int = 8) -> Dict:
    return {
        "_id": player_name,
        "player_name": player_name,
        "team_name": team_name,
        "games_played": games,
        "points_per_game": 12.0,
        "total_points": 96,
        "assists_per_game": 3.0,
        "rebounds_per_game": 4.0,
    }


def _mock_db(
    team_stats_by_collection: Dict[str, List[Dict]],
    player_stats_by_collection: Dict[str, List[Dict]] | None = None,
) -> MagicMock:
    db = MagicMock()
    db.is_connected.return_value = True

    def _team_stats(coll, *args, **kwargs):
        return team_stats_by_collection.get(coll, [])

    def _player_stats(coll, *args, **kwargs):
        if player_stats_by_collection:
            return player_stats_by_collection.get(coll, [])
        return []

    db.get_team_stats.side_effect = _team_stats
    db.get_player_stats.side_effect = _player_stats
    db.get_opponent_stats.side_effect = lambda coll, *a, **kw: team_stats_by_collection.get(coll, [])
    return db


# ===========================================================================
# Combined team stats
# ===========================================================================

class TestCombinedTeamStats:
    def test_returns_list(self):
        db = _mock_db({"COL_A": [_team_row("TeamX")], "COL_B": [_team_row("TeamX")]})
        svc = MultiPhaseService(db, ["COL_A", "COL_B"])
        result = svc.get_combined_team_stats(is_fbcyl=False)
        assert isinstance(result, list)

    def test_teams_merged_by_name(self):
        db = _mock_db({
            "COL_A": [_team_row("TeamX", games=10), _team_row("TeamY", games=10)],
            "COL_B": [_team_row("TeamX", games=8),  _team_row("TeamY", games=8)],
        })
        svc = MultiPhaseService(db, ["COL_A", "COL_B"])
        result = svc.get_combined_team_stats(is_fbcyl=False)
        team_x = next(r for r in result if r["team_name"] == "TeamX")
        assert team_x["games_played"] == 18

    def test_points_summed_across_collections(self):
        db = _mock_db({
            "COL_A": [_team_row("TeamX", games=10, pts=750.0)],
            "COL_B": [_team_row("TeamX", games=8,  pts=600.0)],
        })
        svc = MultiPhaseService(db, ["COL_A", "COL_B"])
        result = svc.get_combined_team_stats(is_fbcyl=False)
        team_x = next(r for r in result if r["team_name"] == "TeamX")
        assert team_x["points_scored"] == pytest.approx(1350.0, abs=0.1)

    def test_per_game_recomputed_from_totals(self):
        db = _mock_db({
            "COL_A": [_team_row("TeamX", games=10, pts=700.0, pts_pg=70.0)],
            "COL_B": [_team_row("TeamX", games=10, pts=800.0, pts_pg=80.0)],
        })
        svc = MultiPhaseService(db, ["COL_A", "COL_B"])
        result = svc.get_combined_team_stats(is_fbcyl=False)
        team_x = next(r for r in result if r["team_name"] == "TeamX")
        # 1500 pts / 20 games = 75.0 ppg
        assert team_x["points_per_game"] == pytest.approx(75.0, abs=0.1)

    def test_team_only_in_one_collection_included(self):
        db = _mock_db({
            "COL_A": [_team_row("TeamX"), _team_row("TeamZ")],
            "COL_B": [_team_row("TeamX")],
        })
        svc = MultiPhaseService(db, ["COL_A", "COL_B"])
        result = svc.get_combined_team_stats(is_fbcyl=False)
        names = [r["team_name"] for r in result]
        assert "TeamZ" in names

    def test_empty_collections_returns_empty_list(self):
        svc = MultiPhaseService(_mock_db({}), [])
        result = svc.get_combined_team_stats(is_fbcyl=False)
        assert result == []

    def test_single_collection_returns_as_is(self):
        row = _team_row("TeamX")
        db = _mock_db({"COL_A": [row]})
        svc = MultiPhaseService(db, ["COL_A"])
        result = svc.get_combined_team_stats(is_fbcyl=False)
        assert len(result) == 1
        assert result[0]["games_played"] == row["games_played"]


# ===========================================================================
# Combined player stats
# ===========================================================================

class TestCombinedPlayerStats:
    def test_returns_list(self):
        db = _mock_db(
            {"COL_A": [], "COL_B": []},
            {"COL_A": [_player_row("P1", "T1")], "COL_B": [_player_row("P1", "T1")]},
        )
        svc = MultiPhaseService(db, ["COL_A", "COL_B"])
        result = svc.get_combined_player_stats(is_fbcyl=False)
        assert isinstance(result, list)

    def test_player_games_summed(self):
        db = _mock_db(
            {},
            {
                "COL_A": [_player_row("P1", "T1", games=8)],
                "COL_B": [_player_row("P1", "T1", games=6)],
            },
        )
        svc = MultiPhaseService(db, ["COL_A", "COL_B"])
        result = svc.get_combined_player_stats(is_fbcyl=False)
        p1 = next(r for r in result if r["player_name"] == "P1")
        assert p1["games_played"] == 14

    def test_player_points_per_game_recomputed(self):
        row_a = _player_row("P1", "T1", games=10)
        row_a["total_points"] = 100
        row_b = _player_row("P1", "T1", games=10)
        row_b["total_points"] = 120
        db = _mock_db({}, {"COL_A": [row_a], "COL_B": [row_b]})
        svc = MultiPhaseService(db, ["COL_A", "COL_B"])
        result = svc.get_combined_player_stats(is_fbcyl=False)
        p1 = next(r for r in result if r["player_name"] == "P1")
        # 220 pts / 20 games = 11.0 ppg
        assert p1["points_per_game"] == pytest.approx(11.0, abs=0.1)


# ===========================================================================
# Breakdown view
# ===========================================================================

class TestTeamStatsBreakdown:
    def test_breakdown_has_entry_per_collection(self):
        db = _mock_db({
            "COL_A": [_team_row("TeamX")],
            "COL_B": [_team_row("TeamX")],
        })
        svc = MultiPhaseService(db, ["COL_A", "COL_B"])
        result = svc.get_team_stats_breakdown(is_fbcyl=False)
        assert "COL_A" in result
        assert "COL_B" in result

    def test_breakdown_entry_is_list(self):
        db = _mock_db({"COL_A": [_team_row("TeamX")]})
        svc = MultiPhaseService(db, ["COL_A"])
        result = svc.get_team_stats_breakdown(is_fbcyl=False)
        assert isinstance(result["COL_A"], list)

    def test_breakdown_contains_original_rows(self):
        row = _team_row("TeamX", games=7)
        db = _mock_db({"COL_A": [row]})
        svc = MultiPhaseService(db, ["COL_A"])
        result = svc.get_team_stats_breakdown(is_fbcyl=False)
        assert result["COL_A"][0]["games_played"] == 7

    def test_empty_collections_returns_empty_dict(self):
        svc = MultiPhaseService(_mock_db({}), [])
        result = svc.get_team_stats_breakdown(is_fbcyl=False)
        assert result == {}


# ===========================================================================
# Sibling collections (CollectionService helper)
# ===========================================================================

class TestGetSiblingCollections:
    def test_returns_same_competition_and_season(self):
        from services.collection_service import CollectionService

        db = MagicMock()
        db.is_connected.return_value = True
        svc = CollectionService(db)

        siblings = svc.get_sibling_collections(
            "FEB_LF2_2025_A",
            ["FEB_LF2_2025_A", "FEB_LF2_2025_B", "FEB_LF2_2025_C"],
        )
        assert set(siblings) == {"FEB_LF2_2025_A", "FEB_LF2_2025_B", "FEB_LF2_2025_C"}

    def test_excludes_different_season(self):
        from services.collection_service import CollectionService

        db = MagicMock()
        db.is_connected.return_value = True
        svc = CollectionService(db)

        siblings = svc.get_sibling_collections(
            "FEB_LF2_2025_A",
            ["FEB_LF2_2025_A", "FEB_LF2_2026_A"],
        )
        assert "FEB_LF2_2026_A" not in siblings

    def test_excludes_different_competition(self):
        from services.collection_service import CollectionService

        db = MagicMock()
        db.is_connected.return_value = True
        svc = CollectionService(db)

        siblings = svc.get_sibling_collections(
            "FEB_LF2_2025_A",
            ["FEB_LF2_2025_A", "FEB_EBA_2025_A"],
        )
        assert "FEB_EBA_2025_A" not in siblings

    def test_always_includes_self(self):
        from services.collection_service import CollectionService

        db = MagicMock()
        db.is_connected.return_value = True
        svc = CollectionService(db)

        siblings = svc.get_sibling_collections(
            "FEB_LF2_2025_A",
            ["FEB_LF2_2025_A"],
        )
        assert "FEB_LF2_2025_A" in siblings


# ===========================================================================
# Sibling detection regression — multi-word / long phase names
# ===========================================================================

class TestSiblingCollectionsRegression:
    """Regression: _parse_components used a ≤2-char regex for group labels, so
    multi-word suffixes like ELIMINATORIAS or FASE_ASCENSO were absorbed into
    the season field and never matched as siblings of single-char groups (A/B).
    """

    def _svc(self):
        from services.collection_service import CollectionService
        db = MagicMock()
        db.is_connected.return_value = True
        return CollectionService(db)

    def test_includes_playoff_phase_as_sibling(self):
        """ELIMINATORIAS must be treated as a group label, not part of season."""
        siblings = self._svc().get_sibling_collections(
            "FEB_LF2_2025_A",
            ["FEB_LF2_2025_A", "FEB_LF2_2025_B", "FEB_LF2_2025_ELIMINATORIAS"],
        )
        assert "FEB_LF2_2025_ELIMINATORIAS" in siblings, (
            "ELIMINATORIAS should be a sibling of groups A/B in the same "
            "competition+season"
        )

    def test_includes_multiword_phase_as_sibling(self):
        """Multi-token suffix FASE_ASCENSO must be a sibling of single-letter groups."""
        siblings = self._svc().get_sibling_collections(
            "FEB_LF2_2025_A",
            ["FEB_LF2_2025_A", "FEB_LF2_2025_FASE_ASCENSO"],
        )
        assert "FEB_LF2_2025_FASE_ASCENSO" in siblings

    def test_different_year_not_sibling_regression(self):
        """Different year must not be treated as sibling even with long phase names."""
        siblings = self._svc().get_sibling_collections(
            "FEB_LF2_2025_ELIMINATORIAS",
            ["FEB_LF2_2025_ELIMINATORIAS", "FEB_LF2_2026_ELIMINATORIAS"],
        )
        assert "FEB_LF2_2026_ELIMINATORIAS" not in siblings


# ===========================================================================
# FEB pipeline field name regression
# ===========================================================================

def _feb_pipeline_team_row(team_name: str, games: int = 10) -> Dict:
    """Team row as produced by the FEB aggregation pipeline.

    The FEB pipeline uses different field names than the FBCYL pipeline:
      - total_games   (not games_played)
      - fg2_attempted (not fg2_attempts)
      - fg3_attempted (not fg3_attempts)
      - ft_attempted  (not ft_attempts)
    """
    return {
        "_id": team_name,
        "team_name": team_name,
        "total_games": games,          # FEB name
        "points_scored": 750.0,
        "points_per_game": 75.0,
        "fg2_made": 200,
        "fg2_attempted": 400,          # FEB name
        "fg3_made": 50,
        "fg3_attempted": 150,          # FEB name
        "ft_made": 80,
        "ft_attempted": 100,           # FEB name
        "rebounds_off": 80,
        "rebounds_def": 220,
        "total_rebounds": 300,
        "assists": 150,
        "steals": 50,
        "turnovers": 100,
        "blocks": 30,
        "personal_fouls": 160,
    }


class TestFebFieldNamesRegression:
    """Regression: MultiPhaseService._merge_by_key used games_played / fg2_attempts
    etc., but the FEB MongoDB pipeline emits total_games / fg2_attempted etc.
    All merged stats were zero for FEB collections.
    """

    def _svc(self, rows_a, rows_b):
        db = _mock_db({"COL_A": rows_a, "COL_B": rows_b})
        return MultiPhaseService(db, ["COL_A", "COL_B"])

    def test_games_non_zero_with_total_games_field(self):
        """games_played in merged row must not be zero when source uses total_games."""
        svc = self._svc(
            [_feb_pipeline_team_row("TeamX", games=10)],
            [_feb_pipeline_team_row("TeamX", games=8)],
        )
        result = svc.get_combined_team_stats(is_fbcyl=False)
        team = next(r for r in result if r["team_name"] == "TeamX")
        assert team["games_played"] == 18, (
            f"Expected 18 but got {team['games_played']}; "
            "FEB pipeline uses 'total_games' not 'games_played'"
        )

    def test_points_per_game_non_zero_with_feb_fields(self):
        """points_per_game must be recomputed correctly when source uses total_games."""
        svc = self._svc(
            [_feb_pipeline_team_row("TeamX", games=10)],
            [_feb_pipeline_team_row("TeamX", games=10)],
        )
        result = svc.get_combined_team_stats(is_fbcyl=False)
        team = next(r for r in result if r["team_name"] == "TeamX")
        assert team["points_per_game"] > 0, (
            "points_per_game is zero, likely because games denominator was not "
            "found (FEB field: total_games)"
        )

    def test_fg2_percentage_non_zero_with_attempted_field(self):
        """fg2_pct must be non-zero when source uses fg2_attempted (not fg2_attempts)."""
        svc = self._svc(
            [_feb_pipeline_team_row("TeamX")],
            [_feb_pipeline_team_row("TeamX")],
        )
        result = svc.get_combined_team_stats(is_fbcyl=False)
        team = next(r for r in result if r["team_name"] == "TeamX")
        assert team.get("fg2_percentage", 0) > 0, (
            "fg2_percentage is zero, likely because fg2_attempted was not recognised "
            "(FEB pipeline field vs fg2_attempts)"
        )


class TestAdvancedStatsRegression:
    """Regression: _recompute_derived did not compute advanced stats (OER, DER,
    four factors, rates) and did not alias games_played → total_games.
    MultiPhaseStatsPage showed zeros for all advanced columns.
    """

    def _team_row(self, games=10, pts=800, opp_pts=720, poss=950,
                  fg2m=200, fg2a=400, fg3m=80, fg3a=220, ftm=100, fta=130,
                  orb=80, drb=200, ast=150, stl=60, blk=30, tov=100):
        """Build a realistic FEB-style aggregated team row."""
        return {
            "team_name": "TestTeam",
            "games_played": games,
            "games_won": 7,
            "games_lost": 3,
            "points_scored": pts,
            "points_received": opp_pts,
            "total_possessions": poss,
            "fg2_made": fg2m, "fg2_attempts": fg2a,
            "fg3_made": fg3m, "fg3_attempts": fg3a,
            "ft_made": ftm, "ft_attempts": fta,
            "rebounds_off": orb, "rebounds_def": drb,
            "total_rebounds": orb + drb,
            "assists": ast, "steals": stl, "blocks": blk,
            "turnovers": tov, "personal_fouls": 180,
        }

    def _merged(self, **kwargs):
        from src.services.multi_phase_service import _merge_by_key
        return _merge_by_key({"X": [self._team_row(**kwargs)]}, key="team_name")[0]

    def test_total_games_alias_matches_games_played(self):
        """total_games must be set to same value as games_played after merge."""
        row = self._merged(games=12)
        assert row["total_games"] == 12

    def test_offensive_rating_computed(self):
        """offensive_rating = points_scored / total_possessions * 100."""
        row = self._merged(pts=800, poss=1000)
        assert row.get("offensive_rating") == 80.0

    def test_defensive_rating_computed(self):
        """defensive_rating = points_received / total_possessions * 100."""
        row = self._merged(opp_pts=720, poss=1000)
        assert row.get("defensive_rating") == 72.0

    def test_net_rating_computed(self):
        """net_rating = (pts - opp_pts) / poss * 100."""
        row = self._merged(pts=800, opp_pts=720, poss=1000)
        assert row.get("net_rating") == 8.0

    def test_efg_percentage_computed(self):
        """efg_percentage = (fg2m + 1.5*fg3m) / fga * 100."""
        # fg2m=200, fg2a=400, fg3m=80, fg3a=200 → fga=600, efg = (200+120)/600*100 = 53.33
        row = self._merged(fg2m=200, fg2a=400, fg3m=80, fg3a=200)
        expected = round((200 + 1.5 * 80) / 600 * 100, 2)
        assert row.get("efg_percentage") == expected

    def test_turnover_rate_computed(self):
        """turnover_rate = tov / (fga + 0.44*fta + tov) * 100."""
        row = self._merged(fg2a=400, fg3a=200, fta=100, tov=80)
        fga = 600
        tov_denom = fga + 0.44 * 100 + 80
        expected = round(80 / tov_denom * 100, 2)
        assert row.get("turnover_rate") == expected

    def test_free_throw_rate_computed(self):
        """free_throw_rate = ft_attempts / fga * 100."""
        row = self._merged(fg2a=400, fg3a=200, fta=120)
        expected = round(120 / 600 * 100, 2)
        assert row.get("free_throw_rate") == expected

    def test_true_shooting_computed(self):
        """true_shooting = pts / (2 * (fga + 0.44*fta)) * 100."""
        row = self._merged(pts=800, fg2a=400, fg3a=200, fta=100)
        ts_denom = 2 * (600 + 0.44 * 100)
        expected = round(800 / ts_denom * 100, 2)
        assert row.get("true_shooting") == expected

    def test_assist_rate_computed(self):
        """assist_rate = ast / poss * 100."""
        row = self._merged(ast=150, poss=1000)
        expected = round(150 / 1000 * 100, 2)
        assert row.get("assist_rate") == expected

    def test_orb_drb_per_game_computed(self):
        """offensive_rebounds_per_game and defensive_rebounds_per_game must be non-zero."""
        row = self._merged(games=10, orb=80, drb=200)
        assert row.get("offensive_rebounds_per_game") == 8.0
        assert row.get("defensive_rebounds_per_game") == 20.0

    def test_zero_possessions_no_rating_error(self):
        """No KeyError when total_possessions is 0; ratings should not be set."""
        row = self._merged(poss=0)
        # offensive_rating should not be present or be falsy without possessions
        assert not row.get("offensive_rating")

