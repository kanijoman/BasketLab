"""No timeout is proposed right after one (issue #318): the alert stays, and offers a tactical or a rotation change instead."""

from src.live_core.config import RuleConfig
from tests.test_live_core_advice import OWN, RIVAL, _player, _pts, engine, snap

RUN = [_pts(1000, RIVAL, 3), _pts(1040, RIVAL, 2), _pts(1100, RIVAL, 3)]


def run_snapshot(own_timeouts=(), rival_timeouts=(), elapsed=1110):
    s = snap(elapsed=elapsed, log=RUN, players={"p1": _player("Ana", OWN, minutes=1100, stint=300)})
    s["teams"][OWN]["timeouts"], s["teams"][RIVAL]["timeouts"] = list(own_timeouts), list(rival_timeouts)
    return s


def run_alert(snapshot, **kw):
    [a] = [a for a in engine(**kw).evaluate(snapshot) if a.id == "rival_run"]
    return a


def kinds(alert):
    return [p["type"] for p in alert.proposal]


def test_without_a_recent_timeout_it_proposes_the_timeout_as_before():
    a = run_alert(run_snapshot())
    assert "timeout" in kinds(a) and "ya hubo un tiempo muerto" not in a.message.lower()


def test_a_timeout_just_called_is_not_proposed_again_a_tactical_change_is():
    a = run_alert(run_snapshot(own_timeouts=[1020]))        # 90 s ago: past the quiet minute of the run rule, still recent
    assert "timeout" not in kinds(a)
    tactic = [p for p in a.proposal if p["type"] == "tactic"]
    assert tactic and "rotación" in tactic[0]["message"].lower()
    assert a.message.endswith("Ya hubo un tiempo muerto propio hace poco.")          # the situation says it, the proposal is the change


def test_an_old_timeout_does_not_count_and_neither_does_one_of_the_rival():
    assert "timeout" in kinds(run_alert(run_snapshot(own_timeouts=[600])))          # 510 s ago: long enough
    assert "timeout" in kinds(run_alert(run_snapshot(rival_timeouts=[1100])))       # the rival's timeout is not ours


def test_the_window_is_configurable_and_the_limit_is_inclusive():
    cfg = RuleConfig(timeout_recent_s=100)
    assert "timeout" not in kinds(run_alert(run_snapshot(own_timeouts=[1010]), config=cfg))   # exactly 100 s
    assert "timeout" in kinds(run_alert(run_snapshot(own_timeouts=[1009]), config=cfg))       # 101 s
    assert "timeout" in kinds(run_alert(run_snapshot(own_timeouts=[1020]), config=RuleConfig(timeout_recent_s=0)))   # switched off


def test_no_alert_of_the_engine_proposes_a_timeout_right_after_one():
    """Whatever the rule, a recent own timeout means no ``timeout`` proposal in any alert of the engine."""
    for a in engine().evaluate(run_snapshot(own_timeouts=[1020])):
        assert "timeout" not in kinds(a), a.id
