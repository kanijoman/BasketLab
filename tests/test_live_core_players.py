"""Players on a streak and the rival's key player (issue #244): J1 hot rival, J2 rival dependence, J3 own hot player,
J4 own cold player with a high volume, V1 the rival's key player on the bench.

Streaks read the event log with a player: ``[elapsed, team_id, kind, value, player_id]``.
"""
import json

import pytest

from src.live_core.advice import RULES, AdviceEngine
from src.live_core.config import RULE_IDS, RuleConfig
from src.live_core.windows import player_form
from tests.builders import OWN, RIVAL, snap

STATS0 = {k: 0 for k in ("fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta", "orb", "drb", "tov", "stl", "ast", "blk")}


def player(name, team, pf=0, pts=0, on_court=True, minutes=600, stats=None):
    return {"name": name, "team_id": team, "on_court": on_court, "minutes": minutes, "stint": 0, "pf": pf, "pts": pts,
            "pf_by_period": {}, "stats": {**STATS0, **(stats or {})}}


def basket(team, pid, t, value=2):
    """A made basket as the log has it: the attempt and its points."""
    return [[t, team, "fg3" if value == 3 else "fg2", 1, pid], [t, team, "pts", value, pid]]


def miss(team, pid, t):
    return [[t, team, "fg2", 0, pid]]


def pl_snap(players, log=(), elapsed=400):
    return snap(elapsed=elapsed, players=players, log=[e for group in log for e in group])


def evaluate(players, log=(), elapsed=400, period=1, score=None, eng=None, **kw):
    s = snap(elapsed=elapsed, period=period, players=players, log=[e for group in log for e in group])   # ``log``: groups of entries
    if score:
        s["score"] = score
    return (eng or AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, **kw)).evaluate(s)


def by_id(advices, advice_id):
    return [a for a in advices if a.id == advice_id]


def test_the_rules_are_registered_and_can_be_switched_off():
    for rule_id in ("rival_player_form", "own_player_form", "rival_star_bench"):
        assert rule_id in RULE_IDS and rule_id in [rid for rid, _ in RULES]
    off = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, config=RuleConfig(rules_off=("rival_player_form",)))
    log = [basket(RIVAL, "r1", 300, 3), basket(RIVAL, "r1", 330, 2), basket(RIVAL, "r1", 360, 2)]
    assert not by_id(evaluate({"r1": player("Rita", RIVAL)}, log, eng=off), "rival_hot_run")


# --- the helper: how a player is doing in the last minutes ----------------------------------------------

def test_player_form_counts_points_and_consecutive_makes_inside_the_window():
    log = [e for g in (basket(OWN, "p1", 100, 3), basket(OWN, "p1", 300, 2), miss(OWN, "p1", 320), basket(OWN, "p1", 340, 2),
                       basket(OWN, "p1", 360, 3), basket(RIVAL, "r1", 350, 2)) for e in g]
    form = player_form(log, OWN, "p1", now=380, window_s=180)
    assert form == {"pts": 7, "made_in_row": 2}      # the basket at 100 is out of the window; the miss at 320 breaks the row
    assert player_form(log, OWN, "nobody", 380, 180) == {"pts": 0, "made_in_row": 0}


# --- J1: hot rival ------------------------------------------------------------------------------------

def test_j1_seven_points_in_three_minutes_says_to_double_or_change_the_matchup():
    log = [basket(RIVAL, "r1", 250, 3), basket(RIVAL, "r1", 310, 2), basket(RIVAL, "r1", 380, 2)]
    [alert] = by_id(evaluate({"r1": player("Rita", RIVAL)}, log), "rival_hot_run")
    assert alert.severity == "warning" and alert.category == "rival" and "Rita" in alert.message and "7" in alert.message
    tactic = alert.proposal[0]
    assert tactic["type"] == "tactic" and tactic["player_id"] == "r1" and "Rita" in tactic["message"]


def test_j1_three_baskets_in_a_row_is_a_streak_even_with_fewer_points():
    log = [basket(RIVAL, "r1", 250), basket(RIVAL, "r1", 310), basket(RIVAL, "r1", 380)]
    [alert] = by_id(evaluate({"r1": player("Rita", RIVAL)}, log), "rival_hot_run")
    assert alert.evidence["made_in_row"] == 3 and alert.evidence["pts"] == 6


@pytest.mark.parametrize("log", [
    [basket(RIVAL, "r1", 250, 3), basket(RIVAL, "r1", 380, 2), miss(RIVAL, "r1", 390)],            # 5 points, row broken
    [basket(RIVAL, "r1", 100, 3), basket(RIVAL, "r1", 120, 2), basket(RIVAL, "r1", 380, 2)],         # the 3 are outside the window
])
def test_j1_less_than_seven_points_or_old_ones_is_not_a_streak(log):
    assert not by_id(evaluate({"r1": player("Rita", RIVAL)}, log), "rival_hot_run")


