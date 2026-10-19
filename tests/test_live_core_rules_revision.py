"""Revision of the existing rules (issue #241): R4 fouls by risk, F3 bonus by time left, R8 rival fouls with a concrete tactic,
R1 rival run by levels, R3 turnovers with a timeout, R5 escalated fatigue, R6 lever only when it changes or worsens.

After this change no revised rule repeats by ``rearm_s``: each says a new thing (a new key) or nothing.
"""
import copy

import pytest

from live_helpers import TABLE, z
from src.live_core.advice import AdviceEngine
from src.live_core.config import RuleConfig
from tests.test_live_core_advice import OWN, RIVAL, _player, ff_snap, snap

MIN = 60


def engine(**kw):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, **kw)


def by_id(advices, advice_id):
    return [a for a in advices if a.id == advice_id]


def foul_snap(pf, period, remaining, pid="p1"):
    s = snap(period=period, elapsed=(period - 1) * 600 + (600 - remaining), players={pid: _player("Ana", OWN, pf=pf)})
    s["remaining"] = remaining
    return s


# --- R4: own fouls by risk of elimination -------------------------------------------------

@pytest.mark.parametrize("period", [1, 2, 3, 4])
def test_r4_two_fouls_never_raise_an_alert(period):
    assert not by_id(engine().evaluate(foul_snap(2, period, 400)), "foul_trouble")


def test_r4_three_fouls_in_the_first_half_is_information_the_coach_usually_already_acts_on():
    for period in (1, 2):
        [alert] = by_id(engine().evaluate(foul_snap(3, period, 400)), "foul_trouble")
        assert alert.severity == "info" and alert.category == "faltas"


def test_r4_three_fouls_in_the_second_half_is_a_warning_while_there_is_time_to_be_eliminated():
    for period in (3, 4):
        [alert] = by_id(engine().evaluate(foul_snap(3, period, 500)), "foul_trouble")
        assert alert.severity == "warning"


def test_r4_three_fouls_with_less_than_six_minutes_left_in_the_game_is_not_a_risk():
    assert not by_id(engine().evaluate(foul_snap(3, 4, 300)), "foul_trouble")
    assert by_id(engine().evaluate(foul_snap(3, 4, 361)), "foul_trouble")
    assert not by_id(engine().evaluate(foul_snap(3, 4, 360)), "foul_trouble")


def test_r4_the_time_left_counts_the_periods_still_to_play():
    assert by_id(engine().evaluate(foul_snap(3, 3, 100)), "foul_trouble")     # 1:40 of the 3rd + the whole 4th


def test_r4_four_fouls_is_critical_whatever_the_time_left_of_the_game_until_the_last_seconds():
    for period, remaining in ((1, 400), (4, 41)):
        assert [a.severity for a in by_id(engine().evaluate(foul_snap(4, period, remaining)), "foul_trouble")] == ["critical"]


@pytest.mark.parametrize("pf", [3, 4])
def test_r4_no_foul_alert_in_the_last_40_seconds_of_the_game_regression(pf):
    """#403: a third foul with seconds to go was announced; with this little game left there is nothing to do with it."""
    assert not by_id(engine().evaluate(foul_snap(pf, 4, 40)), "foul_trouble")
    assert not by_id(engine().evaluate(foul_snap(pf, 4, 0)), "foul_trouble")
    assert not by_id(engine().evaluate(foul_snap(pf, 5, 30)), "foul_trouble")             # overtime counts its own period
    assert by_id(engine().evaluate(foul_snap(4, 4, 41)), "foul_trouble") if pf == 4 else True


def test_r4_the_end_of_a_quarter_is_not_the_end_of_the_game():
    for period in (1, 2, 3):
        assert by_id(engine().evaluate(foul_snap(4, period, 30)), "foul_trouble")


