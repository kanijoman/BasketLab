"""Characterization of TeamStatsService.get_possession_stats (every field of every entry).

Written before extracting the entry builders out of ``src/services/team_stats_service.py`` (#360); regenerated
on purpose in #350 because the possessions now come from the tracker. The
possession stats come from the real PossessionAnalyzer over the FEB and FBCYL sample games; one extra team
has no id and another has no play-by-play, to freeze the ``None`` paths too. Regenerate the goldens with
``python -c "from tests.test_team_possession_stats_characterization import print_goldens; print_goldens()"``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from src.services import team_stats_service  # noqa: E402
from src.services.team_stats_service import TeamStatsService  # noqa: E402
from tests.test_possession_repository_characterization import _FakeRepo, _cases  # noqa: E402

GOLDENS = {'fbcyl': [{'avg_duration': 19.78,
            'boxscore_oer': 0,
            'data_quality_score': 100,
            'der': 98.5,
            'est_possessions_per_game': 60.7,
            'net_rating': 1.5,
            'oer': 100.0,
            'oer_fast': 66.67,
            'oer_medium': 93.75,
            'oer_slow': 51.43,
            'pace': 70.0,
            'pct_fast': 5.6,
            'pct_medium': 29.6,
            'pct_slow': 64.8,
            'phantom_pct': 0,
            'possessions_per_game': 70.0,
            'reconciliation': 'use_playbyplay',
            'rival_avg_duration': 17.63,
            'rival_avg_duration_general': 17.63,
            'rival_oer_fast': 140.0,
            'rival_oer_medium': 126.32,
            'rival_oer_slow': 182.14,
            'rival_pace_differential': 0.0,
            'rival_pct_fast': 17.5,
            'rival_pct_medium': 33.3,
            'rival_pct_slow': 49.1,
            'team_id': '33865',
            'team_name': 'Team 0',
            'total_games': 1},
           {'avg_duration': 17.63,
            'boxscore_oer': 0,
            'data_quality_score': 100,
            'der': 97.5,
            'est_possessions_per_game': 68.1,
            'net_rating': 3.5,
            'oer': 101.0,
            'oer_fast': 140.0,
            'oer_medium': 126.32,
            'oer_slow': 182.14,
            'pace': 71.0,
            'pct_fast': 17.5,
            'pct_medium': 33.3,
            'pct_slow': 49.1,
            'phantom_pct': 0,
            'possessions_per_game': 71.0,
            'reconciliation': 'use_playbyplay',
            'rival_avg_duration': 19.78,
            'rival_avg_duration_general': 19.78,
            'rival_oer_fast': 66.67,
            'rival_oer_medium': 93.75,
            'rival_oer_slow': 51.43,
            'rival_pace_differential': 0.0,
            'rival_pct_fast': 5.6,
            'rival_pct_medium': 29.6,
            'rival_pct_slow': 64.8,
            'team_id': '33866',
            'team_name': 'Team 1',
            'total_games': 2},
           {'avg_duration': None,
            'der': 96.5,
            'est_possessions_per_game': None,
            'net_rating': 5.5,
            'oer': 102.0,
            'oer_fast': None,
            'oer_medium': None,
            'oer_slow': None,
            'pace': 72.0,
            'pct_fast': None,
            'pct_medium': None,
            'pct_slow': None,
            'possessions_per_game': 72.0,
            'rival_avg_duration_general': None,
            'rival_pace_differential': None,
            'team_id': None,
            'team_name': 'Team without id',
            'total_games': 3},
           {'avg_duration': None,
            'der': 95.5,
            'est_possessions_per_game': None,
            'net_rating': 7.5,
            'oer': 103.0,
            'oer_fast': None,
            'oer_medium': None,
            'oer_slow': None,
            'pace': 73.0,
            'pct_fast': None,
            'pct_medium': None,
            'pct_slow': None,
            'possessions_per_game': 73.0,
            'rival_avg_duration_general': None,
            'rival_pace_differential': None,
            'team_id': 'no-pbp',
            'team_name': 'Team without pbp',
            'total_games': 4}],
 'feb': [{'avg_duration': 17.39,
          'boxscore_oer': 112.05,
          'data_quality_score': 98,
          'der': 98.5,
          'est_possessions_per_game': 69.0,
          'net_rating': 1.5,
          'oer': 100.0,
          'oer_fast': 66.67,
          'oer_medium': 112.5,
          'oer_slow': 116.22,
          'pace': 70.0,
          'pct_fast': 9.0,
          'pct_medium': 35.8,
          'pct_slow': 55.2,
          'phantom_pct': 0,
          'possessions_per_game': 70.0,
          'reconciliation': 'use_playbyplay',
          'rival_avg_duration': 15.9,
          'rival_avg_duration_general': 15.9,
          'rival_oer_fast': 145.45,
          'rival_oer_medium': 76.0,
          'rival_oer_slow': 63.64,
          'rival_pace_differential': 0.0,
          'rival_pct_fast': 15.9,
          'rival_pct_medium': 36.2,
          'rival_pct_slow': 47.8,
          'team_id': '982047',
          'team_name': 'Team 0',
          'total_games': 1},
         {'avg_duration': 15.9,
          'boxscore_oer': 75.19,
          'data_quality_score': 85,
          'der': 97.5,
          'est_possessions_per_game': 75.5,
          'net_rating': 3.5,
          'oer': 101.0,
          'oer_fast': 145.45,
          'oer_medium': 76.0,
          'oer_slow': 63.64,
          'pace': 71.0,
          'pct_fast': 15.9,
          'pct_medium': 36.2,
          'pct_slow': 47.8,
          'phantom_pct': 0,
          'possessions_per_game': 71.0,
          'reconciliation': 'use_hybrid',
          'rival_avg_duration': 17.39,
          'rival_avg_duration_general': 17.39,
          'rival_oer_fast': 66.67,
          'rival_oer_medium': 112.5,
          'rival_oer_slow': 116.22,
          'rival_pace_differential': 0.0,
          'rival_pct_fast': 9.0,
          'rival_pct_medium': 35.8,
          'rival_pct_slow': 55.2,
          'team_id': '981204',
          'team_name': 'Team 1',
          'total_games': 2},
         {'avg_duration': None,
          'der': 96.5,
          'est_possessions_per_game': None,
          'net_rating': 5.5,
          'oer': 102.0,
          'oer_fast': None,
          'oer_medium': None,
          'oer_slow': None,
          'pace': 72.0,
          'pct_fast': None,
          'pct_medium': None,
          'pct_slow': None,
          'possessions_per_game': 72.0,
          'rival_avg_duration_general': None,
          'rival_pace_differential': None,
          'team_id': None,
          'team_name': 'Team without id',
          'total_games': 3},
         {'avg_duration': None,
          'der': 95.5,
          'est_possessions_per_game': None,
          'net_rating': 7.5,
          'oer': 103.0,
          'oer_fast': None,
          'oer_medium': None,
          'oer_slow': None,
          'pace': 73.0,
          'pct_fast': None,
          'pct_medium': None,
          'pct_slow': None,
          'possessions_per_game': 73.0,
          'rival_avg_duration_general': None,
          'rival_pace_differential': None,
          'team_id': 'no-pbp',
          'team_name': 'Team without pbp',
          'total_games': 4}]}


def _season_rows(names):
    """One boxscore-style season row per team name, with deterministic numbers."""
    rows = []
    for i, name in enumerate(names):
        rows.append({
            "team_name": name, "possessions_per_game": 70.0 + i, "offensive_rating": 100.0 + i,
            "defensive_rating": 98.5 - i, "net_rating": 1.5 + 2 * i, "total_games": 1 + i,
        })
    return rows


def _run(name):
    collection, doc, team_ids = _cases()[name]
    names = [f"Team {i}" for i in range(len(team_ids))] + ["Team without id", "Team without pbp"]
    ids = team_ids + [None, "no-pbp"]

    class _Repo(_FakeRepo):
        def get_team_possession_stats(self, coll, tid, date_filter=None):
            if tid == "no-pbp":
                return {}
            return super().get_team_possession_stats(coll, tid, date_filter)

    db = MagicMock()
    db.get_team_stats.return_value = _season_rows(names)
    db.repository = _Repo([doc])
    teams = [{"name": n, "id": i} for n, i in zip(names, ids) if i]
    team_stats_service._possession_cache.clear()
    with patch("src.services.team_stats_service.get_available_teams_from_collection", return_value=teams):
        return TeamStatsService(db).get_possession_stats(collection + "_" + name)


def print_goldens():  # pragma: no cover - maintenance helper
    print(json.dumps({n: _run(n) for n in ("feb", "fbcyl")}, indent=4, sort_keys=True))


@pytest.mark.parametrize("name", ["feb", "fbcyl"])
def test_possession_stats_entries_do_not_change(name):
    assert json.loads(json.dumps(_run(name), sort_keys=True)) == GOLDENS[name]


def test_result_is_cached_per_collection():
    first = _run("feb")
    db = MagicMock()
    db.get_team_stats.side_effect = AssertionError("must be served from the cache")
    assert TeamStatsService(db).get_possession_stats("FEB_LF2_2025_A_feb") is first