def test_j1_it_is_about_the_rival_and_is_said_once_per_player_and_period():
    log = [basket(OWN, "p1", 250, 3), basket(OWN, "p1", 310, 2), basket(OWN, "p1", 380, 2)]
    assert not by_id(evaluate({"p1": player("Ana", OWN)}, log), "rival_hot_run")
    rival_log = [basket(RIVAL, "r1", 250, 3), basket(RIVAL, "r1", 310, 2), basket(RIVAL, "r1", 380, 2)]
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL)
    assert by_id(evaluate({"r1": player("Rita", RIVAL)}, rival_log, eng=e), "rival_hot_run")
    assert not by_id(evaluate({"r1": player("Rita", RIVAL)}, rival_log, elapsed=410, eng=e), "rival_hot_run")


# --- J2: dependence on one rival player --------------------------------------------------------------------

def test_j2_more_than_forty_percent_of_the_rival_points_with_twelve_or_more_says_to_deny_the_ball():
    players = {"r1": player("Rita", RIVAL, pts=14), "r2": player("Rosa", RIVAL, pts=10)}
    [alert] = by_id(evaluate(players, elapsed=1200, score={OWN: 30, RIVAL: 30}), "rival_dependence")
    assert alert.severity == "info" and alert.category == "rival" and "Rita" in alert.message and "47 %" in alert.message
    assert alert.proposal[0]["type"] == "tactic" and alert.proposal[0]["player_id"] == "r1"


@pytest.mark.parametrize("pts, team", [(11, 24), (12, 31), (10, 20)])
def test_j2_needs_twelve_points_and_more_than_forty_percent(pts, team):
    players = {"r1": player("Rita", RIVAL, pts=pts)}
    assert not by_id(evaluate(players, elapsed=1200, score={OWN: 30, RIVAL: team}), "rival_dependence")


def test_j2_it_is_said_once_per_player_and_half():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL)
    players = {"r1": player("Rita", RIVAL, pts=14)}
    assert by_id(evaluate(players, elapsed=1200, period=2, score={OWN: 30, RIVAL: 30}, eng=e), "rival_dependence")
    assert not by_id(evaluate(players, elapsed=1250, period=2, score={OWN: 30, RIVAL: 30}, eng=e), "rival_dependence")


# --- J3: own player on a streak ----------------------------------------------------------------------------

def test_j3_an_own_player_on_a_streak_is_to_be_looked_for():
    log = [basket(OWN, "p1", 250, 3), basket(OWN, "p1", 310, 2), basket(OWN, "p1", 380, 2)]
    [alert] = by_id(evaluate({"p1": player("Ana", OWN)}, log), "own_hot_player")
    assert alert.severity == "info" and "Ana" in alert.message and alert.proposal[0]["message"].startswith("Buscar a Ana")


def test_j3_the_bench_and_the_rival_do_not_count():
    log = [basket(OWN, "p1", 250, 3), basket(OWN, "p1", 310, 2), basket(OWN, "p1", 380, 2)]
    assert not by_id(evaluate({"p1": player("Ana", OWN, on_court=False)}, log), "own_hot_player")


def test_j3_the_streak_also_defers_the_fatigue_warning_of_that_player():
    """Seven points in three minutes count as a streak for R5 as well, not only three baskets in a row."""
    from live_helpers import TABLE, snap as roster_snap

    cfg = RuleConfig(fatigue_alert_index=10, fatigue_warning_index=20, fatigue_critical_index=30)
    s = roster_snap(period=1, elapsed=580, overrides={"g1": {"stint": 560, "minutes": 560}})
    s["log"] = [e for g in (basket("T1", "g1", 400, 3), basket("T1", "g1", 450, 2), [[500, "T1", "fg2", 0, "g1"]],
                            basket("T1", "g1", 540, 2)) for e in g]          # 7 points, no three in a row
    [alert] = by_id(AdviceEngine(own_team_id="T1", rival_team_id="T2", baselines=TABLE, config=cfg).evaluate(s), "fatigue_high")
    assert alert.severity == "warning" and "está en racha" in alert.message


# --- J4: own player cold with a high volume ---------------------------------------------------------------------

USUAL = {"p1": {"rates": {"fg2a40": 4.0, "fg3a40": 2.0}, "avg_min": 1200, "z": {}}}


def test_j4_a_cold_player_shooting_more_than_usual_says_to_change_his_role_or_look_for_another_shooter():
    stats = {"fg2a": 5, "fg2m": 1, "fg3a": 3, "fg3m": 0}          # 1/8 with 6 expected per 40: 600 s -> 1.5 expected
    [alert] = by_id(evaluate({"p1": player("Ana", OWN, stats=stats)}, baselines=USUAL), "own_cold_player")
    assert alert.severity == "info" and "Ana" in alert.message and "1/8" in alert.message
    assert alert.proposal[0]["type"] == "tactic" and "otro tirador" in alert.proposal[0]["message"]


