"""Advice engine: pure rules over the live snapshot, with dedupe and re-arm.

Perspective: alerts are for the OWN team (``own_team_id``); rival data produces
opportunities (info) rather than warnings.
"""

import pytest

from src.live_core.advice import Advice, AdviceEngine
from src.live_core.config import RuleConfig
from src.live_core.rules_rotation import fatigue_index

OWN, RIVAL = "T1", "T2"


def _player(name, team, pf=0, on_court=True, minutes=0, stint=0, pf_by_period=None):
    return {"name": name, "team_id": team, "on_court": on_court, "minutes": minutes,
            "stint": stint, "pf": pf, "pts": 0, "pf_by_period": pf_by_period or {}}


def snap(elapsed=600, period=1, players=None, fouls_by_period=None, log=None):
    fouls_by_period = fouls_by_period or {}
    return {
        "period": period, "remaining": 0, "elapsed": elapsed, "last_num": 1,
        "score": {OWN: 0, RIVAL: 0},
        "teams": {tid: {"name": tid, "fouls_game": sum(fouls_by_period.get(tid, {}).values()),
                        "timeouts": [], "fouls_by_period": fouls_by_period.get(tid, {}),
                        "stats": {}} for tid in (OWN, RIVAL)},
        "players": players or {}, "log": log or [],
    }


def engine(**kw):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, **kw)


def ids(advices):
    return [a.id for a in advices]


# --- foul trouble ------------------------------------------------------------------

def test_own_player_with_two_fouls_in_q1_gets_a_warning():
    out = engine().evaluate(snap(period=1, players={"p1": _player("Ana", OWN, pf=2)}))
    [a] = [a for a in out if a.id == "foul_trouble"]
    assert a.severity == "warning" and a.category == "faltas" and "Ana" in a.message
    assert a.evidence["pf"] == 2


def test_four_fouls_is_critical():
    out = engine().evaluate(snap(period=3, players={"p1": _player("Ana", OWN, pf=4)}))
    assert [a.severity for a in out if a.id == "foul_trouble"] == ["critical"]


def test_rival_foul_trouble_is_an_opportunity_not_a_warning():
    out = engine().evaluate(snap(period=1, players={"r1": _player("Rival Uno", RIVAL, pf=2)}))
    assert "foul_trouble" not in ids(out)
    [a] = [a for a in out if a.id == "rival_foul_trouble"]
    assert a.severity == "info" and "Rival Uno" in a.message


def test_same_alert_is_not_repeated_but_a_new_foul_is_new():
    eng = engine()
    players = {"p1": _player("Ana", OWN, pf=3)}
    assert eng.evaluate(snap(period=2, players=players))
    assert eng.evaluate(snap(period=2, players=players)) == []
    players["p1"]["pf"] = 4
    assert [a.severity for a in eng.evaluate(snap(period=2, players=players))] == ["critical"]


# --- team fouls --------------------------------------------------------------------

def test_own_team_at_four_fouls_in_the_period_warns_about_the_bonus():
    out = engine().evaluate(snap(period=2, fouls_by_period={OWN: {"2": 4}}))
    [a] = [a for a in out if a.id == "team_fouls_bonus"]
    assert a.severity == "warning" and a.evidence["team_fouls"] == 4


def test_three_team_fouls_is_not_enough_and_only_the_current_period_counts():
    assert "team_fouls_bonus" not in ids(engine().evaluate(snap(period=2, fouls_by_period={OWN: {"2": 3}})))
    assert "team_fouls_bonus" not in ids(engine().evaluate(snap(period=3, fouls_by_period={OWN: {"2": 5}})))


def test_bonus_warning_fires_again_in_a_new_period():
    eng = engine()
    assert "team_fouls_bonus" in ids(eng.evaluate(snap(period=2, fouls_by_period={OWN: {"2": 4}})))
    assert "team_fouls_bonus" in ids(eng.evaluate(snap(period=3, fouls_by_period={OWN: {"3": 4}})))


