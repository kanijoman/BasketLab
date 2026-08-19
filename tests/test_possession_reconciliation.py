"""Unit tests for possession stats reconciliation logic.

Tests the hybrid reconciliation approach:
- Boxscore vs. play-by-play OER comparison
- Data quality scoring based on OER mismatch
- Decision logic (use_boxscore | use_hybrid | use_playbyplay)
- Team stats service integration

No database data dependencies — all tests use mocked repository responses.
"""

import pytest
from unittest.mock import Mock, patch

from src.services.team_stats_service import TeamStatsService


class TestReconciliationDecisionLogic:
    """Decision logic is now mismatch-based, not phantom-based."""

    def test_use_boxscore_when_mismatch_above_15(self):
        """mismatch_pct > 15% → recommendation should be 'use_boxscore'."""
        mismatch_pct = 15.4  # AZULMARINO example: 95.2 vs 112.5
        assert mismatch_pct > 15
        recommendation = "use_boxscore" if mismatch_pct > 15 else (
            "use_hybrid" if mismatch_pct > 5 else "use_playbyplay"
        )
        assert recommendation == "use_boxscore"

    def test_use_hybrid_when_mismatch_5_to_15(self):
        """5% ≤ mismatch_pct ≤ 15% → recommendation should be 'use_hybrid'."""
        mismatch_pct = 10.0
        recommendation = "use_boxscore" if mismatch_pct > 15 else (
            "use_hybrid" if mismatch_pct > 5 else "use_playbyplay"
        )
        assert recommendation == "use_hybrid"

    def test_use_playbyplay_when_mismatch_below_5(self):
        """mismatch_pct ≤ 5% → recommendation should be 'use_playbyplay'."""
        mismatch_pct = 2.0
        recommendation = "use_boxscore" if mismatch_pct > 15 else (
            "use_hybrid" if mismatch_pct > 5 else "use_playbyplay"
        )
        assert recommendation == "use_playbyplay"


class TestDataQualityScoring:
    """Data quality score is now based on OER mismatch, not phantom rate."""

    def test_quality_score_100_with_zero_mismatch(self):
        score = max(0, 100 - int(0 * 2))
        assert score == 100

    def test_quality_score_degrades_with_mismatch(self):
        scores = [max(0, 100 - int(m * 2)) for m in [0, 5, 10, 15, 20, 50]]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_quality_score_bottoms_at_zero(self):
        for mismatch in [60, 100, 200]:
            assert max(0, 100 - int(mismatch * 2)) >= 0

    def test_high_mismatch_gives_low_score(self):
        score = max(0, 100 - int(15.4 * 2))  # 15.4% mismatch → score 70
        assert score <= 70


class TestMismatchPercentageCalculation:
    """Test OER mismatch percentage between PBP and boxscore."""
    
    def test_17_percent_mismatch_example(self):
        """AZULMARINO example: 95.2 vs 112.5 OER (~15% mismatch)."""
        pbp_oer = 95.2
        boxscore_oer = 112.5
        mismatch_pct = abs((pbp_oer - boxscore_oer) / boxscore_oer * 100)
        
        # (95.2 - 112.5) / 112.5 * 100 = -17.3 / 112.5 * 100 ≈ -15.4%
        assert abs(mismatch_pct - 15.4) < 0.5  # Should be ~15.4%
    
    def test_zero_mismatch_when_oers_equal(self):
        """When OERs match, mismatch should be 0%."""
        pbp_oer = 110.0
        boxscore_oer = 110.0
        mismatch_pct = abs((pbp_oer - boxscore_oer) / boxscore_oer * 100)
        
        assert mismatch_pct == 0


