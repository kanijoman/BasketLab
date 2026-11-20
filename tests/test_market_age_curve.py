"""The age curve of the projection (#892, E2 of epic #872): how much a player's z changes from one season to the next beyond what the reliability says, as a function of his age.

``z_next = rho * z + effect(age) + noise``, per axis, fitted on the players who stay in a competition (the effect of the competition is not in it) and validated a season out at a time: a model that does not
beat «only shrink by the reliability» is not shown. Synthetic worlds with a KNOWN curve check that it is recovered (and that nothing is invented where there is none); the real sample checks the structure.
"""
import gzip
import json
import random
from pathlib import Path

import pytest

from src.market.age_curve import AGE_MAX, AGE_MIN, births_of, fit, leave_one_season_out, pairs, project
from src.market.equivalence import AXES, Observation, observations

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "talent_rows_movers.json.gz"
DATA = json.loads(gzip.decompress(FIXTURE.read_bytes()).decode("utf-8"))
NODE = "F|feb|A"
RHO = 0.7


def curve(age):
    """The truth of the synthetic world: young players improve, old ones decline."""
    return 0.25 if age <= 18 else 0.1 if age <= 21 else 0.0 if age <= 29 else -0.12


def world(seed=1, persons=900, effect=curve, seasons=(2020, 2021, 2022, 2023, 2024), noise=0.5):
    """Observations of persons who stay in one competition for the seasons they play, with their births, generated from ``z_next = RHO * z + effect(age) + noise``."""
    rng = random.Random(seed)
    obs, births = [], {}
    for k in range(persons):
        born = 2024 - rng.randint(17, 34)
        births[f"p{k}"] = born
        z = tuple(rng.gauss(0, 1) for _ in AXES)
        start = rng.choice(seasons[:-1])
        for season in range(start, seasons[-1] + 1):
            obs.append(Observation(f"p{k}", NODE, season, None, 900, z))
            age = season - born
            z = tuple(RHO * v + effect(age) + rng.gauss(0, noise) for v in z)
    return obs, births


class TestThePairs:
    def test_a_pair_is_the_same_person_in_the_same_competition_h_seasons_later_with_his_age(self):
        obs, births = world(persons=50)
        for h in (1, 2):
            found = pairs(obs, births, h)
            assert found and all(p.season_to - p.season_from == h and p.age == p.season_from - births[p.person] for p in found)

    def test_a_person_without_birth_or_in_another_competition_makes_no_pair(self):
        a, b = Observation("x", NODE, 2020, None, 900, (0.0,) * 8), Observation("x", "F|feb|B", 2021, None, 900, (0.0,) * 8)
        assert pairs([a, b], {"x": 2000}, 1) == []                                   # moved: that is a translation, not a stay
        assert pairs([a, Observation("x", NODE, 2021, None, 900, (0.0,) * 8)], {}, 1) == []

    def test_the_birth_of_a_person_is_the_year_his_rows_say_most_often_and_it_is_linked_to_the_feb_person(self):
        rows = [{"person_id": "feb:1", "birth": "2001-05-06"}, {"person_id": "feb:1", "birth": "2001-05-06"}, {"person_id": "feb:1", "birth": "2002-01-01"},
                {"person_id": "fbcyl:9", "linked_to": "feb:1", "birth": None}, {"person_id": "feb:2", "birth": None}, {"person_id": "feb:3", "birth": "no es una fecha"}]
        assert births_of(rows) == {"feb:1": 2001}


