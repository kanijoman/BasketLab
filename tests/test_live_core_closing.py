"""Closing and pauses (issue #246): C1 the briefing of a close finish, C3 the summary at the end of a quarter and at halftime,
C4 managing an advantage, G1 the rival imposes its pace and we are losing.

C1 uses the free-throw percentage of each player in the package (``ft_pct``, ``fta``); without it the briefing leaves that part out.
"""
import json

import pytest

from src.live_core.advice import RULES, AdviceEngine
from src.live_core.config import RULE_IDS, RuleConfig
from tests.test_live_core_advice import OWN, RIVAL, snap

STATS0 = {k: 0 for k in ("fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta", "orb", "drb", "tov", "stl", "ast", "blk")}


def player(name, team, on_court=True, pf=0, stats=None, pts=0):
    return {"name": name, "team_id": team, "on_court": on_court, "minutes": 600, "stint": 0, "pf": pf, "pts": pts,
            "pf_by_period": {}, "stats": {**STATS0, **(stats or {})}, "unsportsmanlike": 0, "technical": 0}


def ft(pct, fta=40):
    return {"name": "x", "avg_min": 1200, "ft_pct": pct, "fta": fta}


OWN_FT = {"g1": ft(0.88), "w1": ft(0.60), "w2": ft(0.80), "b1": ft(0.55), "g3": ft(0.70)}
RIVAL_FT = {"r1": ft(0.52), "r2": ft(0.85), "r3": ft(0.60), "r4": ft(0.74), "r5": ft(0.78)}


def lineup(stats_own=None):
    own = {pid: player(f"Propia {pid}", OWN, stats=stats_own) for pid in OWN_FT}
    rival = {pid: player(f"Rival {pid}", RIVAL) for pid in RIVAL_FT}
    own["g1"]["name"], own["w2"]["name"] = "Guard Uno", "Ala Dos"
    rival["r1"]["name"], rival["r3"]["name"] = "Rita", "Rut"
    return {**own, **rival}


def finish(period=4, remaining=200, margin=2, players=None, timeouts=None, fouls=None, elapsed=None):
    s = snap(elapsed=elapsed or (period - 1) * 600 + 600 - remaining, period=period, players=players if players is not None else lineup(),
             fouls_by_period=fouls)
    s["remaining"], s["score"] = remaining, {OWN: 60, RIVAL: 60 - margin}
    for team, times in (timeouts or {}).items():
        s["teams"][team]["timeouts"] = times
    return s


def engine(**kw):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, **kw)


def by_id(advices, advice_id):
    return [a for a in advices if a.id == advice_id]


def test_the_rules_are_registered_and_can_be_switched_off():
    for rule_id in ("closing_briefing", "period_summary", "advantage_management", "pace_control"):
        assert rule_id in RULE_IDS and rule_id in [rid for rid, _ in RULES]
    off = engine(baselines=OWN_FT, rival_baselines=RIVAL_FT, config=RuleConfig(rules_off=("closing_briefing",)))
    assert not by_id(off.evaluate(finish()), "closing_briefing")


# --- C1: the briefing of a close finish --------------------------------------------------------------------------

def test_c1_a_close_finish_gets_a_briefing_with_timeouts_fouls_and_free_throws():
    s = finish(timeouts={RIVAL: [1300, 1500]}, fouls={OWN: {"4": 3}, RIVAL: {"4": 5}})
    [alert] = by_id(engine(baselines=OWN_FT, rival_baselines=RIVAL_FT).evaluate(s), "closing_briefing")
    assert alert.category == "gestion" and alert.severity == "critical" and alert.evidence["base_severity"] == "warning"
    msg = alert.message
    assert "Cierre igualado" in msg and "+2" in msg and "3:20" in msg
    assert "3 tiempos muertos" in msg and "rival 1" in msg
    assert "faltas de equipo" in msg and "3" in msg and "5" in msg
    assert "Guard Uno (88 %)" in msg and "Ala Dos (80 %)" in msg           # the best free-throw shooters on court
    assert "Rita (52 %)" in msg and "Rut (60 %)" in msg                     # who to foul
    kinds = [p["type"] for p in alert.proposal]
    assert kinds[0] == "timeout" and kinds.count("tactic") == 2


