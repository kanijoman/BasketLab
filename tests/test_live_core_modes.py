"""Alert modes (issue #130): the staff does not tune thresholds, it picks how many alerts it wants.

Three modes: ``aggressive`` (more alerts, earlier), ``medium`` (the stock thresholds) and ``conservative`` (only what is clear). Each is a set of
``RuleConfig`` values we calibrate; the session applies it under the package's own ``rule_config`` (what the package says wins).
"""
from collections import Counter
from dataclasses import fields
from pathlib import Path

import pytest

from src.live_core.config import RuleConfig
from src.live_core.package import PreparationPackage
from src.live_core.modes import DEFAULT_MODE, MODES, mode_overrides
from src.live_core.session import LiveSession, start_json

RECORDINGS = Path(__file__).parent / "recordings"


def test_there_are_three_modes_and_medium_is_the_stock_configuration():
    assert set(MODES) == {"aggressive", "medium", "conservative"} and DEFAULT_MODE == "medium"
    assert mode_overrides("medium") == {}


def test_every_value_of_a_mode_is_a_real_setting_of_the_right_type():
    known = {f.name: f.type for f in fields(RuleConfig)}
    stock = RuleConfig()
    for name, values in MODES.items():
        for key, value in values.items():
            assert key in known, f"{name}: {key} is not a RuleConfig setting"
            assert isinstance(value, type(getattr(stock, key))), f"{name}: {key} has the wrong type"


def test_aggressive_is_more_sensitive_than_stock_and_conservative_less_in_every_setting():
    stock = RuleConfig()
    for key, value in MODES["aggressive"].items():
        assert value != getattr(stock, key) or key in MODES["conservative"], key
    # the same settings in both: a mode never changes a setting the other one leaves alone
    assert set(MODES["aggressive"]) == set(MODES["conservative"])
    for key in MODES["aggressive"]:
        low, mid, high = MODES["aggressive"][key], getattr(stock, key), MODES["conservative"][key]
        assert low != high and (low < mid < high or low > mid > high), f"{key}: {low} / {mid} / {high} is not ordered"


def test_an_unknown_mode_is_the_default_one():
    assert mode_overrides("loud") == {} and mode_overrides(None) == {}


def _alerts(mode):
    session = LiveSession((RECORDINGS / "2524470.package.json").read_text(encoding="utf-8"), mode=mode)
    session.load_recording((RECORDINGS / "2524470.rec.json.gz").read_bytes())
    found = []
    for t in range(0, 7200, 30):
        result = session.play(t)
        if result["output"]:
            found += result["output"]["alerts"]
    return found


def test_more_alerts_the_more_aggressive_the_mode_on_the_real_match():
    n = {mode: len(_alerts(mode)) for mode in MODES}
    assert n["aggressive"] > n["medium"] > n["conservative"] > 0, n


def test_the_conservative_mode_keeps_the_critical_alerts():
    critical = lambda mode: Counter(a["id"] for a in _alerts(mode) if a["severity"] == "critical")
    assert critical("conservative") and set(critical("conservative")) <= set(critical("medium")) | {"fatigue_high"}


def test_the_package_wins_over_the_mode():
    package = PreparationPackage.loads((RECORDINGS / "2524470.package.json").read_text(encoding="utf-8"))
    package.rule_config = {"fatigue_alert_index": 99.0}
    text = package.dumps()
    session = LiveSession(text, mode="aggressive")
    assert session._advice._ctx.config.fatigue_alert_index == 99.0                # the package
    assert session._advice._ctx.config.run_points == MODES["aggressive"]["run_points"]   # the mode


def test_the_session_entry_point_takes_the_mode_and_it_defaults_to_medium():
    text = (RECORDINGS / "2524470.package.json").read_text(encoding="utf-8")
    start_json(text)
    from src.live_core import session as module
    assert module._SESSION._advice._ctx.config == RuleConfig.from_dict(LiveSession(text).package.rule_config)
    start_json(text, "conservative")
    assert module._SESSION._advice._ctx.config.run_points == MODES["conservative"]["run_points"]


def test_the_mode_can_change_in_a_running_session_and_the_next_update_uses_it():
    text = (RECORDINGS / "2524470.package.json").read_text(encoding="utf-8")
    session = LiveSession(text)
    assert session._advice._ctx.config.run_points == RuleConfig().run_points
    session.set_mode("aggressive")
    assert session._advice._ctx.config.run_points == MODES["aggressive"]["run_points"]
    session.set_mode(None)
    assert session._advice._ctx.config.run_points == RuleConfig().run_points


def test_the_json_entry_point_changes_the_mode_of_the_started_session():
    from src.live_core import session as module
    start_json((RECORDINGS / "2524470.package.json").read_text(encoding="utf-8"))
    assert module.set_mode_json("conservative") == "{}"
    assert module._SESSION._advice._ctx.config.run_points == MODES["conservative"]["run_points"]
