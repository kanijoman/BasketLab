"""The registry of the team formulas (#1153): ``config/formulas.json`` is the only place where a rate is defined; Python, the browser and the Mongo pipelines read it.

* the registry gives the textbook value of ``tests/formulas/vector.json`` (written independently of it) for every formula and case, ``None`` when a denominator is 0;
* the Mongo expressions it builds give the same numbers (run on mongomock) with the safe-divide convention of the tables (0 for an empty denominator);
* the Four Factors are those of CLAUDE.md and the cost of a free throw is the tracker's.
"""
import json
from pathlib import Path

import pytest
from db_helpers import new_mock_db

from src.live_core.four_factors import FT_POSSESSION_COST
from src.stats.formulas import COUNTERS, FORMULAS, evaluate, evaluate_all, mongo_expression

ROOT = Path(__file__).resolve().parent
VECTOR = json.loads((ROOT / "formulas" / "vector.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", VECTOR, ids=[c["name"] for c in VECTOR])
def test_every_formula_gives_the_textbook_value(case):
    got = evaluate_all(case["counters"])

    assert set(got) == set(case["expected"]) == set(FORMULAS)
    for name, want in case["expected"].items():
        assert (got[name] is None) if want is None else got[name] == pytest.approx(want, rel=1e-12), name


def test_the_registry_covers_the_four_factors_with_the_formulas_of_claude_md():
    counters = VECTOR[0]["counters"]
    fga = counters["fg2a"] + counters["fg3a"]

    assert evaluate("efg_percentage", counters) == pytest.approx((counters["fg2m"] + counters["fg3m"] + 0.5 * counters["fg3m"]) / fga * 100)
    assert evaluate("turnover_rate", counters) == pytest.approx(counters["tov"] / (fga + 0.44 * counters["fta"] + counters["tov"]) * 100)
    assert evaluate("offensive_rebound_rate", counters) == pytest.approx(counters["orb"] / (counters["orb"] + counters["opp_drb"]) * 100)
    assert evaluate("free_throw_rate", counters) == pytest.approx(counters["fta"] / fga * 100)


def test_the_cost_of_a_free_throw_is_the_one_of_the_tracker():
    den = FORMULAS["turnover_rate"]["den"]

    assert den["fta"] == FT_POSSESSION_COST == 0.44


def test_steals_and_blocks_are_per_rival_possession_and_a_defensive_rating_too():
    """Decided 27/11/2026 (#1153): ROB% and TAP% are divided by the possessions of the RIVAL, as the DRtg; the offensive ones by the team's own."""
    assert set(FORMULAS["steal_rate"]["den"]) == set(FORMULAS["block_rate"]["den"]) == set(FORMULAS["defensive_rating"]["den"]) == {"opp_poss"}
    assert set(FORMULAS["assist_rate"]["den"]) == set(FORMULAS["offensive_rating"]["den"]) == {"poss"}


def test_an_unknown_counter_is_an_error_not_a_zero():
    with pytest.raises(KeyError):
        evaluate("turnover_rate", {"tov": 1})


@pytest.mark.parametrize("case", VECTOR, ids=[c["name"] for c in VECTOR])
def test_the_mongo_expressions_give_the_same_numbers_with_zero_for_an_empty_denominator(case):
    col = new_mock_db("formulas")["T"]
    col.insert_one({"_id": 1, **{k: v for k, v in case["counters"].items()}})
    fields = {name: f"${name}" for name in COUNTERS}
    stage = {"$project": {name: mongo_expression(name, fields) for name in FORMULAS if name != "net_rating"}}
    stage["$project"]["net_rating"] = mongo_expression("net_rating", fields)

    row = next(col.aggregate([stage]))

    for name, want in case["expected"].items():
        assert row[name] == pytest.approx(0 if want is None else want, rel=1e-12, abs=1e-12), name
