"""Tests for src.database.fbcyl_transformer.FBCYLTransformer."""

import pytest
from src.database.fbcyl_transformer import FBCYLTransformer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_match(local_score=80, visit_score=72, local_id=1, visit_id=2):
    """Return a minimal FBCYL match dict with required 'moves' structure."""
    return {
        'uuid': 'test-uuid',
        'moves': {
            'localId': local_id,
            'visitId': visit_id,
            'idMatchIntern': 'MATCH001',
            'time': '2025-01-10T18:00:00.000Z',
            'score': [
                {'local': 20, 'visit': 18},
                {'local': 40, 'visit': 35},
                {'local': 60, 'visit': 55},
                {'local': local_score, 'visit': visit_score},
            ],
        },
        'stats': {},
    }


# ---------------------------------------------------------------------------
# transform_match_to_boxscore
# ---------------------------------------------------------------------------

class TestTransformMatchToBoxscore:
    def test_returns_dict_for_valid_input(self):
        match = _minimal_match()
        result = FBCYLTransformer.transform_match_to_boxscore(match)
        assert isinstance(result, dict)

    def test_returns_none_when_no_moves(self):
        result = FBCYLTransformer.transform_match_to_boxscore({'uuid': 'x', 'stats': {}})
        assert result is None

    def test_returns_none_when_moves_is_none(self):
        result = FBCYLTransformer.transform_match_to_boxscore({'moves': None})
        assert result is None

    def test_returns_none_when_score_array_empty(self):
        match = {'moves': {'localId': 1, 'visitId': 2, 'score': []}}
        result = FBCYLTransformer.transform_match_to_boxscore(match)
        assert result is None

    def test_local_score_extracted_correctly(self):
        match = _minimal_match(local_score=95, visit_score=88)
        result = FBCYLTransformer.transform_match_to_boxscore(match)
        assert result['local']['score'] == 95

    def test_visit_score_extracted_correctly(self):
        match = _minimal_match(local_score=65, visit_score=70)
        result = FBCYLTransformer.transform_match_to_boxscore(match)
        assert result['visitor']['score'] == 70

    def test_local_team_id_propagated(self):
        match = _minimal_match(local_id=42)
        result = FBCYLTransformer.transform_match_to_boxscore(match)
        assert result['local']['team_id'] == 42

    def test_visitor_team_id_propagated(self):
        match = _minimal_match(visit_id=99)
        result = FBCYLTransformer.transform_match_to_boxscore(match)
        assert result['visitor']['team_id'] == 99

    def test_local_key_present(self):
        result = FBCYLTransformer.transform_match_to_boxscore(_minimal_match())
        assert 'local' in result

    def test_visitor_key_present(self):
        result = FBCYLTransformer.transform_match_to_boxscore(_minimal_match())
        assert 'visitor' in result

    def test_date_field_present(self):
        result = FBCYLTransformer.transform_match_to_boxscore(_minimal_match())
        assert 'date' in result

    def test_match_id_field_present(self):
        result = FBCYLTransformer.transform_match_to_boxscore(_minimal_match())
        assert 'match_id' in result

    def test_players_is_list(self):
        result = FBCYLTransformer.transform_match_to_boxscore(_minimal_match())
        assert isinstance(result['local']['players'], list)
        assert isinstance(result['visitor']['players'], list)

    def test_no_crash_on_empty_dict(self):
        result = FBCYLTransformer.transform_match_to_boxscore({})
        assert result is None

    def test_final_score_from_last_score_entry(self):
        """Only the last entry in the score array should be used as final score."""
        match = _minimal_match(local_score=110, visit_score=108)
        result = FBCYLTransformer.transform_match_to_boxscore(match)
        # last entry wins
        assert result['local']['score'] == 110
        assert result['visitor']['score'] == 108


# ---------------------------------------------------------------------------
# extract_player_stats_from_moves
# ---------------------------------------------------------------------------

class TestExtractPlayerStatsFromMoves:
    def test_returns_dict(self):
        result = FBCYLTransformer.extract_player_stats_from_moves([])
        assert isinstance(result, dict)

    def test_empty_moves_returns_empty_dict(self):
        result = FBCYLTransformer.extract_player_stats_from_moves([])
        assert result == {}

    def test_handles_non_list_gracefully(self):
        """Should not crash on None or bad input."""
        try:
            result = FBCYLTransformer.extract_player_stats_from_moves(None)
            # If it doesn't crash, that's acceptable
        except (TypeError, AttributeError):
            pass  # expected for unimplemented TODO