def test_r4_the_rival_foul_alerts_are_silent_in_the_last_40_seconds_of_the_game_too_regression():
    """#403: 'Rival X con 3 faltas: atacarle' with seconds left is just as useless."""
    def rival_snap(remaining, period=4):
        s = foul_snap(3, period, remaining, pid="r1")
        s["players"] = {"r1": {**_player("Rita", RIVAL, pf=3)}, "r2": {**_player("Rosa", RIVAL, pf=4)}}
        return s
    for remaining in (30, 0):
        out = engine().evaluate(rival_snap(remaining))
        assert not by_id(out, "rival_foul_trouble") and not by_id(out, "rival_foul_pair")
    out = engine().evaluate(rival_snap(120))
    assert by_id(out, "rival_foul_trouble") and by_id(out, "rival_foul_pair")
    assert by_id(engine().evaluate(rival_snap(30, period=2)), "rival_foul_trouble")


def test_r4_the_threshold_of_time_comes_from_the_config():
    e = engine(config=RuleConfig(foul_min_left_s=120))
    assert by_id(e.evaluate(foul_snap(3, 4, 300)), "foul_trouble")


# --- F3: the bonus by the time left in the period -----------------------------------------------

def bonus_snap(remaining, count=4, rival_count=0):
    s = snap(period=2, fouls_by_period={OWN: {"2": count}, RIVAL: {"2": rival_count}})
    s["remaining"] = remaining
    return s


@pytest.mark.parametrize("remaining, count, severity", [
    (500, 4, "warning"), (100, 4, "info"),
    (500, 6, "critical"), (200, 6, "warning"), (60, 6, "info"),
])
def test_f3_the_longer_we_are_in_bonus_the_more_serious(remaining, count, severity):
    [alert] = by_id(engine().evaluate(bonus_snap(remaining, count)), "team_fouls_bonus")
    assert alert.severity == severity


def test_f3_the_rival_near_bonus_stays_information_whatever_the_time_left():
    [alert] = by_id(engine().evaluate(bonus_snap(500, count=0, rival_count=4)), "rival_near_bonus")
    assert alert.severity == "info"


# --- R8: rival fouls, concrete tactic -------------------------------------------------------------

RIVAL_TABLE = {"r1": {"name": "Rival Uno", "avg_min": 1500}, "r2": {"name": "Rival Dos", "avg_min": 400}}


def rival_foul_snap(pid="r1", pf=3):
    players = {pid: _player("Rival Uno", RIVAL, pf=pf), **{k: _player(v["name"], OWN, on_court=True) for k, v in
               {"g1": TABLE["g1"], "b1": TABLE["b1"]}.items()}}
    return snap(period=2, players=players)


def test_r8_an_important_rival_in_foul_trouble_is_a_warning_and_a_minor_one_is_information():
    e = engine(rival_baselines=RIVAL_TABLE)
    [important] = by_id(e.evaluate(rival_foul_snap("r1")), "rival_foul_trouble")
    [minor] = by_id(engine(rival_baselines=RIVAL_TABLE).evaluate(rival_foul_snap("r2")), "rival_foul_trouble")
    assert important.severity == "warning" and minor.severity == "info"
    assert important.evidence["important"] is True and minor.evidence["important"] is False


def test_r8_without_rival_baselines_it_stays_information():
    [alert] = by_id(engine().evaluate(rival_foul_snap("r1")), "rival_foul_trouble")
    assert alert.severity == "info"


def contact_table():
    table = copy.deepcopy(TABLE)
    table["g1"]["z"]["ftr"], table["b1"]["z"]["ftr"] = 0.2, 1.4
    return table


def test_r8_it_names_who_to_give_the_ball_to_the_one_who_draws_contact():
    e = engine(baselines=contact_table(), rival_baselines=RIVAL_TABLE)
    [alert] = by_id(e.evaluate(rival_foul_snap("r1")), "rival_foul_trouble")
    assert "Pivot Uno" in alert.message and "contacto" in alert.message
    tactic = alert.proposal[0]
    assert tactic["type"] == "tactic" and tactic["player_id"] == "b1" and "Pivot Uno" in tactic["message"]


def test_r8_nobody_who_draws_contact_gives_a_generic_tactic():
    e = engine(baselines=TABLE, rival_baselines=RIVAL_TABLE)
    [alert] = by_id(e.evaluate(rival_foul_snap("r1")), "rival_foul_trouble")
    assert alert.proposal[0]["type"] == "tactic" and "player_id" not in alert.proposal[0]