def test_rival_near_bonus_is_info():
    out = engine().evaluate(snap(period=1, fouls_by_period={RIVAL: {"1": 4}}))
    assert [a.severity for a in out if a.id == "rival_near_bonus"] == ["info"]


# --- scoring runs / turnovers ------------------------------------------------------

def _pts(t, team, v):
    return [t, team, "pts", v]


def test_unanswered_rival_run_is_critical_and_suggests_a_timeout():
    log = [_pts(1000, RIVAL, 3), _pts(1040, RIVAL, 2), _pts(1100, RIVAL, 3)]
    out = engine().evaluate(snap(elapsed=1110, log=log))
    [a] = [a for a in out if a.id == "rival_run"]
    assert a.severity == "critical" and "tiempo muerto" in a.message.lower()
    assert a.evidence["rival_points"] == 8 and a.evidence["own_points"] == 0


def test_run_requires_it_to_be_unanswered_and_recent():
    answered = [_pts(1000, RIVAL, 3), _pts(1040, RIVAL, 5), _pts(1050, OWN, 2)]
    assert "rival_run" not in ids(engine().evaluate(snap(elapsed=1110, log=answered)))
    too_slow = [_pts(800, RIVAL, 3), _pts(1000, RIVAL, 5)]
    assert "rival_run" not in ids(engine().evaluate(snap(elapsed=1110, log=too_slow)))


def test_four_own_turnovers_in_five_minutes_warns():
    four = [[1000 + 30 * i, OWN, "tov", 1] for i in range(4)]
    three = four[:3]
    assert "turnover_streak" in ids(engine().evaluate(snap(elapsed=1200, log=four)))
    assert "turnover_streak" not in ids(engine().evaluate(snap(elapsed=1200, log=three)))


def test_old_turnovers_do_not_count():
    old = [[100 + 30 * i, OWN, "tov", 1] for i in range(4)]
    assert "turnover_streak" not in ids(engine().evaluate(snap(elapsed=1200, log=old)))


# --- fatigue -----------------------------------------------------------------------

BASE = {"p1": {"avg_stint": 360, "avg_min": 1500, "p90_min": 2000}}


def test_fatigue_index_components_and_weights():
    index, parts = fatigue_index(stint=300, minutes=1200, elapsed=1200,
                                 baseline={"avg_stint": 360, "avg_min": 1500, "p90_min": 2000})
    assert parts["stint"] == pytest.approx(0.0, abs=0.01)
    assert parts["minutes"] == pytest.approx(1.0)
    assert parts["projection"] == pytest.approx(0.8)
    assert index == pytest.approx(55.0)


def test_fatigue_index_without_baseline_uses_stint_only():
    index, parts = fatigue_index(stint=840, minutes=700, elapsed=900, baseline=None)
    assert set(parts) == {"stint"} and index == pytest.approx(100.0)


def test_fatigue_alert_for_a_long_stint():
    players = {"p1": _player("Ana", OWN, stint=720, minutes=1100)}
    out = engine(baselines=BASE).evaluate(snap(elapsed=1200, players=players))
    [a] = [a for a in out if a.id == "fatigue_high"]
    assert a.severity == "warning" and a.category == "rotacion" and a.evidence["index"] >= 60


def test_no_fatigue_alert_for_a_short_stint_or_the_bench_or_the_rival():
    short = {"p1": _player("Ana", OWN, stint=400, minutes=500)}
    bench = {"p1": _player("Ana", OWN, on_court=False, stint=0, minutes=3000)}
    rival = {"r1": _player("Rival", RIVAL, stint=900, minutes=900)}
    for players in (short, bench, rival):
        assert "fatigue_high" not in ids(engine(baselines=BASE).evaluate(snap(elapsed=1200, players=players)))


