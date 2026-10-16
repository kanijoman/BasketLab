"""Characterization of PossessionRepositoryMixin.get_team_possession_stats on both sample games.

Written before extracting the pure helpers out of ``src/database/repository_possession.py`` (#360): the
whole result (PBP stats, rival breakdown, boxscore fallback and reconciliation) must stay identical. Regenerated
on purpose in #350: the possessions now come from the tracker (fewer phantom possessions, FBCYL clock fixed).
Regenerate the goldens, if a behaviour change is deliberate, with
``python -c "from tests.test_possession_repository_characterization import print_goldens; print_goldens()"``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from src.database import repository_possession  # noqa: E402
from src.database.repository_possession import PossessionRepositoryMixin  # noqa: E402

GOLDENS = {'fbcyl': {'33865': {'avg_duration': 19.78,
                     'boxscore_oer': 0,
                     'boxscore_possessions': 0.0,
                     'data_quality_score': 100,
                     'games_analyzed': 1,
                     'mismatch_pct': 0,
                     'possessions_by_duration': {'8-16s': {'count': 16, 'oer': 93.75, 'total_points': 15},
                                                 '<=8s': {'count': 3, 'oer': 66.67, 'total_points': 2},
                                                 '>16s': {'count': 35, 'oer': 51.43, 'total_points': 18}},
                     'recommendation': 'use_playbyplay',
                     'rival_avg_duration': 17.63,
                     'rival_oer_fast': 140.0,
                     'rival_oer_medium': 126.32,
                     'rival_oer_slow': 182.14,
                     'rival_opponent_breakdown': {'33866': {'possessions': 57, 'weighted_duration': 1004.91}},
                     'rival_pct_fast': 17.5,
                     'rival_pct_medium': 33.3,
                     'rival_pct_slow': 49.1,
                     'total_games': 0,
                     'total_possessions': 54},
           '33866': {'avg_duration': 17.63,
                     'boxscore_oer': 0,
                     'boxscore_possessions': 0.0,
                     'data_quality_score': 100,
                     'games_analyzed': 1,
                     'mismatch_pct': 0,
                     'possessions_by_duration': {'8-16s': {'count': 19, 'oer': 126.32, 'total_points': 24},
                                                 '<=8s': {'count': 10, 'oer': 140.0, 'total_points': 14},
                                                 '>16s': {'count': 28, 'oer': 182.14, 'total_points': 51}},
                     'recommendation': 'use_playbyplay',
                     'rival_avg_duration': 19.78,
                     'rival_oer_fast': 66.67,
                     'rival_oer_medium': 93.75,
                     'rival_oer_slow': 51.43,
                     'rival_opponent_breakdown': {'33865': {'possessions': 54,
                                                            'weighted_duration': 1068.1200000000001}},
                     'rival_pct_fast': 5.6,
                     'rival_pct_medium': 29.6,
                     'rival_pct_slow': 64.8,
                     'total_games': 0,
                     'total_possessions': 57}},
 'feb': {'981204': {'avg_duration': 15.9,
                    'boxscore_oer': 75.19,
                    'boxscore_possessions': 74.5,
                    'data_quality_score': 85,
                    'games_analyzed': 1,
                    'mismatch_pct': 7.9,
                    'possessions_by_duration': {'8-16s': {'count': 25, 'oer': 76.0, 'total_points': 19},
                                                '<=8s': {'count': 11, 'oer': 145.45, 'total_points': 16},
                                                '>16s': {'count': 33, 'oer': 63.64, 'total_points': 21}},
                    'recommendation': 'use_hybrid',
                    'rival_avg_duration': 17.39,
                    'rival_oer_fast': 66.67,
                    'rival_oer_medium': 112.5,
                    'rival_oer_slow': 116.22,
                    'rival_opponent_breakdown': {'982047': {'possessions': 67, 'weighted_duration': 1165.13}},
                    'rival_pct_fast': 9.0,
                    'rival_pct_medium': 35.8,
                    'rival_pct_slow': 55.2,
                    'total_games': 1,
                    'total_possessions': 69},
         '982047': {'avg_duration': 17.39,
                    'boxscore_oer': 112.05,
                    'boxscore_possessions': 66.0,
                    'data_quality_score': 98,
                    'games_analyzed': 1,
                    'mismatch_pct': 1.4,
                    'possessions_by_duration': {'8-16s': {'count': 24, 'oer': 112.5, 'total_points': 27},
                                                '<=8s': {'count': 6, 'oer': 66.67, 'total_points': 4},
                                                '>16s': {'count': 37, 'oer': 116.22, 'total_points': 43}},
                    'recommendation': 'use_playbyplay',
                    'rival_avg_duration': 15.9,
                    'rival_oer_fast': 145.45,
                    'rival_oer_medium': 76.0,
                    'rival_oer_slow': 63.64,
                    'rival_opponent_breakdown': {'981204': {'possessions': 69,
                                                            'weighted_duration': 1097.1000000000001}},
                    'rival_pct_fast': 15.9,
                    'rival_pct_medium': 36.2,
                    'rival_pct_slow': 47.8,
                    'total_games': 1,
                    'total_possessions': 67}}}


class _FakeRepo(PossessionRepositoryMixin):
    def __init__(self, games):
        self.connection = MagicMock()
        self.connection.is_connected.return_value = True
        self._games = games

    def get_games_for_team(self, collection_name, team_id, only_with_playbyplay=False, projection=None):
        return self._games


def _cases():
    samples = Path(__file__).parent.parent / "src" / "JSON_samples"
    from src.live_core.vectors import unwrap_extended_json

    with open(samples / "feb_game.json", encoding="utf-8") as f:
        feb = unwrap_extended_json(json.load(f))
    with open(samples / "fbcyl_game.json", encoding="utf-8") as f:
        fbcyl = json.load(f)
    return {
        "feb": ("FEB_LF2_2025_A", feb, [str(t["id"]) for t in feb["HEADER"]["TEAM"]]),
        "fbcyl": ("FBCYL_SE_2025_A", fbcyl, [str(t["teamIdIntern"]) for t in fbcyl["stats"]["teams"]]),
    }


def _results(name):
    collection, doc, team_ids = _cases()[name]
    repo = _FakeRepo([doc])
    return {tid: repo.get_team_possession_stats(collection, tid) for tid in team_ids}


def print_goldens():  # pragma: no cover - maintenance helper
    print(json.dumps({n: _results(n) for n in ("feb", "fbcyl")}, indent=4, sort_keys=True))


@pytest.mark.parametrize("name", ["feb", "fbcyl"])
def test_possession_stats_do_not_change(name):
    assert json.loads(json.dumps(_results(name), sort_keys=True)) == GOLDENS[name]


def test_module_keeps_the_private_helpers_other_tests_import():
    for helper in ("_possession_projection", "_aggregate_game_possession", "_empty_possession_result"):
        assert hasattr(repository_possession, helper), helper