def test_c1_without_free_throw_data_in_the_package_it_leaves_that_part_out():
    [alert] = by_id(engine().evaluate(finish()), "closing_briefing")
    assert "Cierre igualado" in alert.message and "tiempos muertos" in alert.message
    assert "tiradores" not in alert.message and "hacer falta" not in alert.message.lower()
    assert [p["type"] for p in alert.proposal] == ["timeout"]


def test_c1_it_adds_our_poor_free_throws_of_the_day():
    players = lineup(stats_own={"ftm": 1, "fta": 2})                           # 5 players x (1/2) = 5/10
    [alert] = by_id(engine(baselines=OWN_FT, rival_baselines=RIVAL_FT).evaluate(finish(players=players)), "closing_briefing")
    assert "5/10" in alert.message and "hoy" in alert.message
    players = lineup(stats_own={"ftm": 2, "fta": 2})
    [good] = by_id(engine(baselines=OWN_FT, rival_baselines=RIVAL_FT).evaluate(finish(players=players)), "closing_briefing")
    assert "hoy" not in good.message


@pytest.mark.parametrize("kw", [dict(remaining=300), dict(margin=9), dict(period=3, remaining=100)])
def test_c1_it_is_only_for_a_close_finish(kw):
    assert not by_id(engine(baselines=OWN_FT, rival_baselines=RIVAL_FT).evaluate(finish(**kw)), "closing_briefing")


def test_c1_overtime_is_a_closing_stretch_too_and_it_is_said_once_per_period():
    e = engine(baselines=OWN_FT, rival_baselines=RIVAL_FT)
    assert by_id(e.evaluate(finish(period=5, remaining=200, margin=1, elapsed=2400 + 100)), "closing_briefing")
    assert not by_id(e.evaluate(finish(period=5, remaining=190, margin=1, elapsed=2400 + 110)), "closing_briefing")
    first = engine(baselines=OWN_FT, rival_baselines=RIVAL_FT)
    assert by_id(first.evaluate(finish()), "closing_briefing")
    assert not by_id(first.evaluate(finish(remaining=190)), "closing_briefing")


def test_c1_it_needs_the_game_context():
    off = engine(config=RuleConfig(rules_off=("game_context",)))
    assert not by_id(off.evaluate(finish()), "closing_briefing")


# --- C3: the summary of a quarter and of the first half ---------------------------------------------------------------

def pts(team, t, value=2):
    return [[t, team, "fg3" if value == 3 else "fg2", 1, "p1"], [t, team, "pts", value, "p1"]]


def tov(team, t):
    return [[t, team, "tov", 1, "p1"]]


def orb(team, t):
    return [[t, team, "orb", 1, "p1"]]


def flat(*groups):
    return [e for g in groups for e in g]


def end_of(period, log, players=None, remaining=0):
    s = snap(elapsed=period * 600 - remaining, period=period, players=players or {}, log=flat(*log))
    s["remaining"] = remaining
    return s


def test_c3_the_end_of_a_quarter_gets_a_summary_with_the_score_the_keys_and_adjustments():
    log = [pts(OWN, 100), pts(OWN, 200), pts(RIVAL, 150, 3), pts(RIVAL, 250, 3), pts(RIVAL, 300), pts(RIVAL, 350),
           *[tov(OWN, 50 + 40 * i) for i in range(6)], tov(RIVAL, 70), *[orb(RIVAL, 400 + 30 * i) for i in range(4)], orb(OWN, 450)]
    [alert] = by_id(engine().evaluate(end_of(1, log)), "period_summary")
    assert alert.severity == "info" and alert.category == "resumen" and alert.key == "summary:1"
    msg = alert.message
    assert "Fin del 1.er cuarto" in msg and "4-10" in msg and "-6" in msg
    assert "Pérdidas: 6 vs 1" in msg and "Rebotes ofensivos del rival: 4 vs 1" in msg
    assert "Asegurar el balón" in msg and "Cerrar el rebote" in msg
    assert len(alert.evidence["keys"]) <= 3 and 1 <= len(alert.evidence["adjustments"]) <= 2


