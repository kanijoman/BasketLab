"""The summary of a quarter, reviewed with the Copa match Cultural - Oviedo (feedback of 0.3.2, issues #485, #486, #487).

* #486: every summary says the score of the game, the partial of the period and its difference (it used to show only the partial of the window).
* #487: «Faltas de equipo: 7» said neither whose they were nor what they meant: now own vs rival, the free throws they gave and the players in trouble.
* #485: «Final 1C: +8 y ritmo» described the result but did not explain it: the keys look for the factor (shooting, turnovers, free throws) that is out
  of range against what is usual for both teams and justifies the lead or the deficit.
"""
from src.live_core.advice import AdviceEngine
from tests.builders import OWN, RIVAL
from tests.test_live_core_closing import by_id, end_of, flat, player, pts
from tests.test_live_core_summary_scope import STARTS, attempts


def summary(period, log, players=None, fouls=None, **kw):
    engine = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, **kw)
    entries = log if log and isinstance(log[0][0], (int, float)) else flat(*log)      # a flat list of entries, or a list of groups
    snapshot = end_of(period, [entries], players=players)
    for team, by_period in (fouls or {}).items():
        snapshot["teams"][team]["fouls_by_period"] = by_period
    [alert] = by_id(engine.evaluate(snapshot), "period_summary")
    return alert


# --- #486 the score, the partial and the difference ---------------------------------------------------------------------------------------

def test_the_first_quarter_says_the_score_and_the_partial_of_the_quarter():
    log = [pts(OWN, 100, 3), pts(OWN, 200), pts(RIVAL, 300), pts(OWN, 400)]            # 6-2
    alert = summary(1, log)
    assert alert.message.startswith("Fin del 1.er cuarto: marcador 7-2 (+5); 1.er cuarto 7-2 (+5).")
    assert alert.evidence["score"] == {"own": 7, "rival": 2} and alert.evidence["period_points"] == {"own": 7, "rival": 2}


def test_the_third_quarter_says_the_game_score_and_its_own_partial_apart_regression():
    """Found with the Copa (21/10/2026): the header said the partial of the quarter as if it were the score."""
    log = [pts(OWN, 100, 3), pts(RIVAL, 300, 3), pts(RIVAL, 700, 2), pts(OWN, 900, 3), pts(OWN, 1300, 2), pts(RIVAL, 1500, 3)]
    alert = summary(3, log)
    assert "marcador 8-8 (+0)" in alert.message and "3.er cuarto 2-3 (-1)" in alert.message
    assert alert.evidence["score"] == {"own": 8, "rival": 8} and alert.evidence["period_points"] == {"own": 2, "rival": 3}


def test_halftime_says_the_score_the_first_half_and_the_second_quarter():
    log = [pts(OWN, 100, 3), pts(RIVAL, 300), pts(OWN, 700, 3), pts(RIVAL, 900, 3)]
    alert = summary(2, log)
    assert alert.message.startswith("Descanso: marcador 6-5 (+1); 1.ª parte 6-5 (+1); 2.º cuarto 3-3 (+0).")
    assert alert.evidence["half_points"] == {"own": 6, "rival": 5} and alert.evidence["period_points"] == {"own": 3, "rival": 3}


def test_points_after_the_end_of_the_period_are_not_in_its_summary_when_the_poll_is_late():
    """The summary also comes in the first minute of the next period if the poll missed the 0:00: those points are not the quarter's."""
    engine = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL)
    snapshot = end_of(2, [pts(OWN, 100, 3), pts(RIVAL, 590, 2), pts(OWN, 615, 3)], remaining=570)       # a 3 already in the 2nd quarter
    [alert] = by_id(engine.evaluate(snapshot), "period_summary")
    assert alert.key == "summary:1" and alert.evidence["score"] == {"own": 3, "rival": 2}


# --- #487 the team fouls ------------------------------------------------------------------------------------------------------------------

def foul_log():
    rival_ft = [[100 + 10 * i, RIVAL, "ft", 1, "r1"] for i in range(9)]                 # 9 free throws of the rival (the fouls we made)
    return rival_ft + pts(OWN, 50) + pts(RIVAL, 200)


def test_the_team_fouls_say_whose_they_are_and_the_free_throws_they_gave():
    alert = summary(1, foul_log(), fouls={OWN: {"1": 7}, RIVAL: {"1": 4}})
    assert "Faltas propias: 7 (el rival lanzó 9 tiros libres) frente a 4 del rival" in alert.message
    assert "Faltas de equipo: 7" not in alert.message


def test_the_players_in_foul_trouble_are_named():
    players = {"p1": player("Ana", OWN, pf=3), "p2": player("Bea", OWN, pf=2), "p3": player("Cora", OWN, pf=1), "r1": player("Rita", RIVAL, pf=3)}
    alert = summary(1, foul_log(), players=players, fouls={OWN: {"1": 7}, RIVAL: {"1": 4}})
    assert "con problemas: Ana (3), Bea (2)" in alert.message and "Cora" not in alert.message and "Rita" not in alert.message
    assert alert.evidence["foul_trouble"] == [{"name": "Ana", "pf": 3}, {"name": "Bea", "pf": 2}]
    assert any("Ana" in p["message"] or "rotar" in p["message"].lower() for p in alert.proposal)


