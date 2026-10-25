"""The review of a timeout, own or rival: why it was called (what happened in the 2 minutes before) and whether it worked (the 2 minutes after).

Asked by the staff on 23/10/2026: un aviso de tiempo muerto (nuestro o rival) con un breve análisis de los 2 minutos anteriores/posteriores (¿por fatiga?, ¿para cortar un
parcial?, ¿para preparar una jugada?), con cambios, defensas alternativas, lo que ha ido bien y mal.
"""
import pytest

from src.live_core.advice import RULES, AdviceEngine
from src.live_core.config import RULE_IDS, RuleConfig
from tests.builders import OWN, RIVAL, _player, snap


def pts(team, t, value=2):
    return [t, team, "pts", value, "p1" if team == OWN else "r1"]


def shot(team, t, made, kind="fg2"):
    return [t, team, kind, 1 if made else 0, "p1" if team == OWN else "r1"]


def tov(team, t):
    return [t, team, "tov", 1, "p1" if team == OWN else "r1"]


def at(elapsed, log, own_timeouts=(), rival_timeouts=(), players=None, period=2, remaining=None, score=None):
    """A snapshot at ``elapsed`` with the given log and timeouts (the timeouts are also written in the log, as the engine does)."""
    log = list(log) + [[t, OWN, "timeout", 1, None] for t in own_timeouts] + [[t, RIVAL, "timeout", 1, None] for t in rival_timeouts]
    s = snap(elapsed=elapsed, period=period, log=log, players=players or {})
    s["remaining"] = remaining if remaining is not None else max(0, period * 600 - elapsed)
    s["teams"][OWN]["timeouts"] = list(own_timeouts)
    s["teams"][RIVAL]["timeouts"] = list(rival_timeouts)
    if score:
        s["score"] = score
    return s


def engine(**kw):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, **kw)


def by_id(alerts, alert_id):
    return [a for a in alerts if a.id == alert_id]


RIVAL_RUN = [pts(RIVAL, 660), pts(RIVAL, 690, 3), pts(RIVAL, 720, 2), pts(RIVAL, 750, 2)]      # 0-9 against in the 2 minutes before the timeout at 1200 (2nd quarter, 10:00 played)
OWN_RUN = [pts(OWN, 660), pts(OWN, 690, 3), pts(OWN, 720, 2), pts(OWN, 750, 2)]
T = 760


def review(snapshot, eng=None):
    return by_id((eng or engine()).evaluate(snapshot), "timeout_review")


def followup(snapshot, eng=None):
    return by_id((eng or engine()).evaluate(snapshot), "timeout_followup")


def test_the_rules_are_registered_and_can_be_switched_off():
    for rule_id in ("timeout_review", "timeout_followup"):
        assert rule_id in RULE_IDS and rule_id in [rid for rid, _ in RULES]
    off = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, config=RuleConfig(rules_off=("timeout_review",)))
    assert not by_id(off.evaluate(at(T + 10, RIVAL_RUN, own_timeouts=[T])), "timeout_review")


# --- why it was called: the 2 minutes before -------------------------------------------------------------------------

def test_an_own_timeout_after_a_rival_run_is_to_stop_it_and_says_the_run():
    [alert] = review(at(T + 10, RIVAL_RUN, own_timeouts=[T], score={OWN: 20, RIVAL: 30}))
    assert alert.severity == "info" and alert.category == "gestion" and alert.evidence["reason"] == "run"
    assert "Tiempo muerto propio" in alert.message and "cortar el parcial" in alert.message and "0-9" in alert.message
    assert alert.evidence["team_id"] == OWN and alert.evidence["net"] == -9


def test_a_rival_timeout_after_our_run_is_to_stop_ours():
    [alert] = review(at(T + 10, OWN_RUN, rival_timeouts=[T]))
    assert "Tiempo muerto del rival" in alert.message and "cortar nuestro parcial" in alert.message and "9-0" in alert.message
    assert alert.evidence["reason"] == "run" and alert.evidence["team_id"] == RIVAL