def test_c3_at_most_three_keys_in_priority_order_and_two_adjustments():
    log = [pts(OWN, 100), *[tov(OWN, 50 + 40 * i) for i in range(6)], *[orb(RIVAL, 400 + 30 * i) for i in range(4)],
           pts(RIVAL, 120, 3), pts(RIVAL, 220, 3), pts(RIVAL, 320, 2),                       # a rival scorer with 8 points
           *[[[500 + i, OWN, "ft", 0, "p1"]] for i in range(6)]]                              # and poor own free throws
    players = {"r9": player("Rosa", RIVAL, pts=8)}
    log += [[[t, RIVAL, "pts", v, "r9"]] for t, v in ((120, 3), (220, 3), (320, 2))]
    [alert] = by_id(engine().evaluate(end_of(1, log, players=players)), "period_summary")
    keys = alert.evidence["keys"]
    assert len(keys) == 3 and keys[:2] == ["turnovers", "rival_orb"] and "own_ft" not in keys
    assert len(alert.evidence["adjustments"]) == 2


def test_c3_a_quiet_quarter_says_so():
    log = [pts(OWN, 100), pts(RIVAL, 200), pts(OWN, 300), pts(RIVAL, 400)]
    [alert] = by_id(engine().evaluate(end_of(1, log)), "period_summary")
    assert "Sin claves destacadas" in alert.message and alert.evidence["keys"] == [] and alert.evidence["adjustments"] == []


def test_c3_halftime_summarises_the_first_half_and_the_third_quarter_only_the_third():
    log = [pts(OWN, 100, 3), pts(RIVAL, 300), pts(OWN, 700, 3), pts(RIVAL, 900), pts(OWN, 1300), pts(RIVAL, 1500, 3)]
    [half] = by_id(engine().evaluate(end_of(2, log)), "period_summary")
    assert "Descanso" in half.message and "6-4" in half.message and half.key == "summary:2"
    [third] = by_id(engine().evaluate(end_of(3, log)), "period_summary")
    assert "Fin del 3.er cuarto" in third.message and "2-3" in third.message


@pytest.mark.parametrize("period, remaining", [(1, 5), (2, 120), (4, 0), (5, 0)])
def test_c3_only_at_the_end_of_the_first_three_periods(period, remaining):
    assert not by_id(engine().evaluate(end_of(period, [pts(OWN, 100)], remaining=remaining)), "period_summary")


def test_c3_if_the_poll_missed_the_end_the_summary_comes_in_the_first_minute_of_the_next_period_regression():
    """In the real recording the 0:00 of the 2nd period lasts two frames: a poll every 30 s misses it."""
    [first] = by_id(engine().evaluate(end_of(2, [pts(OWN, 100)], remaining=570)), "period_summary")        # 30 s into the 2nd
    assert first.key == "summary:1" and "Fin del 1.er cuarto" in first.message
    [half] = by_id(engine().evaluate(end_of(3, [pts(OWN, 100, 3), pts(RIVAL, 300)], remaining=560)), "period_summary")
    assert half.key == "summary:2" and "Descanso" in half.message and "3-2" in half.message
    assert not by_id(engine().evaluate(end_of(2, [pts(OWN, 100)], remaining=500)), "period_summary")     # a minute and a half in: too late
    assert not by_id(engine().evaluate(end_of(5, [pts(OWN, 100)], remaining=260)), "period_summary")     # nothing after the 4th period


def test_c3_the_fallback_does_not_repeat_a_summary_already_said_at_the_end_of_the_period():
    e = engine()
    assert by_id(e.evaluate(end_of(1, [pts(OWN, 100)])), "period_summary")
    assert not by_id(e.evaluate(end_of(2, [pts(OWN, 100)], remaining=570)), "period_summary")


def test_c3_each_period_is_summarised_once():
    e = engine()
    assert by_id(e.evaluate(end_of(1, [pts(OWN, 100)])), "period_summary")
    assert not by_id(e.evaluate(end_of(1, [pts(OWN, 100)])), "period_summary")


# --- C4: managing an advantage ---------------------------------------------------------------------------------------------

def test_c4_ten_points_up_with_less_than_five_minutes_says_to_manage_the_advantage():
    [alert] = by_id(engine().evaluate(finish(remaining=280, margin=10)), "advantage_management")
    assert alert.severity == "info" and alert.category == "gestion" and "+10" in alert.message
    assert [p["type"] for p in alert.proposal] == ["tactic"] * 3
    assert any("reloj" in p["message"] for p in alert.proposal) and any("triples" in p["message"] for p in alert.proposal)


