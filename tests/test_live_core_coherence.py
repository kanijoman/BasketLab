"""The alerts do not contradict each other (feedback 0.4.0, #568): «subir el ritmo» and then «bajar el ritmo», «mantener el quinteto» and then «sacar a la jugadora».

A pattern for any rule, not a patch for a pair of them: some alerts take a STANCE on a topic of the game (``coherence.stance_of``: pace up/down, rotation keep/change). A new alert whose stance is the opposite
of one said a short while ago (``conflict_window_s``) waits unless it is more severe than that one, and when it goes ahead it says that it changes what was said.
"""
import pytest

from src.live_core import advice as advice_module
from src.live_core.advice import Advice, AdviceEngine
from src.live_core.coherence import stance_of
from src.live_core.config import RuleConfig
from tests.builders import OWN, RIVAL, snap


def pace(direction, severity="info", key=None):
    return Advice(key=key or f"pace:{direction}", id="pace_control", severity=severity, category="gestion", message=f"{direction.capitalize()} el ritmo.", evidence={"direction": direction})


def keep(key="own_run:1", severity="info"):
    return Advice(key=key, id="own_run", severity=severity, category="gestion", message="Parcial a favor. No romper el quinteto.", evidence={})


def change(key="fatigue:p1", severity="warning"):
    return Advice(key=key, id="fatigue_high", severity=severity, category="rotacion", message="Ana: riesgo de fatiga alto.", evidence={"player_id": "p1"})


def run(monkeypatch, steps):
    """``steps``: (elapsed, [advices the rules give at that moment]); returns what the engine says at each one."""
    queue = {}
    monkeypatch.setattr(advice_module, "RULES", [("fake", lambda s, ctx: queue.get(s["elapsed"], []))])
    engine = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, config=RuleConfig())
    said = []
    for elapsed, advices in steps:
        queue[elapsed] = advices
        said.append([a.key for a in engine.evaluate(snap(elapsed=elapsed))])
    return said, engine


def test_an_opposite_stance_on_the_same_topic_waits_while_the_first_one_is_recent_regression(monkeypatch):
    said, _ = run(monkeypatch, [(2000, [pace("up")]), (2100, [pace("down")])])
    assert said == [["pace:up"], []]


def test_it_goes_ahead_once_the_window_has_passed(monkeypatch):
    window = RuleConfig().conflict_window_s
    said, _ = run(monkeypatch, [(2000, [pace("up")]), (2000 + window + 10, [pace("down")])])
    assert said == [["pace:up"], ["pace:down"]]


def test_the_same_stance_again_and_other_topics_are_not_held_back(monkeypatch):
    said, _ = run(monkeypatch, [(2000, [pace("up", key="pace:up:1")]), (2060, [pace("up", key="pace:up:2")]), (2070, [change()])])
    assert said == [["pace:up:1"], ["pace:up:2"], ["fatigue:p1"]]


def test_a_more_severe_alert_goes_ahead_and_says_it_changes_what_was_said(monkeypatch):
    queue = {}
    monkeypatch.setattr(advice_module, "RULES", [("fake", lambda s, ctx: queue.get(s["elapsed"], []))])
    engine = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, config=RuleConfig())
    queue[2000] = [keep()]
    engine.evaluate(snap(elapsed=2000))
    queue[2050] = [change()]
    [alert] = engine.evaluate(snap(elapsed=2050))
    assert alert.key == "fatigue:p1" and "Cambia lo dicho antes" in alert.message and "mantener el quinteto" in alert.message


def test_what_was_withheld_is_not_lost_it_is_said_when_the_window_is_over(monkeypatch):
    window = RuleConfig().conflict_window_s
    said, _ = run(monkeypatch, [(2000, [pace("up")]), (2050, [pace("down")]), (2000 + window + 10, [pace("down")])])
    assert said == [["pace:up"], [], ["pace:down"]]


@pytest.mark.parametrize("advice, expected", [
    (pace("up"), ("pace", "up")), (pace("down"), ("pace", "down")),
    (Advice("w", "win_flip", "warning", "probabilidad", "x", {"lever": "pace", "lever_direction": "down"}), ("pace", "down")),
    (Advice("w", "win_flip", "warning", "probabilidad", "x", {"lever": "tov"}), None),
    (keep(), ("rotation", "keep")), (change(), ("rotation", "change")),
    (Advice("l", "lineup_net", "warning", "rotacion", "x", {}), ("rotation", "change")),
    (Advice("t", "timeout_followup", "info", "gestion", "x", {"worked": True}), ("rotation", "keep")),
    (Advice("t", "timeout_followup", "info", "gestion", "x", {"worked": False}), None),
    (Advice("f", "foul_trouble", "warning", "faltas", "x", {}), None),
])
def test_which_alerts_take_a_stance(advice, expected):
    found = stance_of(advice)
    assert (found[0], found[1]) == expected if expected else found is None