@pytest.mark.parametrize("timeouts, who", [({"own_timeouts": [T]}, OWN), ({"rival_timeouts": [T]}, RIVAL)])
def test_three_turnovers_without_a_run_are_the_reason(timeouts, who):
    log = [tov(who, 660), tov(who, 690), tov(who, 720), pts(OWN, 700), pts(RIVAL, 730)]
    [alert] = review(at(T + 10, log, **timeouts))
    assert alert.evidence["reason"] == "turnovers" and "3 pérdidas" in alert.message


def test_a_drought_is_the_reason_when_the_team_has_not_scored_for_a_minute_and_a_half():
    log = [pts(OWN, 560), pts(RIVAL, 660), pts(RIVAL, 710)]            # we scored last at 16:40: 200 s without scoring, and the rival run is only -4
    [alert] = review(at(T + 10, log, own_timeouts=[T]))
    assert alert.evidence["reason"] == "drought" and "sin anotar" in alert.message


def test_fatigue_is_the_reason_and_the_tired_players_are_named_with_a_rotation():
    players = {"p1": _player("Ana", OWN, stint=900, minutes=1500), "p2": _player("Bea", OWN, stint=60, minutes=300)}
    log = [pts(OWN, 670), pts(RIVAL, 700), pts(OWN, 730), pts(RIVAL, 750)]
    [alert] = review(at(T + 10, log, own_timeouts=[T], players=players))
    assert alert.evidence["reason"] == "fatigue" and "Ana" in alert.message and "Bea" not in alert.message
    assert any(p["type"] == "tactic" and "Ana" in p["message"] for p in alert.proposal)


def test_foul_trouble_is_the_reason_of_a_timeout_with_a_player_with_four_fouls_on_court():
    players = {"p1": _player("Ana", OWN, pf=4, stint=100, minutes=500)}
    log = [pts(OWN, 670), pts(RIVAL, 700), pts(OWN, 730), pts(RIVAL, 750)]
    [alert] = review(at(T + 10, log, own_timeouts=[T], players=players))
    assert alert.evidence["reason"] == "fouls" and "Ana" in alert.message


def test_a_timeout_at_the_end_of_a_period_is_to_prepare_the_last_possession():
    log = [pts(OWN, 1100), pts(RIVAL, 1130), pts(OWN, 1160), pts(RIVAL, 1170)]
    [alert] = review(at(1175, log, own_timeouts=[1170], remaining=25))
    assert alert.evidence["reason"] == "last_possession" and "última posesión" in alert.message


def test_without_a_clear_reason_it_says_so_and_still_offers_the_analysis():
    log = [pts(OWN, 670), pts(RIVAL, 700), pts(OWN, 730), pts(RIVAL, 750)]
    [alert] = review(at(T + 10, log, own_timeouts=[T]))
    assert alert.evidence["reason"] == "none" and "descanso o preparar una jugada" in alert.message
    assert alert.proposal


# --- what went well and badly --------------------------------------------------------------------------------------

def test_it_says_what_went_well_and_what_went_badly_in_the_two_minutes():
    log = [shot(OWN, 650 + 10 * i, True) for i in range(6)] + [pts(OWN, 650 + 10 * i) for i in range(6)] \
        + [tov(RIVAL, 660), tov(RIVAL, 680), tov(RIVAL, 700), tov(OWN, 720), tov(OWN, 730), tov(OWN, 740)]
    [alert] = review(at(T + 10, log, own_timeouts=[T], score={OWN: 30, RIVAL: 20}))
    assert "Ha ido bien" in alert.message and "3 pérdidas del rival" in alert.message
    assert "Ha ido mal" in alert.message and "3 pérdidas propias" in alert.message
    assert alert.evidence["well"] and alert.evidence["bad"]


# --- proposals ---------------------------------------------------------------------------------------------------

