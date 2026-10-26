"""The levers say whether the problem is the attack or the defence (issue #586, decision of the user on the study of #567).

«¿Atacan bien? ¿Hay que mejorar la defensa?» It is a DIAGNOSIS of what the game shows, not a forecast (the study found that the factors of the game do not predict the next minutes): each
factor is compared with what is usual for THIS matchup, which the package knows (``baselines.team_levels``: how each team attacks and defends in the season, and the league):
we are expected to make what we usually make plus what the rival usually lets, and the rival what it usually makes plus what we usually let.
"""
import pytest

from src.live_core.four_factors import lever_sides
from tests.builders import OWN, RIVAL, _stats, engine, ff_snap

LEAGUE = {"efg": 0.50, "tov": 0.15, "orb": 0.30, "ftr": 0.30}


def levels(own_attack=None, own_defence=None, rival_attack=None, rival_defence=None):
    mk = lambda over: {**LEAGUE, **(over or {})}  # noqa: E731
    return {"league": LEAGUE, "own": {"attack": mk(own_attack), "defence": mk(own_defence)}, "rival": {"attack": mk(rival_attack), "defence": mk(rival_defence)},
            "games": {"own": 10, "rival": 10}}


PER_UNIT = {"efg": 100.0, "tov": 100.0, "orb": 50.0, "ftr": 20.0}


def test_a_rival_that_shoots_far_above_what_it_usually_does_against_us_is_the_defence():
    sides = lever_sides(levels(), {"efg": 0.50, "tov": 0.15, "orb": 0.30, "ftr": 0.30}, {"efg": 0.65, "tov": 0.15, "orb": 0.30, "ftr": 0.30}, PER_UNIT)
    assert sides["efg"]["attack"] == pytest.approx(0.0, abs=1e-9)
    assert sides["efg"]["defence"] == pytest.approx(-15.0)                     # (0.50 expected - 0.65) * 100 points per 100 possessions


def test_our_own_shooting_below_what_we_usually_do_is_the_attack():
    sides = lever_sides(levels(), {"efg": 0.42, "tov": 0.15, "orb": 0.30, "ftr": 0.30}, {"efg": 0.50, "tov": 0.15, "orb": 0.30, "ftr": 0.30}, PER_UNIT)
    assert sides["efg"]["attack"] == pytest.approx(-8.0) and sides["efg"]["defence"] == pytest.approx(0.0, abs=1e-9)


def test_the_expectation_is_of_the_matchup_not_of_the_league():
    """A rival that always shoots 55 % against a defence that lets 55 % is not «bad defence» when it shoots 56 %: the expectation is 60 %."""
    sides = lever_sides(levels(own_defence={"efg": 0.55}, rival_attack={"efg": 0.55}), {"efg": 0.50, "tov": 0.15, "orb": 0.30, "ftr": 0.30},
                        {"efg": 0.56, "tov": 0.15, "orb": 0.30, "ftr": 0.30}, PER_UNIT)
    assert sides["efg"]["defence"] > 0                                          # expected 0.55 + 0.55 - 0.50 = 0.60: the defence holds the rival below it


def test_turnovers_are_inverted_a_rival_that_loses_fewer_balls_than_usual_is_a_defence_problem():
    sides = lever_sides(levels(), {"efg": 0.50, "tov": 0.15, "orb": 0.30, "ftr": 0.30}, {"efg": 0.50, "tov": 0.08, "orb": 0.30, "ftr": 0.30}, PER_UNIT)
    assert sides["tov"]["defence"] == pytest.approx(-7.0) and sides["tov"]["attack"] == pytest.approx(0.0, abs=1e-9)
    ours = lever_sides(levels(), {"efg": 0.50, "tov": 0.22, "orb": 0.30, "ftr": 0.30}, {"efg": 0.50, "tov": 0.15, "orb": 0.30, "ftr": 0.30}, PER_UNIT)
    assert ours["tov"]["attack"] == pytest.approx(-7.0)                         # we lose more balls than usual: it is on our side


def test_without_the_levels_of_a_team_there_is_no_diagnosis():
    assert lever_sides({}, LEAGUE, LEAGUE, PER_UNIT) is None
    partial = levels()
    del partial["rival"]
    assert lever_sides(partial, LEAGUE, LEAGUE, PER_UNIT) is None


# --- the alert ----------------------------------------------------------------------------------------------------------------------------------

def lever_alert(game_levels, own, rival):
    out = engine(team_baselines={"team_levels": game_levels}).evaluate(ff_snap(_stats(**own), _stats(**rival)))
    return next(a for a in out if a.id == "four_factors_lever")


def test_the_alert_says_it_is_mostly_the_defence_when_the_rival_shoots_far_above_its_usual():
    # the rival makes 30 of 50 from two and 10 of 30 from three (a high effective percentage) in a game where the usual of the matchup is the league's
    alert = lever_alert(levels(), {}, dict(fg2m=40, fg2a=60, fg3m=14, fg3a=30))
    assert alert.evidence["lever"] == "efg" and alert.evidence["side"] == "defence"
    assert "Es sobre todo la defensa" in alert.message and "el rival acierta" in alert.message


def test_the_alert_says_it_is_mostly_the_attack_when_we_shoot_far_below_our_usual():
    alert = lever_alert(levels(own_attack={"efg": 0.60}), dict(fg2m=12, fg2a=40, fg3m=2, fg3a=20), {})
    assert alert.evidence["lever"] == "efg" and alert.evidence["side"] == "attack"
    assert "Es sobre todo el ataque" in alert.message


def test_without_the_levels_the_alert_is_what_it_was_with_no_side():
    alert = lever_alert(None, {}, dict(fg2m=40, fg2a=60, fg3m=14, fg3a=30))
    assert "side" not in alert.evidence and "Es sobre todo" not in alert.message


def test_the_lever_rows_of_the_analysis_carry_the_side_too_and_only_with_the_levels():
    """The card of the app reads it from ``analysis.win_levers`` (the same diagnosis as the alert)."""
    s = ff_snap(_stats(tov=22), _stats())
    s["score"] = {OWN: 36, RIVAL: 40}
    with_levels = {lv["id"]: lv for lv in engine(team_baselines={"team_levels": levels()}).analyze(s)["win_levers"]}
    assert with_levels["tov"]["side"] == "attack"                              # we lose 22 balls: it is our attack
    assert "side" not in {lv["id"]: lv for lv in engine().analyze(s)["win_levers"]}["tov"]
