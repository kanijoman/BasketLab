"""Bug #234: re-emitted alerts never reached the screen.

The app drops any alert whose ``key`` it has already shown (``apps/live-android/src/ui/App.tsx``), but rules with
``rearm_s`` (fatigue, Four Factors lever, rival run, turnover streak) re-emitted under the SAME key. In Zamora-Leon
the engine emitted 27 alerts and the app showed 21; one of the hidden ones was Dembele's fatigue warning, the only
substitution proposal the coach followed. Every emission must carry a key never emitted before in the game.

Since #241 those rules no longer repeat by time, but the engine still supports ``rearm_s`` (the illegal-lineup alert uses it):
the mechanism is tested here with a rule that re-arms every ``REARM`` seconds.
"""
from pathlib import Path

from src.live_core.advice import Advice
from src.live_core.session import LiveSession
from tests.test_live_core_advice import engine, snap

RECORDINGS = Path(__file__).parent / "recordings"
REARM = 240


def _rearming_engine(monkeypatch):
    """An engine whose only rule says the same thing again every REARM game-seconds."""
    rule = lambda s, ctx: [Advice(key="slow", id="fake", severity="warning", category="gestion", message="m", rearm_s=REARM)]  # noqa: E731
    monkeypatch.setattr("src.live_core.advice.RULES", [("fake", rule)])
    return engine()


def _keys(eng, elapsed):
    return [a.key for a in eng.evaluate(snap(elapsed=elapsed))]


def test_a_rearmed_alert_gets_a_new_key_regression(monkeypatch):
    eng = _rearming_engine(monkeypatch)
    assert _keys(eng, 1200) == ["slow"]
    assert _keys(eng, 1200 + REARM) == ["slow#2"]
    assert _keys(eng, 1200 + 2 * REARM) == ["slow#3"]


def test_nothing_is_re_emitted_inside_the_rearm_interval(monkeypatch):
    eng = _rearming_engine(monkeypatch)
    _keys(eng, 1200)
    assert _keys(eng, 1200 + REARM - 10) == []


def test_every_alert_key_of_the_real_match_is_unique_regression():
    session = LiveSession((RECORDINGS / "2524470.package.json").read_text(encoding="utf-8"))
    session.load_recording((RECORDINGS / "2524470.rec.json.gz").read_bytes())
    keys = []
    for t in range(0, 7200, 30):
        result = session.play(t)
        if result["output"]:
            keys += [a["key"] for a in result["output"]["alerts"]]
    assert len(keys) == 101   # the table is in test_live_core_alert_severity.py (#316/#320 changed it: fatigue credit for timeouts, decided game)
    assert len(set(keys)) == len(keys), "the app would hide every alert whose key repeats"
