"""The validation of the equivalence estimator (#891, E1b): a season out at a time, with no leak, and the rule that decides whether the range can be shown.

Synthetic worlds with known parameters (``test_market_equivalence_model.world``) spread over seasons, so that the right answer is known; and the REAL rows of ``tests/fixtures/talent_rows_movers.json.gz``
for the structure and for the claim of the design (the model beats not translating and its 80 % interval holds about 80 %).
"""
import gzip
import json
from pathlib import Path

import pytest

from src.market.equivalence import AXES, Movement, movements, observations, stayers
from src.market.equivalence_model import fit
from src.market.equivalence_study import leave_one_season_out, verdict, walk_forward

from test_market_equivalence_model import world

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "talent_rows_movers.json.gz"
DATA = json.loads(gzip.decompress(FIXTURE.read_bytes()).decode("utf-8"))
SEASONS = (2021, 2022, 2023, 2024)


def seasoned(moves, seasons=SEASONS):
    """The same movements spread over the seasons in turn (to_season = from_season + 1)."""
    return [Movement(m.person, m.from_node, m.to_node, seasons[i % len(seasons)] - 1, seasons[i % len(seasons)], m.age, m.z_from, m.z_to) for i, m in enumerate(moves)]


def rounded(value, places=9):
    """The same structure with its numbers rounded: the order of a sum moves the last digits, nothing else."""
    if isinstance(value, dict):
        return {k: rounded(v, places) for k, v in value.items()}
    return round(value, places) if isinstance(value, float) else value


@pytest.fixture(scope="module")
def synthetic():
    moves, stay = world(seed=4, per_edge=160)
    return seasoned(moves), seasoned(stay)


class TestOneSeasonOut:
    def test_every_season_is_predicted_and_the_model_beats_not_translating_and_only_shrinking(self, synthetic):
        study = leave_one_season_out(*synthetic)
        overall = study["overall"]
        assert sorted(study["per_season"]) == list(SEASONS) and overall["n"] == len(synthetic[0]) * len(AXES)
        assert overall["mae_model"] < overall["mae_rho_only"] < overall["mae_identity"]

    def test_the_interval_of_80_percent_holds_about_80_percent_of_the_movements_it_did_not_see(self, synthetic):
        assert verdict(leave_one_season_out(*synthetic))["publish"] is True
        assert 0.75 < leave_one_season_out(*synthetic)["overall"]["coverage"] < 0.85

    def test_it_reports_each_axis_and_each_pair_of_competitions(self, synthetic):
        study = leave_one_season_out(*synthetic)
        assert list(study["per_axis"]) == list(AXES) and all(v["n"] > 0 for v in study["per_axis"].values())
        assert set(study["per_edge"]) == {"A <-> B (F)", "B <-> C (F)"} and study["per_edge"]["A <-> B (F)"]["coverage"] == pytest.approx(0.8, abs=0.06)

    def test_what_the_model_is_fitted_with_has_nothing_of_the_season_it_predicts(self, synthetic):
        seen = []

        def spy(moves, stay, **options):
            seen.append((sorted({m.from_season for m in moves} | {m.to_season for m in moves}), sorted({s.from_season for s in stay} | {s.to_season for s in stay})))
            return fit(moves, stay, **options)

        leave_one_season_out(*synthetic, fit_fn=spy)
        for season, (moves_seasons, stay_seasons) in zip(SEASONS, seen):
            assert season not in moves_seasons and season not in stay_seasons, season

    def test_the_numbers_of_the_season_it_predicts_cannot_change_what_it_predicts(self, synthetic):
        """Garbage in the z of the season to predict changes the error of THAT season (the real value moved) but not what the model said: the fit never saw it."""
        moves, stay = synthetic
        garbage = [Movement(m.person, m.from_node, m.to_node, m.from_season, m.to_season, m.age, m.z_from, tuple(50.0 for _ in m.z_to)) if m.to_season == 2023 else m for m in moves]
        clean, dirty = leave_one_season_out(moves, stay)["per_season"][2023], leave_one_season_out(garbage, stay)["per_season"][2023]
        assert dirty["mae_model"] > 10 * clean["mae_model"] and dirty["mean_width"] == pytest.approx(clean["mean_width"])

    def test_it_does_not_depend_on_the_order_of_the_movements(self, synthetic):
        moves, stay = synthetic
        assert rounded(leave_one_season_out(list(reversed(moves)), stay)) == rounded(leave_one_season_out(moves, stay))


class TestWalkForward:
    def test_each_season_is_predicted_with_only_the_seasons_before_it(self, synthetic):
        seen = []

        def spy(moves, stay, **options):
            seen.append(max(m.to_season for m in moves))
            return fit(moves, stay, **options)

        study = walk_forward(*synthetic, first=2023, fit_fn=spy)
        assert sorted(study["per_season"]) == [2023, 2024] and seen == [2022, 2023]

    def test_a_season_with_nothing_before_it_is_not_predicted(self, synthetic):
        assert 2021 not in walk_forward(*synthetic)["per_season"]


class TestTheVerdict:
    def test_a_model_that_does_not_beat_not_translating_is_not_published(self):
        study = {"overall": {"n": 100, "mae_model": 0.7, "mae_identity": 0.6, "mae_rho_only": 0.65, "coverage": 0.8}}
        assert verdict(study) == {"publish": False, "better_than_baselines": False, "calibrated": True, "coverage": 0.8}

    def test_an_interval_that_does_not_hold_its_share_is_not_published_even_if_the_error_is_smaller(self):
        study = {"overall": {"n": 100, "mae_model": 0.5, "mae_identity": 0.7, "mae_rho_only": 0.6, "coverage": 0.65}}
        assert verdict(study)["publish"] is False and verdict(study)["calibrated"] is False

    def test_nothing_to_judge_is_not_published(self):
        assert verdict({"overall": {"n": 0}})["publish"] is False


class TestTheRealRows:
    @pytest.fixture()
    def study(self):
        obs = observations(DATA["rows"], DATA["competitions"])
        return leave_one_season_out(movements(obs), stayers(obs))

    def test_the_model_beats_not_translating_on_the_real_movements(self, study):
        overall = study["overall"]
        assert overall["n"] > 300 and overall["mae_model"] < overall["mae_identity"] and overall["mae_model"] <= overall["mae_rho_only"] * 1.02

    def test_the_range_is_neither_too_narrow_nor_too_wide(self, study):
        assert 0.7 < study["overall"]["coverage"] < 0.9

    def test_the_pairs_with_enough_movers_without_the_season_are_reported_and_the_rest_are_not_invented(self, study):
        """The sample has 45 persons per pair: with a season out some pairs fall under the 40 persons an edge needs (they are not predicted); the ones that stay are the two biggest."""
        assert {"L.F.-2 <-> LF CHALLENGE (F)", "PRIMERA FEB <-> SEGUNDA FEB (M)"} <= set(study["per_edge"]) and all(v["n"] > 0 for v in study["per_edge"].values())