def test_r8_the_near_bonus_alert_names_the_same_player():
    s = rival_foul_snap("r2", pf=0)
    s["teams"][RIVAL]["fouls_by_period"] = {"2": 4}
    [alert] = by_id(engine(baselines=contact_table()).evaluate(s), "rival_near_bonus")
    assert alert.proposal[0]["player_id"] == "b1"


# --- R1: rival run by levels ---------------------------------------------------------------------

def points(team, total, start=300, step=10):
    """Baskets of 2 (the last of 1 if odd) of ``team`` spaced inside the run window."""
    out, n, t = [], total, start
    while n > 0:
        value = 2 if n >= 2 else 1
        out += [[t, team, "pts", value, "p1"]]
        n, t = n - value, t + step
    return out


def run_alerts(rival, own=0, elapsed=400, extra=(), timeouts=None, eng=None):
    s = snap(elapsed=elapsed, log=[*points(RIVAL, rival), *points(OWN, own, start=305), *extra])
    for team, times in (timeouts or {}).items():
        s["teams"][team]["timeouts"] = times
    return by_id((eng or engine()).evaluate(s), "rival_run")


@pytest.mark.parametrize("rival, own, severity", [
    (6, 0, "info"), (8, 2, "info"), (10, 4, "info"), (10, 2, "warning"), (12, 4, "warning"), (8, 0, "critical"), (14, 0, "critical"),
])
def test_r1_the_run_has_levels_by_net_points_and_the_unanswered_one_is_critical(rival, own, severity):
    [alert] = run_alerts(rival, own)
    assert alert.severity == severity and alert.category == "gestion"
    assert alert.evidence["rival_points"] == rival and alert.evidence["own_points"] == own


@pytest.mark.parametrize("rival, own", [(5, 0), (8, 3), (4, 0)])
def test_r1_less_than_six_net_is_not_a_run(rival, own):
    assert not run_alerts(rival, own)


def test_r1_it_says_why_with_the_causes_of_the_window():
    extra = [[310, RIVAL, "orb", 1, "r1"], [330, RIVAL, "orb", 1, "r1"]]
    [alert] = run_alerts(8, 2, extra=extra)
    assert "2 rebotes ofensivos del rival" in alert.message


def test_r1_it_proposes_a_timeout_only_if_there_are_some_left():
    [alert] = run_alerts(8, 2)
    assert alert.proposal[0]["type"] == "timeout" and alert.proposal[0]["left"] == 2
    [none_left] = run_alerts(8, 2, timeouts={OWN: [100, 200]})
    assert none_left.proposal == []


def test_r1_it_is_silent_in_the_minute_after_our_timeout():
    assert not run_alerts(8, 2, timeouts={OWN: [380]})


def test_r1_each_level_is_said_once_and_nothing_repeats_by_time():
    e = engine()
    assert [a.severity for a in run_alerts(6, 0, eng=e)] == ["info"]
    assert not run_alerts(6, 0, elapsed=410, eng=e)
    assert [a.severity for a in run_alerts(10, 2, elapsed=420, eng=e)] == ["warning"]
    assert not run_alerts(10, 2, elapsed=700, eng=e)
    assert all(a.rearm_s is None for a in run_alerts(8, 0, elapsed=800, eng=e))


# --- R3: turnovers ----------------------------------------------------------------------------------

def tov_snap(by_player, elapsed=400, timeouts=None):
    log = [[300 + 10 * i, OWN, "tov", 1, pid] for i, pid in enumerate(by_player)]
    s = snap(elapsed=elapsed, log=log, players={"a": _player("Ana", OWN), "b": _player("Bea", OWN)})
    for team, times in (timeouts or {}).items():
        s["teams"][team]["timeouts"] = times
    return s


def tov_alerts(by_player, **kw):
    eng = kw.pop("eng", None) or engine()
    return by_id(eng.evaluate(tov_snap(by_player, **kw)), "turnover_streak")


def test_r3_four_turnovers_propose_a_timeout_and_do_not_depend_on_rearm():
    [alert] = tov_alerts(["a", "b", "a", "b"])
    assert alert.proposal[0]["type"] == "timeout" and alert.proposal[0]["left"] == 2
    assert alert.rearm_s is None and alert.severity == "warning"


