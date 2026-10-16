"""Season pipelines read the exact possessions and validated rebounds / turnovers stored in ``DERIVED`` (#372).

Games without ``DERIVED`` (older data, FBCYL, games without pbp) keep the box-score formula as the fallback.
"""
import pytest

from db_helpers import new_mock_db
from src.database.aggregation.pipeline_builder import AggregationPipelineBuilder as Builder


def _team(tid, name, **kw):
    box = {"pts": 80, "p2m": 20, "p2a": 40, "p3m": 5, "p3a": 15, "p1m": 10, "p1a": 20, "ro": 8, "rd": 25, "to": 10,
           "assist": 10, "st": 5, "bs": 2}
    box.update(kw)
    return {"id": tid, "name": name, "TOTAL": {k: str(v) for k, v in box.items()}}


def _game(match_id, derived=None, quarters=4):
    doc = {"_id": match_id,
           "HEADER": {"starttime": "05-10-2025 - 12:30", "QUARTERS": {"QUARTER": [{}] * quarters},
                      "TEAM": [{"id": "A", "name": "Local"}, {"id": "B", "name": "Visitante"}]},
           "BOXSCORE": {"TEAM": [_team("A", "Local"), _team("B", "Visitante", pts=70, ro=6, rd=20, to=12)]}}
    if derived:
        doc["DERIVED"] = {"v": 1, "TEAM": derived}
    return doc


def _derived(a_poss, b_poss, a_orb=9, b_orb=7, a_drb=26, b_drb=21, a_tov=11, b_tov=13):
    return [{"id": "A", "possessions": a_poss, "orb": a_orb, "drb": a_drb, "tov": a_tov},
            {"id": "B", "possessions": b_poss, "orb": b_orb, "drb": b_drb, "tov": b_tov}]


def _run(docs, pipeline):
    col = new_mock_db("season")["G"]
    col.insert_many(docs)
    return {r["team_name"]: r for r in col.aggregate(pipeline)}


def test_season_possessions_and_rebounds_come_from_the_derived_fields():
    out = _run([_game(1, _derived(75.0, 72.0))], Builder.build_team_stats_pipeline())

    local = out["Local"]
    assert local["total_possessions"] == pytest.approx(75.0)
    assert local["opponent_possessions"] == pytest.approx(72.0)
    assert (local["rebounds_off"], local["rebounds_def"], local["turnovers"]) == (9, 26, 11)
    assert (local["opponent_rebounds_off"], local["opponent_rebounds_def"]) == (7, 21)


def test_games_without_derived_fields_use_the_box_score_estimate_with_the_tracker_free_throw_cost():
    out = _run([_game(1)], Builder.build_team_stats_pipeline())

    # FGA 55 - ORB 8 + TOV 10 + 0.44 * FTA 20
    assert out["Local"]["total_possessions"] == pytest.approx(55 - 8 + 10 + 0.44 * 20)
    assert (out["Local"]["rebounds_off"], out["Local"]["turnovers"]) == (8, 10)


def test_a_season_can_mix_games_with_and_without_derived_fields():
    out = _run([_game(1, _derived(75.0, 72.0)), _game(2)], Builder.build_team_stats_pipeline())

    assert out["Local"]["total_possessions"] == pytest.approx(75.0 + 55 - 8 + 10 + 0.44 * 20)


def test_overtime_possessions_are_scaled_to_40_minutes():
    out = _run([_game(1, _derived(90.0, 90.0), quarters=5)], Builder.build_team_stats_pipeline())

    assert out["Local"]["total_possessions"] == pytest.approx(90.0 * 40 / 45)


def test_per_game_rows_use_the_derived_possessions_for_both_teams():
    col = new_mock_db("pg")["G"]
    col.insert_one(_game(1, _derived(75.0, 72.0)))
    local = next(r for r in col.aggregate(Builder.build_per_game_raw_pipeline()) if r["team_name"] == "Local")

    assert local["possessions"] == pytest.approx(75.0)
    assert local["off_rebounds"] == 9 and local["opp_off_rebounds"] == 7
    assert local["oer_game"] == pytest.approx(80 / 75.0 * 100)
    assert local["der_game"] == pytest.approx(70 / 75.0 * 100)   # rival points per own possession (existing convention)


def test_opponent_pipeline_reads_the_derived_fields_of_the_rival():
    out = _run([_game(1, _derived(75.0, 72.0))], Builder.build_opponent_stats_pipeline())

    # "Local" row = what its rivals did against it: the visitor's numbers
    assert out["Local"]["total_possessions"] == pytest.approx(72.0)
    assert out["Local"]["opponent_possessions"] == pytest.approx(75.0)
    assert out["Local"]["turnovers"] == 13
