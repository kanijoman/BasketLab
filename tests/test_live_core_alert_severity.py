"""Alert hierarchy (issue #229): severity is the urgency for the staff, so the list has a real order.

critical = act now (4th foul, rival run) · warning = consider acting (3rd foul, turnovers, bonus, hot rival player,
very high fatigue) · info = context (moderate fatigue, Four Factors lever, rival zones, rival fouls/bonus).
Thresholds live in RuleConfig ("a confirmar con el staff").
"""
import gzip
import json
from collections import Counter
from pathlib import Path

import pytest

from src.live_core.config import RuleConfig
from src.live_core.session import LiveSession
from tests.test_live_core_advice import BASE, OWN, RIVAL, _player, _stats, engine, ff_snap, snap

RECORDINGS = Path(__file__).parent / "recordings"


def _fatigue(stint):
    players = {"p1": _player("Ana", OWN, stint=stint, minutes=1100)}
    return [a for a in engine(baselines=BASE).evaluate(snap(elapsed=1200, players=players)) if a.id == "fatigue_high"]


def test_moderate_fatigue_is_context_not_a_warning():
    [a] = _fatigue(600)
    assert 60 <= a.evidence["index"] < RuleConfig().fatigue_warning_index
    assert a.severity == "info"


def test_very_high_fatigue_is_a_warning():
    [a] = _fatigue(720)
    assert a.evidence["index"] >= RuleConfig().fatigue_warning_index
    assert a.severity == "warning"


def test_the_fatigue_warning_threshold_is_configurable():
    players = {"p1": _player("Ana", OWN, stint=600, minutes=1100)}
    eng = engine(baselines=BASE, config=RuleConfig(fatigue_warning_index=65.0))
    [a] = [a for a in eng.evaluate(snap(elapsed=1200, players=players)) if a.id == "fatigue_high"]
    assert a.severity == "warning"


def test_the_four_factors_lever_is_context():
    out = engine().evaluate(ff_snap(_stats(tov=22), _stats()))
    assert [a.severity for a in out if a.id == "four_factors_lever"] == ["info"]


def test_only_the_fourth_foul_and_the_rival_run_are_critical():
    third = engine().evaluate(snap(period=3, players={"p1": _player("Ana", OWN, pf=3)}))
    fourth = engine().evaluate(snap(period=3, players={"p1": _player("Ana", OWN, pf=4)}))
    assert [a.severity for a in third if a.id == "foul_trouble"] == ["warning"]
    assert [a.severity for a in fourth if a.id == "foul_trouble"] == ["critical"]
    run = engine().evaluate(snap(elapsed=1110, log=[[1000, RIVAL, "pts", 3], [1040, RIVAL, "pts", 2], [1100, RIVAL, "pts", 3]]))
    assert [a.severity for a in run if a.id == "rival_run"] == ["critical"]


def test_the_real_match_has_a_useful_distribution_regression():
    """Before #229 the 28 alerts of Zamora-Leon were about 1 critical / 18 warning / 7 info: all orange."""
    session = LiveSession((RECORDINGS / "2524470.package.json").read_text(encoding="utf-8"))
    session.load_recording((RECORDINGS / "2524470.rec.json.gz").read_bytes())
    alerts = []
    for t in range(0, 7200, 30):
        result = session.play(t)
        if result["output"]:
            alerts += result["output"]["alerts"]
    counts = Counter(a["severity"] for a in alerts)
    assert (counts["critical"], counts["warning"], counts["info"]) == (1, 10, 20)  # +4 info: rest in the decided stretch (#273); Zamora lost by 20+