def test_fatigue_reminder_after_the_rearm_period_while_still_high():
    eng = engine(baselines=BASE)
    players = {"p1": _player("Ana", OWN, stint=720, minutes=1100)}
    assert "fatigue_high" in ids(eng.evaluate(snap(elapsed=1200, players=players)))
    assert "fatigue_high" not in ids(eng.evaluate(snap(elapsed=1210, players=players)))
    later = 1200 + RuleConfig().fatigue_rearm_s
    players = {"p1": _player("Ana", OWN, stint=960, minutes=1400)}  # still on court, more minutes
    assert "fatigue_high" in ids(eng.evaluate(snap(elapsed=later, players=players)))


# --- ordering / config -------------------------------------------------------------

def test_critical_alerts_come_first():
    players = {"p1": _player("Ana", OWN, pf=4), "p2": _player("Eva", OWN, pf=2)}
    out = engine().evaluate(snap(period=1, players=players,
                                 fouls_by_period={OWN: {"1": 4}}))
    order = {"critical": 0, "warning": 1, "info": 2}
    assert [order[a.severity] for a in out] == sorted(order[a.severity] for a in out)


def test_thresholds_come_from_the_config():
    eng = engine(config=RuleConfig(turnover_streak=2))
    log = [[1000, OWN, "tov", 1], [1050, OWN, "tov", 1]]
    assert "turnover_streak" in ids(eng.evaluate(snap(elapsed=1100, log=log)))


def test_without_a_perspective_no_team_specific_rule_fires():
    eng = AdviceEngine(own_team_id=None)
    out = eng.evaluate(snap(players={"p1": _player("Ana", OWN, pf=4)}))
    assert out == []


def test_advice_is_a_plain_dataclass_with_json_friendly_fields():
    import dataclasses, json

    [a, *_] = engine().evaluate(snap(players={"p1": _player("Ana", OWN, pf=4)}))
    assert isinstance(a, Advice)
    json.dumps(dataclasses.asdict(a))


# --- integration with the real sample game -----------------------------------------

def _run_sample(feb_game_doc, own):
    from src.live_core.engine import LiveEngine
    from src.live_core.clock import period_and_remaining
    from src.live_core.replay import truncate_doc

    live, advice, emitted = LiveEngine(), AdviceEngine(own_team_id=own), []
    for elapsed in range(60, 2401, 30):
        period, remaining = period_and_remaining(elapsed - 1) if elapsed < 2400 else (4, 0)
        snapshot = live.update(truncate_doc(feb_game_doc, period, remaining))
        emitted.extend(advice.evaluate(snapshot))
    return emitted


def test_sample_game_alerts_make_basketball_sense(feb_game_doc):
    emitted = _run_sample(feb_game_doc, own="982047")
    once = [a.key for a in emitted if a.rearm_s is None]
    assert len(set(once)) == len(once), "a one-shot alert key was emitted twice"
    foul_alerts = [a for a in emitted if a.id == "foul_trouble"]
    assert foul_alerts and all(a.evidence["team_id"] == "982047" for a in foul_alerts)
    assert any(a.id == "foul_trouble" and a.severity == "critical" and "JANSSEN" in a.message for a in emitted)
    assert any(a.id == "team_fouls_bonus" and a.evidence["period"] == 2 for a in emitted)


def test_sample_game_rearmed_alerts_respect_their_interval(feb_game_doc):
    from src.live_core.config import RuleConfig

    emitted = _run_sample(feb_game_doc, own="982047")
    fatigue = [a for a in emitted if a.id == "fatigue_high"]
    assert fatigue, "the sample has long stints: at least one fatigue alert is expected"
    by_player = {}
    for a in fatigue:
        by_player.setdefault(a.evidence["player_id"], []).append(a)
    for alerts in by_player.values():
        assert all(a.evidence["index"] >= RuleConfig().fatigue_alert_index for a in alerts)


def test_sample_game_run_is_deterministic(feb_game_doc):
    first = [(a.key, a.severity, a.message) for a in _run_sample(feb_game_doc, own="982047")]
    second = [(a.key, a.severity, a.message) for a in _run_sample(feb_game_doc, own="982047")]
    assert first == second
