"""Characterization of PossessionRepositoryMixin.get_team_possession_stats on both sample games.

Written before extracting the pure helpers out of ``src/database/repository_possession.py`` (#360): the
whole result (PBP stats, rival breakdown, boxscore fallback and reconciliation) must stay identical.
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

GOLDENS = {
    "fbcyl": {
        "33865": {
            "avg_duration": 13.2,
            "boxscore_oer": 0,
            "boxscore_possessions": 0.0,
            "data_quality_score": 100,
            "games_analyzed": 1,
            "mismatch_pct": 0,
            "possessions_by_duration": {
                "8-16s": {
                    "count": 22,
                    "oer": 54.55,
                    "total_points": 12
                },
                "<=8s": {
                    "count": 11,
                    "oer": 118.18,
                    "total_points": 13
                },
                ">16s": {
                    "count": 17,
                    "oer": 58.82,
                    "total_points": 10
                }
            },
            "recommendation": "use_playbyplay",
            "rival_avg_duration": 17.81,
            "rival_oer_fast": 161.54,
            "rival_oer_medium": 135.71,
            "rival_oer_slow": 162.5,
            "rival_opponent_breakdown": {
                "33866": {
                    "possessions": 59,
                    "weighted_duration": 1050.79
                }
            },
            "rival_pct_fast": 22.0,
            "rival_pct_medium": 23.7,
            "rival_pct_slow": 54.2,
            "total_games": 0,
            "total_possessions": 50
        },
        "33866": {
            "avg_duration": 17.81,
            "boxscore_oer": 0,
            "boxscore_possessions": 0.0,
            "data_quality_score": 100,
            "games_analyzed": 1,
            "mismatch_pct": 0,
            "possessions_by_duration": {
                "8-16s": {
                    "count": 14,
                    "oer": 135.71,
                    "total_points": 19
                },
                "<=8s": {
                    "count": 13,
                    "oer": 161.54,
                    "total_points": 21
                },
                ">16s": {
                    "count": 32,
                    "oer": 162.5,
                    "total_points": 52
                }
            },
            "recommendation": "use_playbyplay",
            "rival_avg_duration": 13.2,
            "rival_oer_fast": 118.18,
            "rival_oer_medium": 54.55,
            "rival_oer_slow": 58.82,
            "rival_opponent_breakdown": {
                "33865": {
                    "possessions": 50,
                    "weighted_duration": 660.0
                }
            },
            "rival_pct_fast": 22.0,
            "rival_pct_medium": 44.0,
            "rival_pct_slow": 34.0,
            "total_games": 0,
            "total_possessions": 59
        }
    },
    "feb": {
        "981204": {
            "avg_duration": 14.51,
            "boxscore_oer": 75.19,
            "boxscore_possessions": 74.5,
            "data_quality_score": 96,
            "games_analyzed": 1,
            "mismatch_pct": 2.0,
            "possessions_by_duration": {
                "8-16s": {
                    "count": 26,
                    "oer": 76.92,
                    "total_points": 20
                },
                "<=8s": {
                    "count": 15,
                    "oer": 133.33,
                    "total_points": 20
                },
                ">16s": {
                    "count": 32,
                    "oer": 50.0,
                    "total_points": 16
                }
            },
            "recommendation": "use_playbyplay",
            "rival_avg_duration": 17.13,
            "rival_oer_fast": 57.14,
            "rival_oer_medium": 112.5,
            "rival_oer_slow": 116.22,
            "rival_opponent_breakdown": {
                "982047": {
                    "possessions": 68,
                    "weighted_duration": 1164.84
                }
            },
            "rival_pct_fast": 10.3,
            "rival_pct_medium": 35.3,
            "rival_pct_slow": 54.4,
            "total_games": 1,
            "total_possessions": 73
        },
        "982047": {
            "avg_duration": 17.13,
            "boxscore_oer": 112.05,
            "boxscore_possessions": 66.0,
            "data_quality_score": 95,
            "games_analyzed": 1,
            "mismatch_pct": 2.9,
            "possessions_by_duration": {
                "8-16s": {
                    "count": 24,
                    "oer": 112.5,
                    "total_points": 27
                },
                "<=8s": {
                    "count": 7,
                    "oer": 57.14,
                    "total_points": 4
                },
                ">16s": {
                    "count": 37,
                    "oer": 116.22,
                    "total_points": 43
                }
            },
            "recommendation": "use_playbyplay",
            "rival_avg_duration": 14.51,
            "rival_oer_fast": 133.33,
            "rival_oer_medium": 76.92,
            "rival_oer_slow": 50.0,
            "rival_opponent_breakdown": {
                "981204": {
                    "possessions": 73,
                    "weighted_duration": 1059.23
                }
            },
            "rival_pct_fast": 20.5,
            "rival_pct_medium": 35.6,
            "rival_pct_slow": 43.8,
            "total_games": 1,
            "total_possessions": 68
        }
    }
}


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
