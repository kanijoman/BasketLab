"""Live win probability (issue #254): final margin ~ Normal(margin now + mu * possessions left / 100, sd * sqrt(time left)).

mu blends the pre-game prior (net rating of the matchup + home court) with what the game shows (the Four Factors'
expected net rating), weighted by the possessions played. P(win) = Phi(mean / sd); a tie splits the overtime 50/50.
"""

import pytest

from src.live_core.config import RuleConfig
from src.live_core.win_prob import WinProbabilityModel

OWN, RIVAL = "1", "2"


def snap(margin=0, elapsed=0, home=None):
    return {"score": {OWN: 50 + margin, RIVAL: 50}, "elapsed": elapsed, "home_id": home}


def ff(net=0.0, poss=0.0, poss_remaining=70.0, reliable=True):
    return {"possessions": poss, "reliable": reliable, "expected_net_rtg": net,
            "projection": {"poss_remaining": poss_remaining}}


def model(baselines=None, **cfg):
    return WinProbabilityModel(OWN, RIVAL, baselines or {}, RuleConfig(**cfg))


def p(m, s, f=None):
    return m.evaluate(s, f)["p"]


def test_even_matchup_at_tip_off_is_a_coin_flip():
    assert p(model(), snap(), ff()) == pytest.approx(0.5)


def test_grows_with_the_margin():
    m = model()
    values = [p(m, snap(margin, 1200), ff(poss_remaining=35)) for margin in (-10, -3, 0, 3, 10)]
    assert values == sorted(values) and values[0] < 0.5 < values[-1]


def test_a_lead_is_worth_more_the_less_time_is_left():
    m = model()
    early = p(m, snap(5, 600), ff(poss_remaining=52))
    late = p(m, snap(5, 2100), ff(poss_remaining=9))
    assert late > early


def test_certain_at_the_final_buzzer_and_tie_splits_overtime():
    m = model()
    assert p(m, snap(1, 2400), ff(poss_remaining=0)) == 1.0
    assert p(m, snap(-1, 2400), ff(poss_remaining=0)) == 0.0
    assert p(m, snap(0, 2400), ff(poss_remaining=0)) == 0.5


def test_swapping_the_teams_gives_the_complement():
    own_view = WinProbabilityModel(OWN, RIVAL, {"net_rtg_prior": 4.0}, RuleConfig())
    rival_view = WinProbabilityModel(RIVAL, OWN, {"net_rtg_prior": -4.0}, RuleConfig())
    s = snap(3, 900)
    a = own_view.evaluate(s, ff(net=2.0, poss=30, poss_remaining=45))["p"]
    b = rival_view.evaluate(s, ff(net=-2.0, poss=30, poss_remaining=45))["p"]
    assert a + b == pytest.approx(1.0, abs=1e-6)


def test_the_stronger_team_before_the_game_starts_favourite():
    assert p(model({"net_rtg_prior": 6.0}), snap(), ff()) > 0.5
    assert p(model({"net_rtg_prior": -6.0}), snap(), ff()) < 0.5


def test_what_the_game_shows_takes_over_the_prior_as_possessions_pile_up():
    base = {"net_rtg_prior": 6.0}
    early = p(model(base), snap(0, 300), ff(net=-12.0, poss=10, poss_remaining=62))
    late = p(model(base), snap(0, 300), ff(net=-12.0, poss=120, poss_remaining=62))
    assert late < early < 0.7


def test_home_court_helps_only_the_local_team():
    m = model()
    assert p(m, snap(home=OWN), ff()) > 0.5 > p(m, snap(home=RIVAL), ff())
    assert p(m, snap(home=None), ff()) == pytest.approx(0.5)


def test_without_four_factors_it_still_answers_from_the_prior_and_the_expected_pace():
    result = model({"net_rtg_prior": 5.0, "pace_per_40": 80.0}).evaluate(snap(0, 1200), None)
    assert result["p"] > 0.5
    assert result["poss_remaining"] == pytest.approx(40.0)
    assert result["reliable"] is False


def test_output_fields_and_projected_margin():
    result = model({"net_rtg_prior": 10.0}).evaluate(snap(4, 1200), ff(poss_remaining=40))
    assert set(result) == {"p", "projected_margin", "sd", "poss_remaining", "mu_per_100", "reliable"}
    assert result["mu_per_100"] == pytest.approx(10.0)  # no possessions played: only the prior
    assert result["projected_margin"] == pytest.approx(4 + 10.0 * 40 / 100)
    assert result["reliable"] is True


def test_reliable_follows_the_four_factors():
    assert model().evaluate(snap(0, 600), ff(reliable=False))["reliable"] is False


def test_sd_shrinks_with_the_time_left_and_is_configurable():
    m = model(wp_sigma=12.0)
    assert m.evaluate(snap(0, 0), ff())["sd"] == pytest.approx(12.0)
    assert m.evaluate(snap(0, 1800), ff())["sd"] == pytest.approx(12.0 * 0.25 ** 0.5)


def test_probability_never_leaves_the_open_unit_interval_before_the_end():
    m = model()
    assert 0.0 < p(m, snap(40, 600), ff(poss_remaining=60)) <= 1.0
    assert 0.0 <= p(m, snap(-40, 600), ff(poss_remaining=60)) < 1.0


def test_the_advice_engine_publishes_it_in_the_analysis(feb_game_doc):
    """The analysis the UI reads carries ``win_prob`` next to the Four Factors, and a better start means a higher figure."""
    from src.live_core.advice import AdviceEngine
    from src.live_core.engine import LiveEngine

    snapshot = LiveEngine().update(feb_game_doc)
    ids = list(snapshot["teams"])
    analysis = AdviceEngine(own_team_id=ids[0], rival_team_id=ids[1]).analyze(snapshot)
    wp = analysis["win_prob"]
    assert 0.0 <= wp["p"] <= 1.0
    margin = snapshot["score"][ids[0]] - snapshot["score"][ids[1]]
    assert (wp["p"] > 0.5) == (margin > 0) or margin == 0
