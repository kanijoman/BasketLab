"""Live win probability (issue #254): final margin ~ Normal(margin now + mu * possessions left / 100, sd * sqrt(time left)).

mu blends the pre-game prior (net rating of the matchup + home court) with what the game shows (the Four Factors'
expected net rating), weighted by the possessions played. P(win) = Phi(mean / sd); a tie splits the overtime 50/50.
"""

import pytest

from src.live_core.config import RuleConfig
from src.live_core.win_prob import WinProbabilityModel, phi

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


# -- levers (issue #256): how much the probability moves if the team gets back to its usual level -----------------

LEVER_STATS = dict(fg2m=20, fg2a=40, fg3m=6, fg3a=20, ftm=10, fta=14, orb=8, drb=25, tov=10, tov_team=0, stl=5, ast=12, blk=2, pts=0)


def lever_snap(margin=0, elapsed=1200):
    s = snap(margin, elapsed)
    s["teams"] = {OWN: {"stats": dict(LEVER_STATS)}, RIVAL: {"stats": dict(LEVER_STATS)}}
    return s


def lever_ff(shrunk=None, prior=None, poss_remaining=40.0, reliable=True):
    zero = {"efg": 0.0, "tov": 0.0, "orb": 0.0, "ftr": 0.0}
    return {**ff(poss=40.0, poss_remaining=poss_remaining, reliable=reliable), "shrunk": {**zero, **(shrunk or {})}}


def levers(margin=0, shrunk=None, prior=None, ff_over=None, **cfg):
    m = model({"four_factors_prior": prior or {}}, **cfg)
    s = lever_snap(margin)
    return m.levers(s, {**lever_ff(shrunk), **(ff_over or {})})


def by_id(rows):
    return {r["id"]: r for r in rows}


def test_a_factor_below_its_usual_level_is_a_lever_worth_its_gain_in_probability():
    from src.live_core.four_factors import points_per_unit

    rows = by_id(levers(margin=-4, shrunk={"efg": -0.05}, prior={"efg": 0.0}))
    assert "efg" in rows and rows["efg"]["gain"] > 0
    extra = points_per_unit(LEVER_STATS)["efg"] * 0.05 * 40 / 100        # points over what is left of the game
    m = model()
    base = m.evaluate(lever_snap(-4), lever_ff())
    expected = phi((-4 + extra) / base["sd"]) - base["p"]
    assert rows["efg"]["gain"] == pytest.approx(expected, abs=1e-3)
    assert rows["efg"]["gain_pts"] == pytest.approx(extra, abs=0.01)


def test_a_factor_at_or_above_its_usual_level_is_not_a_lever():
    rows = by_id(levers(margin=-4, shrunk={"efg": 0.03, "tov": 0.0}, prior={"efg": 0.0, "tov": 0.0}))
    assert "efg" not in rows and "tov" not in rows


def test_the_usual_level_is_the_prior_of_the_package():
    # shrunk 0.0 is below a prior of +0.04: back to usual means improving
    assert "orb" in by_id(levers(margin=-4, shrunk={"orb": 0.0}, prior={"orb": 0.04}))


def test_levers_come_ordered_by_gain_and_small_ones_are_dropped():
    rows = levers(margin=-4, shrunk={"efg": -0.08, "tov": -0.03, "ftr": -0.0001})
    gains = [r["gain"] for r in rows if r["id"] != "pace"]
    assert gains == sorted(gains, reverse=True) and "ftr" not in by_id(rows)
    assert all(r["gain"] >= RuleConfig().wp_lever_min_gain for r in rows)


def test_no_levers_without_a_reliable_game_or_four_factors():
    assert levers(margin=-4, shrunk={"efg": -0.08}, ff_over={"reliable": False}) == []
    assert model().levers(lever_snap(-4), None) == []


def test_trailing_team_gains_from_a_faster_game_and_the_leader_from_a_slower_one():
    behind = by_id(levers(margin=-6))["pace"]
    ahead = by_id(levers(margin=6))["pace"]
    assert behind["direction"] == "up" and ahead["direction"] == "down"
    assert behind["gain"] > 0 and ahead["gain"] > 0
    assert "pace" not in by_id(levers(margin=0))


def test_a_decided_game_has_no_pace_lever():
    assert "pace" not in by_id(levers(margin=40))


def test_lever_gain_by_id_for_the_alerts():
    gains = model().lever_gains(lever_snap(-4), lever_ff({"efg": -0.05}))
    assert set(gains) >= {"efg"} and gains["efg"] > 0


# -- the pace lever does not contradict the pace the game already has (issue #488, feedback of 0.3.2) -------------------------------------

def paced_snap(margin, recent_fga, before_fga, elapsed=1200):
    """A snapshot whose last 5 minutes have ``recent_fga`` shots per team and the 15 minutes before ``before_fga``."""
    s = lever_snap(margin, elapsed)
    log = []
    for team in (OWN, RIVAL):
        log += [[900 + 300 * i // max(recent_fga, 1), team, "fg2", 0, "p1"] for i in range(recent_fga)]
        log += [[900 * i // max(before_fga, 1), team, "fg2", 0, "p1"] for i in range(before_fga)]
    s["log"] = log
    return s


def paced_levers(margin, recent_fga, before_fga):
    m = model({"four_factors_prior": {}})
    return by_id(m.levers(paced_snap(margin, recent_fga, before_fga), lever_ff()))


def test_a_deficit_that_came_with_a_pace_already_going_up_does_not_ask_to_raise_it_regression():
    """Copa 21/10/2026, end of Q3: «subir el ritmo» during a hard run against that had arrived when the pace rose: the advice contradicts the cause."""
    assert "pace" not in paced_levers(-8, recent_fga=14, before_fga=20)


def test_a_deficit_with_a_pace_that_has_not_risen_still_asks_to_raise_it():
    assert paced_levers(-8, recent_fga=8, before_fga=22)["pace"]["direction"] == "up"


def test_a_lead_that_came_with_a_pace_already_going_down_does_not_ask_to_lower_it():
    assert "pace" not in paced_levers(8, recent_fga=9, before_fga=40)


def test_a_lead_with_a_pace_that_rose_still_asks_to_lower_it():
    assert paced_levers(8, recent_fga=14, before_fga=20)["pace"]["direction"] == "down"


def test_without_a_pace_to_compare_the_lever_is_what_it_was():
    assert by_id(levers(margin=-6))["pace"]["direction"] == "up"
    s = lever_snap(-6)
    s["log"] = [[1190, OWN, "fg2", 0, "p1"]]                                  # too little play to measure a pace
    assert by_id(model().levers(s, lever_ff()))["pace"]["direction"] == "up"


def test_the_margin_of_what_counts_as_a_change_of_pace_is_in_the_configuration():
    m = model({"four_factors_prior": {}}, wp_pace_recent_delta=500.0)
    assert by_id(m.levers(paced_snap(-8, 14, 20), lever_ff()))["pace"]["direction"] == "up"
