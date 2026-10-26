"""The win probability calibrated per family of competitions (issue #567, study of 26/10/2026).

With the parameters of before (``wp_sigma`` 12, ``wp_home_adv`` 4, ``wp_n0`` 120) the model was off in the men's leagues (Primera and Segunda FEB: log loss 0.4433,
up to 3.3 points of gap per decile): their margins spread more and the home court is worth more. The package says the gender of the competition
(``rule_config.gender``, from the catalog of the publisher), so the engine takes the calibration of its family unless the package overrides a parameter.
"""
import pytest

from src.live_core.config import WP_BY_GENDER, RuleConfig

KEYS = ("wp_sigma", "wp_home_adv", "wp_n0")


@pytest.mark.parametrize("gender", ["F", "M"])
def test_a_package_of_a_family_gets_its_calibration(gender):
    config = RuleConfig.from_dict({"gender": gender})
    assert {k: getattr(config, k) for k in KEYS} == WP_BY_GENDER[gender]


def test_what_the_package_says_wins_over_the_calibration_of_its_family():
    config = RuleConfig.from_dict({"gender": "M", "wp_sigma": 11.0})
    assert config.wp_sigma == 11.0 and config.wp_home_adv == WP_BY_GENDER["M"]["wp_home_adv"]


@pytest.mark.parametrize("overrides", [{}, None, {"gender": ""}, {"gender": "X"}])
def test_without_a_known_family_the_parameters_are_the_defaults(overrides):
    config, default = RuleConfig.from_dict(overrides), RuleConfig()
    assert {k: getattr(config, k) for k in KEYS} == {k: getattr(default, k) for k in KEYS}


def test_the_calibration_says_what_the_study_found():
    """Men's margins spread more and the home court is worth more; in both families the pre-game prior weighs more than the factors of the game."""
    men, women = WP_BY_GENDER["M"], WP_BY_GENDER["F"]
    assert men["wp_sigma"] > RuleConfig().wp_sigma and men["wp_home_adv"] >= women["wp_home_adv"]
    assert min(men["wp_n0"], women["wp_n0"]) > RuleConfig().wp_n0