@pytest.mark.parametrize("stats, minutes", [
    ({"fg2a": 5, "fg2m": 3, "fg3a": 3, "fg3m": 1}, 600),     # shooting well
    ({"fg2a": 3, "fg2m": 0, "fg3a": 2, "fg3m": 0}, 600),     # cold but only five attempts
    ({"fg2a": 5, "fg2m": 1, "fg3a": 3, "fg3m": 0}, 2300),    # cold, but eight attempts in 38 minutes is his usual volume
])
def test_j4_it_needs_a_cold_player_with_volume_above_his_usual(stats, minutes):
    assert not by_id(evaluate({"p1": player("Ana", OWN, stats=stats, minutes=minutes)}, baselines=USUAL), "own_cold_player")


def test_j4_without_a_baseline_it_says_nothing_and_is_said_once_per_player_and_period():
    stats = {"fg2a": 5, "fg2m": 1, "fg3a": 3, "fg3m": 0}
    assert not by_id(evaluate({"p1": player("Ana", OWN, stats=stats)}), "own_cold_player")
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, baselines=USUAL)
    assert by_id(evaluate({"p1": player("Ana", OWN, stats=stats)}, eng=e), "own_cold_player")
    assert not by_id(evaluate({"p1": player("Ana", OWN, stats=stats)}, elapsed=420, eng=e), "own_cold_player")


# --- V1: the rival's key player on the bench -------------------------------------------------------------------------

def impact(pts):
    return {"pts": pts, "orb": 1.5, "stl": 1.4, "ast": 3.5, "fg3m": 1.7, "fta": 3.5}   # the six metrics of the package


RIVAL_TABLE = {"r1": {"name": "Rita", "avg_min": 1500, "impact40": impact(24.0)},
               "r2": {"name": "Rosa", "avg_min": 1200, "impact40": impact(8.0)}}


def star_engine():
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, rival_baselines=RIVAL_TABLE)


def test_v1_when_the_key_rival_sits_it_is_the_moment_to_press_and_nothing_is_said_before():
    e = star_engine()
    on = {"r1": player("Rita", RIVAL), "r2": player("Rosa", RIVAL)}
    assert not by_id(evaluate(on, elapsed=300, eng=e), "rival_star_out")
    off = {"r1": player("Rita", RIVAL, on_court=False), "r2": player("Rosa", RIVAL)}
    [alert] = by_id(evaluate(off, elapsed=330, eng=e), "rival_star_out")
    assert alert.severity == "info" and alert.category == "rival" and "Rita" in alert.message and "apretar" in alert.proposal[0]["message"].lower()
    assert not by_id(evaluate(off, elapsed=360, eng=e), "rival_star_out")


def test_v1_the_key_player_is_the_one_with_most_production_not_the_one_with_most_minutes():
    e = star_engine()
    evaluate({"r1": player("Rita", RIVAL), "r2": player("Rosa", RIVAL)}, elapsed=300, eng=e)
    out = evaluate({"r1": player("Rita", RIVAL), "r2": player("Rosa", RIVAL, on_court=False)}, elapsed=330, eng=e)
    assert not by_id(out, "rival_star_out")


def test_v1_if_he_comes_back_with_fouls_it_says_to_attack_him_and_each_exit_is_a_new_alert():
    e = star_engine()
    evaluate({"r1": player("Rita", RIVAL)}, elapsed=300, eng=e)
    first = by_id(evaluate({"r1": player("Rita", RIVAL, on_court=False)}, elapsed=330, eng=e), "rival_star_out")
    clean = evaluate({"r1": player("Rita", RIVAL, pf=2)}, elapsed=400, eng=e)
    assert not by_id(clean, "rival_star_back")
    evaluate({"r1": player("Rita", RIVAL, on_court=False, pf=3)}, elapsed=430, eng=e)
    [back] = by_id(evaluate({"r1": player("Rita", RIVAL, pf=3)}, elapsed=500, eng=e), "rival_star_back")
    assert back.severity == "warning" and "3 faltas" in back.message and back.proposal[0]["player_id"] == "r1"
    again = by_id(evaluate({"r1": player("Rita", RIVAL, on_court=False, pf=3)}, elapsed=560, eng=e), "rival_star_out")
    assert first and again and first[0].key != again[0].key


def test_v1_without_rival_baselines_there_is_no_key_player():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL)
    evaluate({"r1": player("Rita", RIVAL)}, elapsed=300, eng=e)
    assert not by_id(evaluate({"r1": player("Rita", RIVAL, on_court=False)}, elapsed=330, eng=e), "rival_star_out")


def test_the_alerts_are_json_serialisable():
    log = [basket(RIVAL, "r1", 250, 3), basket(RIVAL, "r1", 310, 2), basket(RIVAL, "r1", 380, 2)]
    [alert] = by_id(evaluate({"r1": player("Rita", RIVAL)}, log), "rival_hot_run")
    assert json.loads(json.dumps(alert.proposal)) == alert.proposal
