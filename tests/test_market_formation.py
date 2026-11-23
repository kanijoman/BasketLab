"""The formation index (#893, E3 of epic #872): what a player of the formation (U12 to U18) is expected to be in the senior game if he gets there, with a range, validated a PROMOTION (season) out at a time.

``z_senior = a + b * z_formation (+ group) + noise`` per sex and axis, where ``z_senior`` is the z of his first senior season put on the COMMON scale of the equivalence graph (minus the level of his competition,
``theta``), so that it can be translated to any senior competition by adding that level back. Only players who reach the senior game with enough minutes are seen: the index is CONDITIONAL on getting there (it
says so). Synthetic worlds with a known relation check that it is recovered and not invented; the validation must beat «the mean of those who made it» and hold its 80 % range.
"""
import random

import pytest

from src.market.equivalence import AXES, Observation
from src.market.formation import FormationObs, fit, leave_one_season_out, pairs, project

SEN = "F|feb|SEN"
THETA = {SEN: (0.3,) * len(AXES), "F|feb|HIGH": (0.9,) * len(AXES)}
levels = lambda node: THETA.get(node)                                                        # noqa: E731
B = 0.6


def world(seed=1, persons=800, slope=B, noise=0.6, seasons=(2020, 2021, 2022, 2023, 2024), reach=1.0):
    """Formation observations and the senior ones they lead to (the next season, on the scale of the node: ``z_ref + theta``)."""
    rng = random.Random(seed)
    formation, senior, births = [], [], {}
    for k in range(persons):
        season = rng.choice(seasons[:-1])
        group = rng.choice(("U16", "U18"))
        z = tuple(rng.gauss(0, 1) for _ in AXES)
        formation.append(FormationObs(f"p{k}", season, group, "F", 600, z))
        if rng.random() <= reach:
            ref = tuple(slope * v + rng.gauss(0, noise) for v in z)
            senior.append(Observation(f"p{k}", SEN, season + 1, None, 900, tuple(r + t for r, t in zip(ref, THETA[SEN]))))
        births[f"p{k}"] = season - 17
    return formation, senior, births


class TestThePairs:
    def test_the_target_is_the_senior_z_without_the_level_of_his_competition(self):
        formation, senior, _ = world(persons=30)
        found = pairs(formation, senior, levels)
        assert found and all(abs(p.z_senior[0] - (s.z[0] - 0.3)) < 1e-9 for p in found for s in senior if s.person == p.person)

    def test_a_player_who_never_reaches_the_senior_game_or_whose_competition_has_no_level_makes_no_pair(self):
        formation, senior, _ = world(persons=40, reach=0.5)
        assert 0 < len(pairs(formation, senior, levels)) < 40
        assert pairs(formation, senior, lambda node: None) == []

    def test_only_the_next_season_in_the_same_sex_counts(self):
        f = [FormationObs("a", 2020, "U18", "F", 600, (0.0,) * len(AXES))]
        late = [Observation("a", SEN, 2022, None, 900, (0.0,) * len(AXES))]
        male = [Observation("a", "M|feb|SEN", 2021, None, 900, (0.0,) * len(AXES))]
        assert pairs(f, late, levels) == [] and pairs(f, male, lambda n: (0.0,) * len(AXES)) == []


class TestTheFit:
    def test_it_recovers_the_relation_of_the_world(self):
        formation, senior, _ = world()
        model = fit(pairs(formation, senior, levels))
        assert all(b == pytest.approx(B, abs=0.08) for b in model.slope["F"])

    def test_it_invents_nothing_where_the_formation_says_nothing_about_the_senior_game(self):
        formation, senior, _ = world(slope=0.0)
        assert all(abs(b) < 0.1 for b in fit(pairs(formation, senior, levels)).slope["F"])

    def test_the_order_of_the_pairs_does_not_change_the_answer(self):
        formation, senior, _ = world(persons=200)
        found = pairs(formation, senior, levels)
        assert fit(found).slope == fit(list(reversed(found))).slope