class TestTheFit:
    def test_it_recovers_the_curve_of_the_world_within_its_error(self):
        obs, births = world()
        model = fit(pairs(obs, births, 1))
        for age, want in ((17, 0.25), (20, 0.1), (25, 0.0), (32, -0.12)):
            got = [model.effect["F"][i][age] for i in range(len(AXES))]
            assert sum(got) / len(got) == pytest.approx(want, abs=0.07), age

    def test_it_invents_no_curve_where_there_is_none(self):
        obs, births = world(effect=lambda a: 0.0)
        model = fit(pairs(obs, births, 1))
        assert max(abs(model.effect["F"][i][a]) for i in range(len(AXES)) for a in range(AGE_MIN, AGE_MAX + 1)) < 0.08

    def test_an_age_with_few_players_is_pulled_to_zero_not_trusted(self):
        obs, births = world(persons=900)
        tiny = [p for p in pairs(obs, births, 1) if p.age != 33] + [p for p in pairs(obs, births, 1) if p.age == 33][:3]
        full = fit(pairs(obs, births, 1)).effect["F"][0][33]
        assert abs(fit(tiny).effect["F"][0][33]) <= abs(full) + 1e-9

    def test_ages_outside_the_range_use_the_edge_of_the_curve(self):
        obs, births = world()
        model = fit(pairs(obs, births, 1))
        assert model.effect_at("F", 0, 12) == model.effect_at("F", 0, AGE_MIN) and model.effect_at("F", 0, 45) == model.effect_at("F", 0, AGE_MAX)

    def test_the_order_of_the_pairs_does_not_change_the_answer(self):
        obs, births = world(persons=300)
        found = pairs(obs, births, 1)
        assert fit(found).effect == fit(list(reversed(found))).effect


class TestTheProjection:
    def test_it_is_the_reliability_times_the_z_plus_the_effect_of_his_age_with_a_range(self):
        obs, births = world()
        model = fit(pairs(obs, births, 1))
        z = (1.0,) * len(AXES)
        young, old = project(model, "F", z, 17), project(model, "F", z, 33)
        assert all(y["mean"] > o["mean"] for y, o in zip(young, old))
        assert all(r["lo"] < r["mean"] < r["hi"] for r in young)

    def test_a_sex_the_model_does_not_know_has_no_projection(self):
        obs, births = world(persons=300)
        assert project(fit(pairs(obs, births, 1)), "M", (0.0,) * len(AXES), 20) is None


class TestTheValidation:
    def test_with_a_real_curve_the_model_beats_only_shrinking_in_a_season_it_has_not_seen_and_its_range_holds(self):
        obs, births = world(persons=1500)
        study = leave_one_season_out(pairs(obs, births, 1))
        o = study["overall"]
        assert o["mae_model"] < o["mae_rho_only"] * 0.97 and abs(o["coverage"] - 0.8) < 0.05

    def test_with_no_curve_it_does_not_claim_to_beat_the_baseline(self):
        obs, births = world(persons=1500, effect=lambda a: 0.0)
        o = leave_one_season_out(pairs(obs, births, 1))["overall"]
        assert o["mae_model"] >= o["mae_rho_only"] * 0.99

    def test_the_season_it_predicts_is_not_in_the_fit_regression(self, monkeypatch):
        obs, births = world(persons=300)
        import src.market.age_curve as module
        seen = []
        real = module.fit
        monkeypatch.setattr(module, "fit", lambda found, *a, **k: (seen.append({(p.season_from, p.season_to) for p in found}), real(found, *a, **k))[1])
        leave_one_season_out(pairs(obs, births, 1))
        assert seen and all(not any(s in pair for pair in fitted) for s, fitted in zip(sorted({p.season_to for p in pairs(obs, births, 1)}), seen))


def test_the_real_rows_make_pairs_and_a_curve_with_the_young_improving_more_than_the_prime():
    obs = observations(DATA["rows"], DATA["competitions"])
    found = pairs(obs, births_of(DATA["rows"]), 1)
    if len(found) < 100:
        pytest.skip("the sample has too few stayers with a birth")
    model = fit(found)
    sex = next(iter(model.effect))
    mean = lambda age: sum(model.effect_at(sex, i, age) for i in range(len(AXES))) / len(AXES)            # noqa: E731
    assert mean(18) >= mean(26)