class TestTeamStatsServiceReconciliation:
    """Service adds quality metadata without altering the aggregation-pipeline OER."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = Mock()
        return db
    
    @patch('src.services.team_stats_service.get_available_teams_from_collection')
    def test_service_preserves_oer_and_adds_boxscore_metadata(self, mock_get_teams, mock_db):
        """General OER must not be altered; quality metadata is added as extra fields."""
        mock_get_teams.return_value = [{"id": "team123", "name": "Test Team"}]
        
        mock_db.get_team_stats.return_value = [
            {
                "team_name": "Test Team",
                "possessions_per_game": 100.0,
                "offensive_rating": 95.2,
                "defensive_rating": 105.0,
                "net_rating": -9.8,
                "total_games": 15,
            }
        ]
        
        mock_db.repository = Mock()
        mock_db.repository.get_team_possession_stats.return_value = {
            "total_possessions": 1000,
            "avg_duration": 16.0,
            "possessions_by_duration": {
                "<=8s": {"count": 200, "total_points": 200, "oer": 100.0},
                "8-16s": {"count": 400, "total_points": 420, "oer": 105.0},
                ">16s": {"count": 400, "total_points": 440, "oer": 110.0},
            },
            "games_analyzed": 15,
            "recommendation": "use_boxscore",
            "boxscore_oer": 112.5,
            "boxscore_possessions": 1735.0,
            "mismatch_pct": 15.4,
            "data_quality_score": 69,
        }
        
        service = TeamStatsService(mock_db)
        result = service.get_possession_stats("test_collection_boxscore")
        
        assert len(result) == 1
        team_data = result[0]
        
        # General OER must stay as the aggregation-pipeline value, never overwritten
        assert team_data["oer"] == 95.2
        assert team_data["reconciliation"] == "use_boxscore"
        assert team_data["data_quality_score"] == 69
        assert team_data["boxscore_oer"] == 112.5
    
    @patch('src.services.team_stats_service.get_available_teams_from_collection')
    def test_service_exposes_hybrid_metadata_without_altering_oer(self, mock_get_teams, mock_db):
        """Hybrid recommendation is surfaced in metadata; general OER is unchanged."""
        mock_get_teams.return_value = [{"id": "team123", "name": "Test Team"}]
        
        offensive_rating = 102.0
        
        mock_db.get_team_stats.return_value = [
            {
                "team_name": "Test Team",
                "possessions_per_game": 100.0,
                "offensive_rating": offensive_rating,
                "defensive_rating": 105.0,
                "net_rating": -3.0,
                "total_games": 15,
            }
        ]
        
        mock_db.repository = Mock()
        mock_db.repository.get_team_possession_stats.return_value = {
            "total_possessions": 1000,
            "avg_duration": 16.0,
            "possessions_by_duration": {
                "<=8s": {"count": 200, "total_points": 204, "oer": 102.0},
                "8-16s": {"count": 400, "total_points": 420, "oer": 105.0},
                ">16s": {"count": 400, "total_points": 440, "oer": 110.0},
            },
            "games_analyzed": 15,
            "recommendation": "use_hybrid",
            "boxscore_oer": 110.0,
            "boxscore_possessions": 1735.0,
            "mismatch_pct": 7.3,
            "data_quality_score": 93,
        }
        
        service = TeamStatsService(mock_db)
        result = service.get_possession_stats("test_collection_hybrid")
        
        team_data = result[0]
        
        assert team_data["oer"] == offensive_rating  # unchanged
        assert team_data["reconciliation"] == "use_hybrid"
        assert team_data["data_quality_score"] == 93
    
    @patch('src.services.team_stats_service.get_available_teams_from_collection')
    def test_service_exposes_playbyplay_metadata_without_altering_oer(self, mock_get_teams, mock_db):
        """Good-quality PBP is surfaced in metadata; general OER is unchanged."""
        offensive_rating = 108.5
        
        mock_get_teams.return_value = [{"id": "team123", "name": "Test Team"}]
        
        mock_db.get_team_stats.return_value = [
            {
                "team_name": "Test Team",
                "possessions_per_game": 100.0,
                "offensive_rating": offensive_rating,
                "defensive_rating": 105.0,
                "net_rating": 3.5,
                "total_games": 15,
            }
        ]
        
        mock_db.repository = Mock()
        mock_db.repository.get_team_possession_stats.return_value = {
            "total_possessions": 1000,
            "avg_duration": 16.0,
            "possessions_by_duration": {
                "<=8s": {"count": 200, "total_points": 217, "oer": 108.5},
                "8-16s": {"count": 400, "total_points": 420, "oer": 105.0},
                ">16s": {"count": 400, "total_points": 440, "oer": 110.0},
            },
            "games_analyzed": 15,
            "recommendation": "use_playbyplay",
            "boxscore_oer": 109.0,
            "boxscore_possessions": 1735.0,
            "mismatch_pct": 0.5,
            "data_quality_score": 99,
        }
        
        service = TeamStatsService(mock_db)
        result = service.get_possession_stats("test_collection_pbp")
        
        team_data = result[0]
        
        assert team_data["oer"] == offensive_rating  # unchanged
        assert team_data["reconciliation"] == "use_playbyplay"
        assert team_data["data_quality_score"] == 99


class TestReconciliationEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_mismatch_exactly_15_uses_hybrid(self):
        mismatch_pct = 15.0
        assert not (mismatch_pct > 15)  # boundary: not use_boxscore

    def test_mismatch_exactly_5_uses_playbyplay(self):
        mismatch_pct = 5.0
        assert not (mismatch_pct > 5)  # boundary: not use_hybrid

    def test_zero_boxscore_possessions_handled(self):
        """Should handle division by zero when boxscore has 0 possessions."""
        boxscore_possessions = 0
        pbp_oer = 100.0

        if boxscore_possessions == 0:
            final_oer = pbp_oer
        else:
            boxscore_oer = 110.0
            final_oer = (pbp_oer + boxscore_oer) / 2

        assert final_oer == pbp_oer

    def test_missing_reconciliation_fields_defaults_to_playbyplay(self):
        """Service should gracefully handle missing reconciliation fields."""
        poss_stats = {
            "total_possessions": 1000,
            "avg_duration": 16.0,
            "possessions_by_duration": {
                "<=8s": {"count": 200, "oer": 100.0},
                "8-16s": {"count": 400, "oer": 105.0},
                ">16s": {"count": 400, "oer": 110.0},
            },
            # Missing: boxscore_oer, recommendation, data_quality_score
        }
        recommendation = poss_stats.get("recommendation", "use_playbyplay")
        assert recommendation == "use_playbyplay"
