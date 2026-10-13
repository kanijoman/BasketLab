"""Bug #234: re-emitted alerts never reached the screen.

The app drops any alert whose ``key`` it has already shown (``apps/live-android/src/ui/App.tsx``), but rules with
``rearm_s`` (fatigue, Four Factors lever, rival run, turnover streak) re-emitted under the SAME key. In Zamora-Leon
the engine emitted 27 alerts and the app showed 21; one of the hidden ones was Dembele's fatigue warning, the only
substitution proposal the coach followed. Every emission must carry a key never emitted before in the game.
"""
from pathlib import Path

from src.live_core.config import RuleConfig
from src.live_core.session import LiveSession
from tests.test_live_core_advice import BASE, OWN, _player, engine, snap

RECORDINGS = Path(__file__).parent / "recordings"
REARM = RuleConfig().fatigue_rearm_s


def _fatigue_keys(eng, elapsed, stint, minutes):
    players = {"p1": _player("Ana", OWN, stint=stint, minutes=minutes)}
    return [a.key for a in eng.evaluate(snap(elapsed=elapsed, players=players)) if a.id == "fatigue_high"]


def test_a_rearmed_alert_gets_a_new_key_regression():
    eng = engine(baselines=BASE)
    assert _fatigue_keys(eng, 1200, stint=720, minutes=1100) == ["fatigue:p1"]
    assert _fatigue_keys(eng, 1200 + REARM, stint=960, minutes=1400) == ["fatigue:p1#2"]
    assert _fatigue_keys(eng, 1200 + 2 * REARM, stint=1200, minutes=1700) == ["fatigue:p1#3"]


def test_nothing_is_re_emitted_inside_the_rearm_interval():
    eng = engine(baselines=BASE)
    _fatigue_keys(eng, 1200, stint=720, minutes=1100)
    assert _fatigue_keys(eng, 1200 + REARM - 10, stint=950, minutes=1390) == []


def test_every_alert_key_of_the_real_match_is_unique_regression():
    session = LiveSession((RECORDINGS / "2524470.package.json").read_text(encoding="utf-8"))
    session.load_recording((RECORDINGS / "2524470.rec.json.gz").read_bytes())
    keys = []
    for t in range(0, 7200, 30):
        result = session.play(t)
        if result["output"]:
            keys += [a["key"] for a in result["output"]["alerts"]]
    assert len(keys) == 27
    assert len(set(keys)) == len(keys), "the app would hide every alert whose key repeats"
