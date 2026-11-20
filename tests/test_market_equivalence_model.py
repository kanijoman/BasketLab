"""The estimator of the equivalence graph (#891, E1b of epic #872): ``z_B = rho * z_A + (theta_B - theta_A)`` fitted on ALL the movements at once.

One level (``theta``) per competition and axis, by least squares over the graph of the movements, so that any two competitions that are connected get a translation (the difference of their levels) and its
uncertainty comes from the covariance of the fit, with the standard errors CLUSTERED by person (one player who moves three times is one source of noise, not three). The shapes are checked on SYNTHETIC data with
known parameters (a chain of three competitions whose levels, reliabilities and noise are chosen) so that what the estimator recovers can be compared with the truth, and on the REAL rows of
``tests/fixtures/talent_rows_movers.json.gz`` for the signs and the structure.
"""
import gzip
import json
import random
from pathlib import Path

import pytest

from src.market.equivalence import AXES, Movement, movements, observations, stayers
from src.market.equivalence_model import MIN_PERSONS, Z80, fit, reliability, translate

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "talent_rows_movers.json.gz"
DATA = json.loads(gzip.decompress(FIXTURE.read_bytes()).decode("utf-8"))
OBSERVATIONS = observations(DATA["rows"], DATA["competitions"])
REAL_MODEL = fit(movements(OBSERVATIONS), stayers(OBSERVATIONS))
A, B, C, D = "F|feb|A", "F|feb|B", "F|feb|C", "M|feb|D"
THETA = {A: 0.0, B: -0.8, C: -1.6}                       # the levels of the world the synthetic data comes from (z units, higher is easier)
RHO, SIGMA = 0.7, 0.5


def world(seed=1, per_edge=120, theta=THETA, rho=RHO, sigma=SIGMA, edges=((A, B), (B, C)), noise_person=0.0):
    """Movements generated from the model: ``per_edge`` persons moving each way on each edge, z_to = rho * z_from + theta_to - theta_from + noise."""
    rng = random.Random(seed)
    moves, stay, k = [], [], 0
    for a, b in edges:
        for src, dst in ((a, b), (b, a)):
            for _ in range(per_edge):
                k += 1
                z = tuple(rng.gauss(0, 1) for _ in AXES)
                shared = rng.gauss(0, noise_person) if noise_person else 0.0
                to = tuple(rho * v + theta[dst] - theta[src] + rng.gauss(0, sigma) + shared for v in z)
                moves.append(Movement(f"p{k}", src, dst, 2020, 2021, None, z, to))
    for node in theta:                                    # the stayers measure the reliability: z_next = rho * z + noise with variance 1 - rho^2
        for _ in range(300):
            z = tuple(rng.gauss(0, 1) for _ in AXES)
            stay.append(Movement(f"s{len(stay)}", node, node, 2020, 2021, None, z, tuple(rho * v + rng.gauss(0, (1 - rho * rho) ** 0.5) for v in z)))
    return moves, stay


class TestTheReliability:
    def test_it_is_the_correlation_of_the_stayers_per_axis_and_per_sex(self):
        moves, stay = world()
        rho = reliability(stay)
        assert set(rho) == {"F"} and all(0.6 < v < 0.8 for v in rho["F"])

    def test_men_and_women_have_their_own(self):
        _, stay = world()
        rng = random.Random(5)
        men = [Movement(s.person, D, D, s.from_season, s.to_season, None, s.z_from, tuple(0.3 * v + rng.gauss(0, 1) for v in s.z_from)) for s in stay[:300]]
        rho = reliability(stay + men)
        assert rho["M"][0] < 0.5 < 0.6 < rho["F"][0]

    def test_an_axis_with_no_variation_has_no_reliability_instead_of_a_division_by_zero(self):
        flat = [Movement(f"s{i}", A, A, 2020, 2021, None, (0.0,) * len(AXES), (0.0,) * len(AXES)) for i in range(20)]
        assert reliability(flat) == {}


