"""Who gets the ball against a rival in foul trouble (#698, feedback 0.5.0, game 2524489).

"Balón a F. DEMBELE" ignored his free-throw percentage: a player who draws many fouls but shoots badly from the line is no use there, and neither is a
great shooter who does not draw fouls. The player must do both: draw contact (free-throw rate) and convert (free-throw percentage).
"""
from tests.builders import OWN, RIVAL, _player, engine, snap


def _base(ftr_z, ft_pct):
    return {"z": {"ftr": ftr_z}, "ft_pct": ft_pct, "avg_min": 1500}


def _proposal(own_baselines):
    players = {"r1": _player("Rival Uno", RIVAL, pf=2), **{pid: _player(pid.upper(), OWN) for pid in own_baselines}}
    out = engine(baselines=own_baselines).evaluate(snap(period=1, players=players))
    [advice] = [a for a in out if a.id == "rival_foul_trouble"]
    return [p["message"] for p in advice.proposal]


def test_a_player_who_draws_fouls_but_shoots_badly_from_the_line_does_not_get_the_ball_regression():
    [text] = _proposal({"dembele": _base(2.0, 0.55)})
    assert "DEMBELE" not in text and "Atacar el aro" in text


def test_a_great_shooter_who_does_not_draw_fouls_does_not_get_the_ball():
    [text] = _proposal({"shooter": _base(0.0, 0.90)})
    assert "SHOOTER" not in text and "Atacar el aro" in text


def test_the_one_who_draws_fouls_and_converts_gets_it_over_the_one_who_only_draws_them():
    [text] = _proposal({"bad": _base(2.5, 0.55), "good": _base(1.0, 0.82)})
    assert "GOOD" in text and "BAD" not in text


def test_between_two_who_do_both_the_best_combination_wins_and_the_percentage_is_said():
    [text] = _proposal({"a": _base(1.0, 0.70), "b": _base(1.4, 0.80)})
    assert "B" in text.split("Balón a ")[1][:3] and "80 %" in text


def test_a_package_without_free_throw_percentages_keeps_the_old_choice_by_contact():
    baselines = {"old": {"z": {"ftr": 1.2}, "avg_min": 1500}}
    [text] = _proposal(baselines)
    assert "OLD" in text and "%" not in text