def test_r3_it_names_who_concentrates_the_turnovers_and_proposes_taking_him_off_the_ball():
    [alert] = tov_alerts(["a", "a", "a", "b"])
    assert "3 de Ana" in alert.message
    tactic = next(p for p in alert.proposal if p["type"] == "tactic")
    assert tactic["player_id"] == "a" and "Ana" in tactic["message"] and "manejo" in tactic["message"]
    assert alert.evidence["main_player_id"] == "a"


def test_r3_spread_turnovers_name_nobody():
    [alert] = tov_alerts(["a", "a", "b", "b"])
    assert "de Ana" not in alert.message and not [p for p in alert.proposal if p["type"] == "tactic"]


def test_r3_it_is_silent_just_after_our_timeout_and_comes_back_if_it_goes_on():
    e = engine()
    assert not tov_alerts(["a", "b", "a", "b"], timeouts={OWN: [390]}, eng=e)
    assert tov_alerts(["a", "b", "a", "b"], elapsed=460, timeouts={OWN: [390]}, eng=e)


def test_r3_the_same_streak_is_said_once():
    e = engine()
    assert tov_alerts(["a", "b", "a", "b"], eng=e)
    assert not tov_alerts(["a", "b", "a", "b"], elapsed=420, eng=e)


def test_r3_the_recommender_substitutions_come_after_the_timeout_proposal():
    from live_helpers import snap as roster_snap

    s = roster_snap(period=2, elapsed=1200)
    s["log"] = [[1000 + 30 * i, OWN, "tov", 1, pid] for i, pid in enumerate(["g1", "g1", "w1", "b1"])]
    [alert] = by_id(engine(baselines=TABLE).evaluate(s), "turnover_streak")
    kinds = [p["type"] for p in alert.proposal]
    assert kinds[0] == "timeout" and "sub" in kinds


# --- R5: escalated fatigue ------------------------------------------------------------------------------

# Low thresholds so that a stint under ten minutes (before the minutes-based components exist) reaches every level.
FATIGUE = RuleConfig(fatigue_alert_index=10, fatigue_warning_index=20, fatigue_critical_index=30)


def fatigue_snap(stint, elapsed=590, overrides=None, log=None):
    from live_helpers import snap as roster_snap

    s = roster_snap(period=1, elapsed=elapsed, overrides={"g1": {"stint": stint, "minutes": stint}, **(overrides or {})})
    s["log"] = log or []
    return s


def fatigue_alerts(eng, stint, **kw):
    return by_id(eng.evaluate(fatigue_snap(stint, **kw)), "fatigue_high")


def test_r5_the_fatigue_alert_escalates_info_warning_critical_with_the_stint():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, baselines=TABLE, config=FATIGUE)
    assert fatigue_alerts(e, 440, elapsed=500) == []
    assert [a.severity for a in fatigue_alerts(e, 480, elapsed=500)] == ["info"]
    assert [a.severity for a in fatigue_alerts(e, 520, elapsed=540)] == ["warning"]
    assert [a.severity for a in fatigue_alerts(e, 560, elapsed=580)] == ["critical"]


def test_r5_each_level_is_said_once_per_stint_and_nothing_repeats_by_time():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, baselines=TABLE, config=FATIGUE)
    [first] = fatigue_alerts(e, 520, elapsed=540)
    assert first.rearm_s is None
    assert fatigue_alerts(e, 524, elapsed=544) == []
    assert fatigue_alerts(e, 530, elapsed=550) == []


def test_r5_a_new_stint_of_the_same_player_says_it_again():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, baselines=TABLE, config=FATIGUE)
    [first] = fatigue_alerts(e, 480, elapsed=500)                 # info, the stint started at second 20
    [second] = fatigue_alerts(e, 600, elapsed=1140)               # info again, another stint (it started at second 540)
    assert first.severity == second.severity == "info" and first.key != second.key


def test_r5_an_own_run_lowers_the_level_one_step_and_says_why():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, baselines=TABLE, config=FATIGUE)
    run = [[t, OWN, "pts", 2, "w1"] for t in (460, 480, 500, 520)]       # +8 in the last 150 s
    [alert] = fatigue_alerts(e, 560, elapsed=580, log=run + [[t, OWN, "fg2", 1, "w1"] for t in (460, 480, 500, 520)])
    assert alert.severity == "warning" and "parcial a favor" in alert.message.lower()