@pytest.mark.parametrize("kw", [dict(remaining=280, margin=9), dict(remaining=301, margin=12), dict(period=3, remaining=100, margin=12),
                                dict(remaining=280, margin=-12)])
def test_c4_it_needs_ten_up_in_the_last_five_minutes_of_the_game(kw):
    assert not by_id(engine().evaluate(finish(**kw)), "advantage_management")


def test_c4_it_is_said_once():
    e = engine()
    assert by_id(e.evaluate(finish(remaining=280, margin=10)), "advantage_management")
    assert not by_id(e.evaluate(finish(remaining=270, margin=14)), "advantage_management")


# --- G1: the rival imposes its pace and we are losing ---------------------------------------------------------------------

POSSESSIONS = {"fg2m": 12, "fg2a": 20, "fg3m": 3, "fg3a": 10, "ftm": 8, "fta": 11, "orb": 5, "drb": 15, "tov": 7, "tov_team": 0,
               "stl": 4, "ast": 9, "blk": 1, "pts": 0}          # 30 - 5 + 7 + 4.84 = 36.8 possessions in 20 minutes = 73.7 per 40


def pace_engine(own, rival, **kw):
    return engine(team_baselines={"pace_own_per_40": own, "pace_rival_per_40": rival}, **kw)


def pace_snap(margin=-8, period=3, elapsed=1200, log=None):
    s = snap(elapsed=elapsed, period=period, log=log)
    s["teams"][OWN]["stats"], s["teams"][RIVAL]["stats"] = dict(POSSESSIONS), dict(POSSESSIONS)
    s["score"] = {OWN: 40, RIVAL: 40 - margin}
    s["remaining"] = 300
    return s


def test_g1_if_the_rival_slows_the_game_down_and_we_lose_the_advice_is_to_raise_the_pace():
    [alert] = by_id(pace_engine(80.0, 72.0).evaluate(pace_snap()), "pace_control")
    assert alert.severity == "info" and alert.category == "gestion" and "subir el ritmo" in alert.message
    assert alert.evidence["direction"] == "up" and alert.proposal[0]["type"] == "tactic"


def test_g1_if_the_rival_speeds_the_game_up_and_we_lose_the_advice_is_to_lower_the_pace():
    [alert] = by_id(pace_engine(66.0, 78.0).evaluate(pace_snap()), "pace_control")
    assert "bajar el ritmo" in alert.message and alert.evidence["direction"] == "down"


@pytest.mark.parametrize("own, rival, kw", [
    (80.0, 72.0, dict(margin=-3)),           # losing by little
    (80.0, 72.0, dict(margin=8)),            # winning
    (72.0, 80.0, {}),                        # the game is closer to our pace than to theirs
    (73.0, 72.0, {}),                        # both paces are alike: nothing to impose
    (80.0, 72.0, dict(elapsed=200)),         # too early to trust the pace
])
def test_g1_it_needs_the_rival_to_impose_its_pace_while_we_lose(own, rival, kw):
    assert not by_id(pace_engine(own, rival).evaluate(pace_snap(**kw)), "pace_control")


def test_g1_without_the_habitual_paces_it_says_nothing_and_it_is_said_once_per_period_and_direction():
    assert not by_id(engine().evaluate(pace_snap()), "pace_control")
    e = pace_engine(80.0, 72.0)
    assert by_id(e.evaluate(pace_snap()), "pace_control")
    assert not by_id(e.evaluate(pace_snap(elapsed=1260)), "pace_control")


def test_g1_it_does_not_speculate_with_much_game_left_regression():
    """#401: it said 'bajar el ritmo' with 15 minutes still to play. Only in the last ``pace_max_left_s`` (15:00)."""
    early = pace_snap(period=2)                           # 25:00 left
    assert not by_id(pace_engine(66.0, 78.0).evaluate(early), "pace_control")
    edge = pace_snap(period=3)                           # exactly 15:00 left
    assert by_id(pace_engine(66.0, 78.0).evaluate(edge), "pace_control")
    assert not by_id(pace_engine(66.0, 78.0, config=RuleConfig(pace_max_left_s=600)).evaluate(edge), "pace_control")


