"""Game context (issue #239): the phase of the match changes how urgent each alert is.

decided (|margin| >= 20 with less than 8:00 left in the 4th period): performance, rhythm, rival and fatigue alerts go
down one level and fouls are kept. close_late (|margin| <= 6 with 4:00 or less in the 4th period, or overtime within
6): fouls and rhythm (timeouts) go up one level and fatigue goes down (nobody rests the best players now). A changed
alert carries its phase in the key so a lowered alert never blocks the normal one later.
"""
import dataclasses

import pytest

from src.live_core.advice import Advice, AdviceEngine
from src.live_core.clock import elapsed_seconds
from src.live_core.config import RULE_IDS, FEATURE_IDS, RuleConfig, unknown_rule_ids
from src.live_core.game_context import PHASES, adjust_for_phase, game_phase

OWN, RIVAL = "T1", "T2"
CFG = RuleConfig()


def mk(period=4, remaining=300, margin=0, own_to=(), rival_to=(), log=None, players=None):
    stamp = lambda pairs: [elapsed_seconds(p, r) for p, r in pairs]  # noqa: E731
    team = lambda timeouts: {"name": "x", "fouls_game": 0, "timeouts": timeouts, "fouls_by_period": {}, "stats": {}}  # noqa: E731
    return {"period": period, "remaining": remaining, "elapsed": elapsed_seconds(period, remaining), "last_num": 1,
            "score": {OWN: 60 + margin, RIVAL: 60}, "teams": {OWN: team(stamp(own_to)), RIVAL: team(stamp(rival_to))},
            "players": players or {}, "log": log or []}


def phase(period, remaining, margin, cfg=CFG):
    return game_phase(mk(period, remaining, margin), OWN, RIVAL, cfg)["phase"]


# --- the phase ----------------------------------------------------------------------------

@pytest.mark.parametrize("margin", [20, -20, 35])
def test_a_game_with_a_big_margin_and_under_eight_minutes_left_is_decided(margin):
    assert phase(4, 479, margin) == "decided"


@pytest.mark.parametrize("period,remaining,margin", [
    (4, 480, 25), (4, 600, 25),        # eight minutes or more left
    (4, 100, 19), (4, 100, -19),       # not far enough
    (3, 100, 30), (2, 100, 30),        # not the 4th period
    (5, 100, 25),                      # overtime is never "decided"
])
def test_otherwise_a_big_margin_does_not_decide_the_game(period, remaining, margin):
    assert phase(period, remaining, margin) != "decided"


@pytest.mark.parametrize("remaining,margin", [(240, 6), (240, -6), (100, 0), (1, 3)])
def test_the_last_four_minutes_of_a_close_game_are_the_closing_stretch(remaining, margin):
    assert phase(4, remaining, margin) == "close_late"


@pytest.mark.parametrize("period,remaining,margin", [(4, 241, 2), (4, 100, 7), (4, 100, -7), (3, 100, 0)])
def test_an_early_or_open_game_is_normal(period, remaining, margin):
    assert phase(period, remaining, margin) == "normal"


def test_overtime_is_the_closing_stretch_while_it_is_within_reach():
    assert phase(5, 300, 0) == "close_late" and phase(6, 120, -6) == "close_late"
    assert phase(5, 200, 10) == "normal"


def test_the_context_says_the_margin_from_our_side_and_the_time_left():
    ctx = game_phase(mk(4, 300, margin=-22), OWN, RIVAL, CFG)
    assert ctx == {"phase": "decided", "margin": -22, "remaining_s": 300}
    assert game_phase(mk(4, 300, margin=22), RIVAL, OWN, CFG)["margin"] == -22


def test_thresholds_come_from_the_config():
    tight = RuleConfig(decided_margin=10, decided_remaining_s=600, close_margin=2, close_remaining_s=60)
    assert phase(4, 590, 12, tight) == "decided" and phase(4, 590, 12) == "normal"
    assert phase(4, 50, 2, tight) == "close_late" and phase(4, 50, 4, tight) == "normal"