class TestTheLevels:
    def test_the_levels_of_the_world_are_recovered_within_their_standard_error(self):
        moves, stay = world()
        model = fit(moves, stay)
        for i in range(len(AXES)):
            for src, dst in ((A, B), (B, C), (A, C)):
                got = translate(model, src, dst, (0.0,) * len(AXES))[i]
                truth = THETA[dst] - THETA[src]
                assert abs(got["mean"] - truth) < 3 * got["se_level"], (AXES[i], src, dst, got, truth)

    def test_the_translation_is_the_reliability_times_the_z_plus_the_shift_of_level(self):
        model = fit(*world())
        zero = translate(model, A, B, (0.0,) * len(AXES))[0]["mean"]
        one = translate(model, A, B, (1.0,) * len(AXES))[0]["mean"]
        assert one - zero == pytest.approx(model.rho["F"][0])

    def test_the_other_direction_is_the_opposite_shift(self):
        model = fit(*world())
        ab = translate(model, A, B, (0.0,) * len(AXES))
        ba = translate(model, B, A, (0.0,) * len(AXES))
        assert all(x["mean"] == pytest.approx(-y["mean"]) for x, y in zip(ab, ba))

    def test_two_competitions_with_no_edge_between_them_are_translated_through_the_ones_in_between_with_more_uncertainty(self):
        model = fit(*world())
        near, far = translate(model, A, B, (0.0,) * len(AXES))[0], translate(model, A, C, (0.0,) * len(AXES))[0]
        assert far["se_level"] > near["se_level"] and far["hi"] - far["lo"] > near["hi"] - near["lo"]
        assert far["mean"] == pytest.approx(near["mean"] + translate(model, B, C, (0.0,) * len(AXES))[0]["mean"], abs=0.05)

    def test_competitions_that_are_not_connected_have_no_translation(self):
        moves, stay = world()
        other, other_stay = world(seed=9, edges=((D, "M|feb|E"),), theta={D: 0.0, "M|feb|E": -0.5})
        model = fit(moves + other, stay + other_stay)
        assert translate(model, A, D, (0.0,) * len(AXES)) is None and translate(model, A, "F|feb|NOWHERE", (0.0,) * len(AXES)) is None
        assert translate(model, D, "M|feb|E", (0.0,) * len(AXES)) is not None

    def test_an_edge_with_fewer_persons_than_the_minimum_does_not_exist(self):
        moves, stay = world(per_edge=MIN_PERSONS // 2 - 1)                                  # both directions together: fewer than the minimum persons
        model = fit(moves, stay)
        assert MIN_PERSONS == 40 and translate(model, A, B, (0.0,) * len(AXES)) is None

    def test_the_answer_does_not_depend_on_the_order_of_the_movements(self):
        moves, stay = world()
        shuffled = list(moves)
        random.Random(3).shuffle(shuffled)
        a, b = fit(moves, stay), fit(shuffled, stay)
        assert [x["mean"] for x in translate(a, A, C, (0.5,) * len(AXES))] == pytest.approx([x["mean"] for x in translate(b, A, C, (0.5,) * len(AXES))], abs=1e-9)


class TestTheUncertainty:
    def test_the_interval_of_80_percent_holds_about_80_percent_of_new_movers(self):
        moves, stay = world(seed=2)
        model = fit(moves, stay)
        test, _ = world(seed=77, per_edge=400)
        hits = total = 0
        for m in test:
            out = translate(model, m.from_node, m.to_node, m.z_from)
            for i, got in enumerate(out):
                total += 1
                hits += got["lo"] <= m.z_to[i] <= got["hi"]
        assert 0.76 < hits / total < 0.84 and Z80 == pytest.approx(1.2816, abs=1e-3)

    def test_more_movers_give_a_narrower_level_uncertainty(self):
        small = translate(fit(*world(per_edge=60)), A, B, (0.0,) * len(AXES))[0]["se_level"]
        large = translate(fit(*world(per_edge=600)), A, B, (0.0,) * len(AXES))[0]["se_level"]
        assert large < small / 2

    def test_a_person_who_moves_many_times_with_the_same_noise_is_not_counted_as_many_independent_ones(self):
        """The clustered error is larger than the naive one when the movements of a person share noise (a player who keeps being better than his level says)."""
        moves, stay = world(per_edge=60, noise_person=0.6)
        repeated = []
        for m in moves:
            for copy in range(3):
                repeated.append(Movement(m.person, m.from_node, m.to_node, 2020 + copy, 2021 + copy, None, m.z_from, m.z_to))
        clustered = translate(fit(repeated, stay), A, B, (0.0,) * len(AXES))[0]["se_level"]
        naive = translate(fit(repeated, stay, cluster=False), A, B, (0.0,) * len(AXES))[0]["se_level"]
        assert clustered > 1.4 * naive


class TestTheSlope:
    def test_with_a_free_slope_the_estimator_finds_the_one_the_world_has_even_when_it_is_not_the_reliability(self):
        """A skill that is kept better in the new competition than its reliability says (assists and steals of the real cases): the data has slope 0.9 and the stayers 0.7."""
        moves, stay = world(rho=0.9)
        _, stay_low = world(rho=0.7)
        fixed = fit(moves, stay_low)
        free = fit(moves, stay_low, slope="free")
        assert free.rho["F"][0] == pytest.approx(0.9, abs=0.06) and fixed.rho["F"][0] == pytest.approx(0.7, abs=0.06)
        got = translate(free, A, B, (2.0,) * len(AXES))[0]["mean"] - translate(free, A, B, (0.0,) * len(AXES))[0]["mean"]
        assert got == pytest.approx(1.8, abs=0.12)


class TestTheRealRows:
    @pytest.fixture()
    def model(self):
        return REAL_MODEL

    def test_moving_up_costs_points_and_accuracy_and_moving_down_gives_them_back(self, model):
        zero = (0.0,) * len(AXES)
        up = translate(model, "F|feb|L.F.-2", "F|feb|LF CHALLENGE", zero)
        down = translate(model, "F|feb|LF CHALLENGE", "F|feb|L.F.-2", zero)
        pts, efg = AXES.index("pts"), AXES.index("efg")
        assert up[pts]["mean"] < -0.2 and up[efg]["mean"] < -0.1 and down[pts]["mean"] > 0.2 and down[efg]["mean"] > 0.1
        assert translate(model, "M|feb|TERCERA FEB", "M|feb|PRIMERA FEB", zero)[pts]["mean"] < up[pts]["mean"]                # two levels cost more than one

    def test_men_and_women_are_never_connected(self, model):
        assert translate(model, "F|feb|LF CHALLENGE", "M|feb|PRIMERA FEB", (0.0,) * len(AXES)) is None

    def test_the_intervals_are_ranges_with_a_lower_and_an_upper_bound_and_a_percentile_for_each(self, model):
        out = translate(model, "M|feb|SEGUNDA FEB", "M|feb|PRIMERA FEB", (1.0,) * len(AXES))
        assert len(out) == len(AXES) and all(o["lo"] < o["mean"] < o["hi"] and 0 < o["pct_lo"] < o["pct_mean"] < o["pct_hi"] < 100 for o in out)


# --- the origin of two seasons (E1c): ONE estimator for the user, two reliabilities inside --------------------------------------------------------------------------------------------------------------------

from src.market.equivalence import Observation  # noqa: E402
from src.market.equivalence_model import estimate, fit_observations  # noqa: E402

ABILITY = 0.8                                            # how much of a z is the player's lasting skill (the rest is the noise of a season)


def career_world(seed=11, players=900, theta_down=-0.9):
    """Observations of players with a lasting skill: a season is ``ABILITY * skill + noise``; some play two seasons in A and then one in B (a level ``theta_down`` below), some two in A and one more in A (stayers)."""
    rng = random.Random(seed)
    obs, k = [], 0
    for _ in range(players):
        k += 1
        skill = [rng.gauss(0, 1) for _ in AXES]
        make = lambda node, season, shift=0.0: Observation(f"c{k}", node, season, None, 20000, tuple(ABILITY * v + shift + rng.gauss(0, 0.6) for v in skill))      # noqa: E731
        obs += [make(A, 2020), make(A, 2021)]
        obs.append(make(B, 2022, theta_down) if k % 2 else make(A, 2022))
        if k % 3 == 0:
            obs.append(make(A, 2019))
    return obs


def test_the_same_competition_on_both_sides_has_no_shift_and_no_uncertainty_of_it_regression():
    """``d[b], d[a] = 1, -1`` with a == b left a -1 and made the shift of a competition to itself uncertain."""
    out = translate(REAL_MODEL, next(iter(REAL_MODEL.fits["F"].nodes)) if "F" in REAL_MODEL.fits else next(iter(REAL_MODEL.fits.values())).nodes[0], next(iter(REAL_MODEL.fits["F"].nodes)) if "F" in REAL_MODEL.fits else next(iter(REAL_MODEL.fits.values())).nodes[0], (0.0,) * len(AXES))
    assert all(o["se_level"] == 0 and o["mean"] == pytest.approx(0.0, abs=1e-9) for o in out)


class TestTheOriginOfTwoSeasons:
    def test_the_reliability_of_two_seasons_is_higher_than_of_one_and_both_are_kept(self):
        model = fit_observations(career_world())
        assert all(two > one for one, two in zip(model.rho["F"], model.history["F"]["rho"]))

    def test_the_translation_with_two_seasons_keeps_more_of_the_z(self):
        model = fit_observations(career_world())
        one = translate(model, A, B, (1.0,) * len(AXES))[0]["mean"] - translate(model, A, B, (0.0,) * len(AXES))[0]["mean"]
        two = translate(model, A, B, (1.0,) * len(AXES), seasons=2)[0]["mean"] - translate(model, A, B, (0.0,) * len(AXES), seasons=2)[0]["mean"]
        assert two > one + 0.03

    def test_without_enough_history_the_two_season_translation_is_the_one_season_one(self):
        moves, stay = world()
        model = fit(moves, stay)
        assert translate(model, A, B, (1.0,) * len(AXES), seasons=2) == translate(model, A, B, (1.0,) * len(AXES))

    def test_the_estimator_of_a_player_uses_two_seasons_when_he_has_them_and_one_when_he_has_not(self):
        model = fit_observations(career_world())
        z1, z2 = (0.5,) * len(AXES), (1.5,) * len(AXES)
        old = [Observation("x", A, 2023, None, 20000, z1), Observation("x", A, 2022, None, 20000, z2)]
        young = [Observation("y", A, 2023, None, 20000, z1)]
        both, one = estimate(model, old, B), estimate(model, young, B)
        assert both[0]["seasons"] == 2 and one[0]["seasons"] == 1
        assert both[0]["mean"] > one[0]["mean"]                                                       # the extra good season lifts the expectation
        assert estimate(model, old, B)[0]["mean"] == pytest.approx(translate(model, A, B, tuple((a + b) / 2 for a, b in zip(z1, z2)), seasons=2)[0]["mean"])

    def test_an_old_season_alone_is_one_season_never_an_average_with_a_gap(self):
        model = fit_observations(career_world())
        gap = [Observation("x", A, 2023, None, 20000, (0.5,) * len(AXES)), Observation("x", A, 2021, None, 20000, (2.0,) * len(AXES))]
        assert estimate(model, gap, B)[0]["seasons"] == 1

    def test_no_history_or_no_connection_has_no_estimate(self):
        model = fit_observations(career_world())
        assert estimate(model, [], B) is None and estimate(model, [Observation("x", A, 2023, None, 1, (0.0,) * len(AXES))], "F|feb|NOWHERE") is None

    def test_two_seasons_predict_better_than_one_for_players_who_have_them(self):
        """The reason for the second reliability: on new players of the same world the average of two seasons has the smaller error."""
        model = fit_observations(career_world(seed=11))
        fresh = [o for o in career_world(seed=99, players=1200)]
        by_player = {}
        for o in fresh:
            by_player.setdefault(o.person, {})[o.season] = o
        one_err, two_err = [], []
        for seasons in by_player.values():
            if 2022 in seasons and seasons[2022].node == B:
                target = seasons[2022]
                last_only = estimate(model, [seasons[2021]], B)
                both = estimate(model, [seasons[2021], seasons[2020]], B)
                for i in range(len(AXES)):
                    one_err.append(abs(target.z[i] - last_only[i]["mean"]))
                    two_err.append(abs(target.z[i] - both[i]["mean"]))
        assert sum(two_err) / len(two_err) < 0.97 * sum(one_err) / len(one_err)