def test_g1_it_does_not_say_to_slow_down_when_the_comeback_came_while_we_sped_up_regression():
    """#401: the comeback arrived after raising the pace; telling the staff to change what is working is wrong."""
    comeback = flat(*[pts(OWN, 950 + 25 * i, 2) for i in range(5)], pts(RIVAL, 1000, 2))   # +8 net in the last 5 minutes
    s = pace_snap(margin=-8, log=comeback)
    assert not by_id(pace_engine(66.0, 78.0).evaluate(s), "pace_control")


def test_g1_a_recent_recovery_is_measured_with_the_net_points_of_the_window_only():
    old = flat(*[pts(OWN, 300 + 25 * i, 2) for i in range(5)])                             # long before the window
    assert by_id(pace_engine(66.0, 78.0).evaluate(pace_snap(log=old)), "pace_control")
    small = flat(pts(OWN, 1100, 2), pts(OWN, 1150, 2))                                     # +4: below ``pace_recovery_net``
    assert by_id(pace_engine(66.0, 78.0).evaluate(pace_snap(log=small)), "pace_control")


def test_the_alerts_are_json_serialisable():
    [alert] = by_id(engine().evaluate(finish()), "closing_briefing")
    assert json.loads(json.dumps(alert.proposal)) == alert.proposal


# --- K2 (issue #275): the clutch players in the closing briefing ----------------------------------------------------

def clutch(usage, effective=False, basis="clutch", sample="ok"):
    return {"basis": basis, "sample": sample, "sec": 600, "usage": usage, "effective": effective, "pps": 1.0, "pps_season": 1.0, "ft_pct": 0.7}


def with_clutch(table, **by_pid):
    return {pid: {**entry, **({"clutch": by_pid[pid]} if pid in by_pid else {})} for pid, entry in table.items()}


def briefing(own=None, rival=None, players=None):
    e = engine(baselines=with_clutch(OWN_FT, **(own or {})), rival_baselines=with_clutch(RIVAL_FT, **(rival or {})))
    [alert] = by_id(e.evaluate(finish(players=players)), "closing_briefing")
    return alert


def test_k2_the_rival_players_with_most_responsibility_are_named_and_labelled_effective_only_if_they_are():
    alert = briefing(rival={"r2": clutch(16.0, effective=True), "r1": clutch(12.0), "r3": clutch(5.0)})
    msg = alert.message
    assert "las que más asumen en el cierre: Rival r2 (eficaz), Rita" in msg and "Rut" not in msg.split("las que más asumen")[1].split(";")[0]
    assert [r["player_id"] for r in alert.evidence["rival_clutch"]] == ["r2", "r1"]
    assert any(p["type"] == "tactic" and "Vigilar" in p["message"] and "Rival r2" in p["message"] for p in alert.proposal)


def test_k2_without_a_clutch_sample_it_uses_the_fourth_period_and_says_so():
    alert = briefing(rival={"r1": clutch(14.0, effective=True, basis="q4", sample="small")})
    assert "Rita (eficaz, muestra pequeña)" in alert.message
    assert alert.evidence["rival_clutch"][0]["sample"] == "small"


def test_k2_whoever_has_no_clutch_data_is_left_out_and_without_data_there_is_no_clutch_part():
    assert "asumen" not in briefing().message
    alert = briefing(rival={"r1": {"basis": "none", "sample": "none", "sec": 0}})
    assert "asumen" not in alert.message


def test_k2_it_says_who_to_look_for_in_our_team_the_effective_first():
    alert = briefing(own={"g1": clutch(10.0, effective=False), "w2": clutch(8.0, effective=True), "b1": clutch(15.0)})
    assert "a quién buscar: Ala Dos (eficaz), Propia b1" in alert.message
    assert [o["player_id"] for o in alert.evidence["own_clutch"]] == ["w2", "b1"]
    assert any(p["type"] == "tactic" and p["message"].startswith("Buscar a Ala Dos") for p in alert.proposal)


def test_k2_the_bench_does_not_count_and_the_existing_parts_of_the_briefing_stay():
    players = lineup()
    players["r2"]["on_court"] = False
    alert = briefing(rival={"r2": clutch(20.0, effective=True), "r1": clutch(12.0)}, players=players)
    assert "Rival r2" not in alert.message.split("asumen")[1].split(";")[0] and "Rita" in alert.message
    assert "tiempos muertos" in alert.message and "hacer falta a" in alert.message
