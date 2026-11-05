"""The vectors of the matchup of the scouting on the device (#751): what the real ``compare_teams`` answers over season rows of the sample league, the reference of
``frontend/src/lib/scoutingCompare.test.ts``.

Only the rows are inputs (they are the ones the vectors of the team tables already prove equal to the API's); the comparison, the catalog of stats, the threshold and the
text of the numbers are the Python's. The cases add what the real rows do not have: the play-by-play figures that complete a row (``bench_pct``...), a stat missing on one side, a
team that is not there and two other thresholds.
"""
import json
from pathlib import Path
from typing import Any, Dict, List

from src.live_prep.scouting_compare import compare_teams
from src.report_engine.catalog import CATALOG

HERE = Path(__file__).resolve().parent
PBP = {"pts_off_tov_per_game": 14.2, "opp_pts_off_tov_per_game": 12.8, "pts_second_chance_per_game": 11.5, "opp_pts_second_chance_per_game": 13.1,
       "pts_paint_per_game": 34.0, "opp_pts_paint_per_game": 31.5, "bench_pct": 27.4}


def _rows() -> List[Dict[str, Any]]:
    return json.loads((HERE / "team_stats_feb.json").read_text(encoding="utf-8"))["cases"][0]["team_stats"]


def build() -> Dict[str, Any]:
    rows = _rows()
    a, b, c = rows[0], rows[1], rows[2]
    equal = dict(a)
    without_one = {k: v for k, v in b.items() if k not in ("efg_percentage", "net_rating")}
    pbp_a = {**a, **PBP}
    pbp_b = {**b, **{k: round(v * 1.2, 3) for k, v in PBP.items()}}
    cases = [
        {"name": "two teams of the league", "own": a, "rival": b},
        {"name": "the same two, the other way round", "own": b, "rival": a},
        {"name": "another pair", "own": c, "rival": a},
        {"name": "the same team: nothing is an advantage", "own": a, "rival": equal},
        {"name": "the play-by-play figures complete the rows", "own": pbp_a, "rival": pbp_b},
        {"name": "a stat missing on one side is left out", "own": a, "rival": without_one},
        {"name": "a team that is not there: nothing to compare", "own": None, "rival": b},
        {"name": "a looser threshold", "own": a, "rival": b, "threshold_pct": 15.0},
        {"name": "a stricter threshold", "own": a, "rival": b, "threshold_pct": 0.5},
    ]
    for case in cases:
        case["expected"] = compare_teams(case["own"], case["rival"], case["threshold_pct"]) if "threshold_pct" in case else compare_teams(case["own"], case["rival"])
    return {"catalog": [{"key": s.key, "label": s.label, "group": s.group, "higher_is_better": s.higher_is_better, "pct": s.pct} for s in CATALOG], "cases": cases}