def test_a_run_comes_with_an_alternative_defence_for_its_cause():
    log = [pts(RIVAL, 660, 3), pts(RIVAL, 690, 3), pts(RIVAL, 720, 3), shot(RIVAL, 660, True, "fg3"), shot(RIVAL, 690, True, "fg3"), shot(RIVAL, 720, True, "fg3")]
    [alert] = review(at(T + 10, log, own_timeouts=[T]))
    assert "tirador" in " ".join(p["message"] for p in alert.proposal).lower()


def test_a_rival_timeout_proposes_to_receive_the_restart_and_to_keep_the_intensity():
    [alert] = review(at(T + 10, OWN_RUN, rival_timeouts=[T]))
    texts = " ".join(p["message"] for p in alert.proposal).lower()
    assert "saque" in texts and "intensidad" in texts


# --- once per timeout and not for old ones -----------------------------------------------------------------------------

def test_each_timeout_is_reviewed_once():
    e = engine()
    assert review(at(T + 10, RIVAL_RUN, own_timeouts=[T]), e)
    assert not review(at(T + 20, RIVAL_RUN, own_timeouts=[T]), e)
    assert review(at(T + 100, RIVAL_RUN, own_timeouts=[T, T + 90]), e)          # the new one


def test_the_timeouts_of_long_ago_are_not_reviewed_when_the_engine_starts_late():
    assert not review(at(T + 900, RIVAL_RUN, own_timeouts=[T], period=3, remaining=300))


# --- the two minutes after ---------------------------------------------------------------------------------------------

def test_an_own_timeout_that_worked_says_so_and_asks_to_keep_what_was_done():
    log = [*RIVAL_RUN, pts(OWN, T + 40, 3), pts(OWN, T + 70), pts(OWN, T + 100, 2), pts(OWN, T + 110)]       # 9-0 against, then +9 after the timeout
    [alert] = followup(at(T + 125, log, own_timeouts=[T]))
    assert alert.severity == "info" and alert.evidence["worked"] is True and alert.evidence["net"] == 9
    assert "Tras el tiempo muerto propio" in alert.message and "funcionado" in alert.message
    assert any("mantener" in p["message"].lower() for p in alert.proposal)


def test_an_own_timeout_that_did_not_work_proposes_another_one_or_a_change():
    log = [*RIVAL_RUN, pts(RIVAL, T + 40, 3), pts(RIVAL, T + 70), pts(OWN, T + 100, 2), pts(RIVAL, T + 110, 3)]
    [alert] = followup(at(T + 125, log, own_timeouts=[T]))
    assert alert.evidence["worked"] is False and "no ha funcionado" in alert.message.lower()
    kinds = [p["type"] for p in alert.proposal]
    assert "timeout" in kinds and "tactic" in kinds


def test_it_waits_for_the_two_minutes_and_is_said_once():
    e = engine()
    log = [*RIVAL_RUN, pts(OWN, T + 40, 3)]
    assert not followup(at(T + 80, log, own_timeouts=[T]), e)
    assert followup(at(T + 125, log, own_timeouts=[T]), e)
    assert not followup(at(T + 140, log, own_timeouts=[T]), e)


def test_a_rival_timeout_is_followed_up_only_when_the_rival_answers_strongly():
    answered = [*OWN_RUN, pts(RIVAL, T + 40, 3), pts(RIVAL, T + 60, 2), pts(RIVAL, T + 90, 3), pts(RIVAL, T + 110, 2)]
    [alert] = followup(at(T + 125, answered, rival_timeouts=[T]))
    assert "Tras el tiempo muerto del rival" in alert.message and alert.evidence["worked"] is True
    quiet = [*OWN_RUN, pts(RIVAL, T + 40, 2), pts(OWN, T + 70, 2)]
    assert not followup(at(T + 125, quiet, rival_timeouts=[T]))


def test_what_happens_in_the_next_period_does_not_count_for_the_timeout_of_the_last_minute():
    log = [pts(OWN, 1170, 2), pts(RIVAL, 1210, 3), pts(RIVAL, 1230, 3)]
    s = at(1300, log, own_timeouts=[1160], period=3, remaining=500)
    [alert] = followup(s)
    assert alert.evidence["net"] == 2 and alert.evidence["window_s"] == 40            # only what was left of the period