def test_without_a_perspective_or_a_rival_in_the_snapshot_the_game_is_normal():
    assert game_phase(mk(4, 100, 30), None, RIVAL, CFG)["phase"] == "normal"
    assert game_phase(mk(4, 100, 30), OWN, "nobody", CFG)["phase"] == "normal"
    assert game_phase(mk(4, 100, 30), OWN, None, CFG) == {"phase": "normal", "margin": 0, "remaining_s": 100}


def test_the_phases_are_declared():
    assert PHASES == ("normal", "close_late", "decided")


# --- adjusting an alert -------------------------------------------------------------------

def adv(severity, category, key="k"):
    return Advice(key=key, id="rule", severity=severity, category=category, message="m", evidence={"x": 1})


def ctx(name):
    return {"phase": name, "margin": 0, "remaining_s": 100}


@pytest.mark.parametrize("category", ["four_factors", "rival", "gestion", "rotacion"])
def test_in_a_decided_game_performance_and_fatigue_alerts_go_down_one_level(category):
    assert adjust_for_phase(adv("critical", category), ctx("decided")).severity == "warning"
    assert adjust_for_phase(adv("warning", category), ctx("decided")).severity == "info"


def test_in_a_decided_game_fouls_are_kept_and_info_cannot_go_lower():
    kept = adv("critical", "faltas")
    assert adjust_for_phase(kept, ctx("decided")) is kept
    info = adv("info", "rival")
    assert adjust_for_phase(info, ctx("decided")) is info


def test_a_changed_alert_carries_the_phase_in_its_key_and_its_evidence():
    out = adjust_for_phase(adv("warning", "rival", key="rival_hot:7:pts"), ctx("decided"))
    assert out.key == "rival_hot:7:pts~decided"
    assert out.evidence == {"x": 1, "phase": "decided", "base_severity": "warning"}
    assert dataclasses.replace(out, key="k", severity="warning", evidence={"x": 1}) == adv("warning", "rival")


def test_an_alert_the_phase_leaves_alone_keeps_its_key():
    assert adjust_for_phase(adv("warning", "faltas"), ctx("decided")).key == "k"


def test_in_the_closing_stretch_fouls_and_timeouts_go_up_and_fatigue_goes_down():
    assert adjust_for_phase(adv("warning", "faltas"), ctx("close_late")).severity == "critical"
    assert adjust_for_phase(adv("info", "faltas"), ctx("close_late")).severity == "warning"
    assert adjust_for_phase(adv("warning", "gestion"), ctx("close_late")).severity == "critical"
    assert adjust_for_phase(adv("critical", "rotacion"), ctx("close_late")).severity == "warning"
    assert adjust_for_phase(adv("warning", "rotacion"), ctx("close_late")).key == "k~close_late"


def test_in_the_closing_stretch_a_critical_foul_is_already_at_the_top():
    top = adv("critical", "faltas")
    assert adjust_for_phase(top, ctx("close_late")) is top
    other = adv("warning", "rival")
    assert adjust_for_phase(other, ctx("close_late")) is other


def test_a_normal_game_changes_nothing():
    alert = adv("warning", "rotacion")
    assert adjust_for_phase(alert, ctx("normal")) is alert


# --- in the engine ------------------------------------------------------------------------

RUN_LOG = [[2000, RIVAL, "pts", 3], [2040, RIVAL, "pts", 2], [2090, RIVAL, "pts", 3]]   # 0-8 against, before 2100


def engine(**kw):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, **kw)


def run_alerts(eng, snapshot):
    return [(a.key, a.severity, a.evidence.get("phase")) for a in eng.evaluate(snapshot) if a.id == "rival_run"]


def test_the_rival_run_is_a_warning_when_the_game_is_decided_and_critical_otherwise():
    assert run_alerts(engine(), mk(4, 300, margin=-22, log=RUN_LOG)) == [("rival_run~decided", "warning", "decided")]
    assert run_alerts(engine(), mk(4, 300, margin=-10, log=RUN_LOG)) == [("rival_run", "critical", None)]