def test_r5_a_player_on_a_hot_streak_lowers_the_level_and_says_so():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, baselines=TABLE, config=FATIGUE)
    hot = [[t, OWN, "fg2", 1, "g1"] for t in (400, 450, 500)]
    [alert] = fatigue_alerts(e, 560, elapsed=580, log=hot)
    assert alert.severity == "warning" and "en racha" in alert.message


def test_r5_the_context_never_lowers_below_information_and_keeps_its_own_key():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, baselines=TABLE, config=FATIGUE)
    hot = [[t, OWN, "fg2", 1, "g1"] for t in (400, 450, 500)]
    [lowered] = fatigue_alerts(e, 480, elapsed=500, log=hot)
    assert lowered.severity == "info"
    [plain] = fatigue_alerts(e, 482, elapsed=502)        # the streak is over: it is said as it is
    assert plain.key != lowered.key and plain.severity == "info"


def test_r5_a_fresh_player_or_the_bench_has_no_alert():
    e = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, baselines=TABLE, config=FATIGUE)
    assert fatigue_alerts(e, 100, elapsed=500) == []
    assert fatigue_alerts(e, 560, elapsed=580, overrides={"g1": {"on_court": False}}) == []


# --- R6: the lever only when it changes or gets worse ---------------------------------------------------------

def lever_alerts(eng, tov, elapsed=1200):
    return by_id(eng.evaluate(ff_snap(_stats_ff(tov=tov), _stats_ff(), elapsed=elapsed)), "four_factors_lever")


def _stats_ff(**kw):
    base = dict(fg2m=20, fg2a=40, fg3m=6, fg3a=20, ftm=10, fta=14, orb=8, drb=25,
                tov=10, tov_team=0, stl=5, ast=12, blk=2, pts=0)
    base.update(kw)
    return base


def test_r6_the_same_lever_is_said_once_and_not_repeated_by_time():
    e = engine()
    [first] = lever_alerts(e, 22)
    assert first.rearm_s is None and first.evidence["lever"] == "tov"
    assert lever_alerts(e, 22, elapsed=1300) == [] and lever_alerts(e, 22, elapsed=2200) == []


def test_r6_it_is_said_again_when_the_lever_gets_five_points_worse_measured_unshrunk():
    e = engine()
    [first] = lever_alerts(e, 22)
    [worse] = lever_alerts(e, 40, elapsed=1300)
    assert worse.evidence["pts100_raw"] <= first.evidence["pts100_raw"] - 5
    assert worse.key != first.key
    assert lever_alerts(e, 40, elapsed=1400) == []


def test_r6_getting_better_and_worse_again_does_not_repeat_what_was_already_said():
    e = engine()
    assert lever_alerts(e, 22)
    assert lever_alerts(e, 40, elapsed=1300)            # five points worse: said again
    assert lever_alerts(e, 22, elapsed=1400) == []      # it improved
    assert lever_alerts(e, 40, elapsed=1500) == []      # and worsened again to the same point: nothing new


def test_r6_a_small_oscillation_does_not_repeat_it():
    e = engine()
    lever_alerts(e, 22)
    assert lever_alerts(e, 23, elapsed=1300) == []


def test_r6_the_step_comes_from_the_config():
    e = engine(config=RuleConfig(lever_step_pts100=1.0))
    lever_alerts(e, 22)
    assert lever_alerts(e, 24, elapsed=1300)


def test_r6_a_different_lever_is_a_new_alert():
    e = engine()
    [first] = lever_alerts(e, 22)
    other = by_id(e.evaluate(ff_snap(_stats_ff(), _stats_ff(fg2m=30, fg2a=40), elapsed=1400)), "four_factors_lever")
    assert other and other[0].evidence["lever"] != "tov" and other[0].key != first.key
    back = lever_alerts(e, 22, elapsed=1500)               # the first lever is the main one again: that is a change too
    assert back and back[0].evidence["lever"] == "tov" and back[0].key != first.key