class TestTheProjection:
    def test_it_adds_back_the_level_of_the_senior_competition_and_gives_a_range(self):
        formation, senior, _ = world()
        model = fit(pairs(formation, senior, levels))
        z = (1.0,) * len(AXES)
        low, high = project(model, "F", z, "U18", THETA[SEN]), project(model, "F", z, "U18", THETA["F|feb|HIGH"])
        assert all(h["mean"] - l_["mean"] == pytest.approx(0.6, abs=1e-9) for h, l_ in zip(high, low))
        assert all(r["lo"] < r["mean"] < r["hi"] for r in low)

    def test_a_sex_the_model_does_not_know_has_no_projection(self):
        formation, senior, _ = world(persons=100)
        assert project(fit(pairs(formation, senior, levels)), "M", (0.0,) * len(AXES), "U18", THETA[SEN]) is None


class TestTheValidation:
    def study(self, **kw):
        formation, senior, _ = world(persons=1500, **kw)
        return leave_one_season_out(formation, senior, lambda season: levels)

    def test_it_beats_the_mean_of_those_who_made_it_in_a_promotion_it_has_not_seen_and_its_range_holds(self):
        o = self.study()["overall"]
        assert o["mae_model"] < o["mae_mean"] * 0.9 and abs(o["coverage"] - 0.8) < 0.05

    def test_with_no_relation_it_does_not_claim_to_beat_the_mean(self):
        o = self.study(slope=0.0)["overall"]
        assert o["mae_model"] >= o["mae_mean"] * 0.99

    def test_the_levels_and_the_fit_are_made_without_the_season_it_predicts_regression(self):
        formation, senior, _ = world(persons=300)
        asked, fitted = [], []
        import src.market.formation as module
        real = module.fit
        module_fit = lambda found, *a, **k: (fitted.append({p.season_to for p in found}), real(found, *a, **k))[1]      # noqa: E731
        import pytest as _p
        mp = _p.MonkeyPatch()
        mp.setattr(module, "fit", module_fit)
        try:
            leave_one_season_out(formation, senior, lambda season: (asked.append(season), levels)[1])
        finally:
            mp.undo()
        assert sorted(asked) == sorted({s.season for s in senior}) and all(season not in seasons for season, seasons in zip(sorted(asked), fitted))


class TestTheObservations:
    def entry(self, **kw):
        return {"category": "formacion", "league": "feb", "gender": "F", "age_group": "U18", "season": "2024", **kw}

    def row(self, **kw):
        return {"comp": "c", "person_id": "feb:1", "linked_to": None, "minutes": 500, "eligible": True, "pct": {a: 50 for a in AXES}, **kw}

    def test_only_the_formation_of_feb_with_minutes_enough_and_the_eight_percentiles_counts(self):
        from src.market.formation import formation_observations
        ok = formation_observations([self.row()], {"c": self.entry()})
        assert len(ok) == 1 and ok[0].group == "U18" and ok[0].sex == "F"
        for bad_row, entry in ((self.row(eligible=False), self.entry()), (self.row(pct={**{a: 50 for a in AXES}, "blk": None}), self.entry()),
                               (self.row(), self.entry(league="fbcyl")), (self.row(), self.entry(category="senior")), (self.row(), self.entry(age_group=None))):
            assert formation_observations([bad_row], {"c": entry}) == []

    def test_a_player_in_two_teams_of_the_same_group_keeps_the_row_with_more_minutes_whatever_the_order(self):
        from src.market.formation import formation_observations
        a, b = self.row(minutes=300, pct={x: 20 for x in AXES}), self.row(minutes=700, pct={x: 80 for x in AXES})
        for rows in ([a, b], [b, a]):
            assert formation_observations(rows, {"c": self.entry()})[0].minutes == 700