def test_a_lowered_alert_does_not_block_the_normal_one_when_the_game_opens_up_again():
    eng = engine()
    assert run_alerts(eng, mk(4, 300, margin=-22, log=RUN_LOG)) == [("rival_run~decided", "warning", "decided")]
    assert run_alerts(eng, mk(4, 250, margin=-9, log=RUN_LOG)) == [("rival_run", "critical", None)]


def test_the_phase_does_not_repeat_what_the_staff_already_saw_inside_the_rearm_window():
    eng = engine()
    assert run_alerts(eng, mk(4, 300, margin=-10, log=RUN_LOG)) == [("rival_run", "critical", None)]
    assert run_alerts(eng, mk(4, 290, margin=-22, log=RUN_LOG)) == []            # same alert, 10 s later: not again
    later = [[2300, RIVAL, "pts", 3], [2340, RIVAL, "pts", 2], [2390, RIVAL, "pts", 3]]       # a new 0-8 run
    assert run_alerts(eng, mk(4, 0, margin=-22, log=later)) == [("rival_run~decided", "warning", "decided")]   # re-armed: it does


def one_shot(monkeypatch, category="rival"):
    """A rule with a single alert that never re-arms, to see how the phase treats alerts the staff already saw."""
    rule = lambda snap, ctx: [Advice(key="one", id="fake", severity="warning", category=category, message="m")]  # noqa: E731
    monkeypatch.setattr("src.live_core.advice.RULES", [("fake", rule)])
    return engine()


def test_a_one_shot_alert_already_seen_is_not_repeated_because_the_phase_lowers_it(monkeypatch):
    eng = one_shot(monkeypatch)
    assert [(a.key, a.severity) for a in eng.evaluate(mk(4, 600, margin=-25))] == [("one", "warning")]   # 10:00 left: normal
    assert eng.evaluate(mk(4, 300, margin=-25)) == []                                                  # decided: it was seen


def test_a_one_shot_alert_first_seen_lowered_is_said_again_at_full_severity_when_the_game_reopens(monkeypatch):
    eng = one_shot(monkeypatch)
    assert [(a.key, a.severity) for a in eng.evaluate(mk(4, 300, margin=-25))] == [("one~decided", "info")]
    assert [(a.key, a.severity) for a in eng.evaluate(mk(4, 200, margin=-8))] == [("one", "warning")]
    assert eng.evaluate(mk(4, 100, margin=-8)) == []


def test_fouls_keep_their_severity_in_a_decided_game():
    fouls = {"p1": {"name": "Ana", "team_id": OWN, "on_court": True, "minutes": 0, "stint": 0, "pf": 4, "pts": 0, "pf_by_period": {}}}
    [a] = [a for a in engine().evaluate(mk(4, 300, margin=-25, players=fouls)) if a.id == "foul_trouble"]
    assert (a.key, a.severity, "phase" in a.evidence) == ("foul:p1:4", "critical", False)


def test_the_context_can_be_switched_off_like_a_rule():
    off = engine(config=RuleConfig(rules_off=("game_context",)))
    assert run_alerts(off, mk(4, 300, margin=-22, log=RUN_LOG)) == [("rival_run", "critical", None)]
    assert "game_context" in FEATURE_IDS and unknown_rule_ids(["game_context", "rival_run"]) == ()
    assert "game_context" not in RULE_IDS      # it is not an alert rule: it has no alerts of its own


def test_the_analysis_exposes_the_context_and_the_timeouts_left():
    analysis = engine().analyze(mk(4, 300, margin=-22, own_to=[(3, 300)], rival_to=[(4, 500), (3, 100)]))
    assert analysis["context"] == {"phase": "decided", "margin": -22, "remaining_s": 300,
                                   "timeouts": {"own": 2, "rival": 1}}


def test_without_a_perspective_there_is_no_context():
    assert "context" not in AdviceEngine(own_team_id=None).analyze(mk())