def test_the_fouls_key_still_needs_the_threshold_of_team_fouls():
    assert "Faltas propias" not in summary(1, foul_log(), fouls={OWN: {"1": 4}, RIVAL: {"1": 8}}).message


def test_halftime_counts_the_fouls_of_both_quarters_of_the_half():
    alert = summary(2, foul_log(), fouls={OWN: {"1": 3, "2": 4}, RIVAL: {"1": 2, "2": 2}})
    assert "Faltas propias: 7" in alert.message and "frente a 4 del rival" in alert.message


# --- #485 the keys explain the lead --------------------------------------------------------------------------------------------------------

def points(team, start, n, step=10):
    """``n`` scores of 2 points of ``team`` with no shot attached (the shots of the quarter are the ``shots`` ones), as flat log entries."""
    return [[start + step * i, team, "pts", 2, "p1"] for i in range(n)]


def shots(team, period, made, missed, kind="fg2"):
    t0 = STARTS[period] + 20
    return [[t0 + i, team, kind, 1, "p1"] for i in range(made)] + [[t0 + 100 + i, team, kind, 0, "p1"] for i in range(missed)]


def cause(period, log, **kw):
    alert = summary(period, log, **kw)
    return alert, [k for k in alert.evidence["keys"] if k == "cause"]


def test_a_lead_explained_by_shooting_says_the_shooting_of_both_teams():
    log = flat(shots(OWN, 1, 12, 4), shots(RIVAL, 1, 6, 10), points(OWN, 30, 12), points(RIVAL, 40, 4))
    alert, found = cause(1, log)
    assert found == ["cause"]
    assert "Ventaja por el tiro: 75 % de campo vs 38 % del rival" in alert.message
    assert any("tiro" in p["message"].lower() for p in alert.proposal)


def test_a_lead_explained_by_turnovers_says_them():
    log = flat(shots(OWN, 1, 7, 7), shots(RIVAL, 1, 7, 7), [[200 + i, RIVAL, "tov", 1, "r1"] for i in range(9)], [[300 + i, OWN, "tov", 1, "p1"] for i in range(2)],
               points(OWN, 30, 10), points(RIVAL, 40, 3))
    alert, found = cause(1, log)
    assert found == ["cause"] and "pérdidas del rival: 9 vs 2" in alert.message.lower()


def test_a_deficit_explained_by_own_shooting_says_it():
    log = flat(shots(OWN, 1, 4, 12), shots(RIVAL, 1, 12, 4), points(OWN, 30, 3), points(RIVAL, 40, 12))
    alert, found = cause(1, log)
    assert found == ["cause"] and "Desventaja por el tiro" in alert.message


def test_a_lead_with_nothing_out_of_range_says_there_is_no_clear_cause():
    log = flat(shots(OWN, 1, 8, 8), shots(RIVAL, 1, 8, 8), points(OWN, 30, 9), points(RIVAL, 40, 2))
    alert, found = cause(1, log)
    assert "no_cause" in alert.evidence["keys"] and "sin causa clara" in alert.message.lower()


def test_a_quiet_quarter_has_no_cause_to_explain():
    log = [pts(OWN, 100), pts(RIVAL, 200), pts(OWN, 300), pts(RIVAL, 400)]
    assert cause(1, log)[1] == []


def test_what_is_usual_for_the_teams_moves_what_is_out_of_range():
    """The package's prior: our shooting is usually +30 points over this rival's, so a +37 gap is not out of range; against equals it is."""
    log = flat(shots(OWN, 1, 12, 4), shots(RIVAL, 1, 6, 10), points(OWN, 30, 12), points(RIVAL, 40, 4))
    usual = {"four_factors_prior": {"efg": 0.30, "tov": 0.0, "orb": 0.0, "ftr": 0.0}}
    assert "Ventaja por el tiro" in summary(1, log).message
    assert "Ventaja por el tiro" not in summary(1, log, team_baselines=usual).message
    assert "sin causa clara" in summary(1, log, team_baselines=usual).message.lower()


def test_the_cause_comes_before_the_period_net_and_the_keys_stay_at_three():
    log = flat(shots(OWN, 1, 12, 4), shots(RIVAL, 1, 6, 10), points(OWN, 30, 12), points(RIVAL, 40, 4))
    keys = summary(1, log).evidence["keys"]
    assert keys.index("cause") < keys.index("period_net") and len(keys) <= 3


def test_no_clear_cause_is_the_last_thing_said_not_the_first():
    """«Sin causa clara» has less to tell than a measured pace or a collapse: it goes after them."""
    log = flat(shots(OWN, 1, 8, 8), shots(RIVAL, 1, 8, 8), points(OWN, 30, 9), points(RIVAL, 40, 2))
    keys = summary(1, log).evidence["keys"]
    assert "no_cause" in keys and "cause" not in keys
