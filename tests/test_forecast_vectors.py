"""The models of the browser forecast are the ones of the live engine (#846): the Bayesian rating, the win probability at tip-off and the four factors.

``frontend/src/forecast`` ports them to TypeScript and must answer every case of ``tests/local_vectors/forecast.json``, which is made by calling the real Python code over the real rows of the fixture
leagues. ``python tests/local_vectors/generate.py`` regenerates the file: any change in the Python side shows up as a diff here and as a failure of the vitest suite until the port follows.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import forecast_vectors  # noqa: E402
import generate  # noqa: E402

from src.live_core.config import WP_BY_GENDER  # noqa: E402


def _stored():
    return json.loads(generate.FORECAST_OUT.read_text(encoding="utf-8"))


def test_the_stored_vectors_are_the_current_reference():
    assert json.loads(json.dumps(forecast_vectors.build(), sort_keys=True)) == json.loads(json.dumps(_stored(), sort_keys=True))


def test_the_win_probability_constants_are_the_calibrated_ones_and_an_unknown_gender_has_the_neutral_defaults():
    constants = _stored()["constants"]["win_prob"]
    assert constants["F"] == {"sigma": WP_BY_GENDER["F"]["wp_sigma"], "home_adv": WP_BY_GENDER["F"]["wp_home_adv"]}
    assert constants["M"] == {"sigma": WP_BY_GENDER["M"]["wp_sigma"], "home_adv": WP_BY_GENDER["M"]["wp_home_adv"]}
    assert constants["default"] == {"sigma": 12.0, "home_adv": 4.0}


def test_both_leagues_and_every_kind_of_headline_are_covered():
    competitions = _stored()["competitions"]
    assert [c["league"] for c in competitions] == ["feb", "fbcyl"]
    for competition in competitions:
        cases = competition["headline"]
        assert {(c["gender"], c["court"]) for c in cases} == {(g, k) for g in ("F", "M", "") for k in ("own", "rival", "neutral")}
        assert 0.0 in {c["pace"] for c in cases} and any(c["own"] == "999" for c in cases)                 # no pace known, and a team never seen
        assert all(0.0 < c["p"] < 1.0 for c in cases)


def test_a_neutral_court_is_a_pure_rating_matchup_and_the_home_court_moves_the_probability_by_the_family_value():
    cases = _stored()["competitions"][0]["headline"]
    home = {(c["own"], c["rival"], c["gender"], c["pace"], c["court"]): c for c in cases}
    key = next(k for k in home if k[4] == "neutral" and k[2] == "F" and k[3] == 70.0)
    neutral, own, rival = (home[(*key[:4], court)] for court in ("neutral", "own", "rival"))
    assert own["p"] > neutral["p"] > rival["p"] and abs((own["projected_margin"] - neutral["projected_margin"]) - 5.0 * 70.0 / 100) < 0.01


def test_the_rating_sequences_are_the_ones_of_the_real_games_and_the_variance_of_a_team_falls_with_its_games():
    for competition in _stored()["competitions"]:
        steps = competition["ratings"]["steps"]
        assert len(steps) == 12
        assert any(s["margin"] == 0 for s in steps) == (competition["league"] == "fbcyl")        # a game of FBCYL ended tied: the update must handle it
        first = steps[0]["after"][steps[0]["home"]]["var"]
        assert first < 60.0 and steps[-1]["after"][steps[0]["home"]]["var"] < first


def test_the_factor_cases_are_the_real_rows_and_their_levels_cover_every_team():
    for competition in _stored()["competitions"]:
        cases, levels = competition["factors"], competition["levels"]
        assert len(cases) == 24 and all({"row", "own", "opp", "factors", "per_unit"} <= set(c) for c in cases)
        assert set(levels["teams"]) == {str(c["row"]["team_id"]) for c in cases} and all(t["games"] == 6 for t in levels["teams"].values())
