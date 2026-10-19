"""Fatigue during a timeout (issue #400).

FEB writes the substitutions of a stoppage AFTER the ``timeout`` line (same clock, consecutive ``num``), and a poll can land
between them: the engine still has the old five on court, so a fatigue alert named a player who was already on the bench
(Carla Celaya, end of Q2). While the stoppage is open (the latest event is a timeout of the same game second) the rule waits
for the substitutions; the alert is not lost, it comes with the next event if the player is still on court.
"""
from pathlib import Path

from src.live_core.session import LiveSession
from tests.test_live_core_advice import BASE, OWN, RIVAL, _player, engine, snap

RECORDINGS = Path(__file__).parent / "recordings"


def _fatigue(log):
    players = {"p1": _player("Ana", OWN, stint=720, minutes=1100)}
    return [a for a in engine(baselines=BASE).evaluate(snap(elapsed=1200, players=players, log=log)) if a.id == "fatigue_high"]


def test_fatigue_waits_while_a_timeout_is_open_regression():
    assert _fatigue([[1200, OWN, "timeout", 1, None]]) == []
    assert _fatigue([[1200, RIVAL, "timeout", 1, None]]) == []


def test_fatigue_is_said_once_the_game_goes_on():
    assert len(_fatigue([[1100, OWN, "timeout", 1, None]])) == 1
    assert len(_fatigue([])) == 1


def test_waiting_does_not_lose_the_alert():
    eng = engine(baselines=BASE)
    players = {"p1": _player("Ana", OWN, stint=720, minutes=1100)}
    during = eng.evaluate(snap(elapsed=1200, players=players, log=[[1200, OWN, "timeout", 1, None]]))
    after = eng.evaluate(snap(elapsed=1215, players=players, log=[[1200, OWN, "timeout", 1, None]]))
    assert not [a for a in during if a.id == "fatigue_high"]
    assert [a for a in after if a.id == "fatigue_high"]


def test_no_fatigue_alert_on_the_recorded_match_names_a_player_who_is_about_to_leave():
    """Zamora-Leon: the polls that caught a timeout without its substitutions raised fatigue alerts (t=2255, 2560, 5590, 5740...)."""
    session = LiveSession((RECORDINGS / "2524470.package.json").read_text(encoding="utf-8"))
    session.load_recording((RECORDINGS / "2524470.rec.json.gz").read_bytes())
    at_timeout = []
    for t in range(0, 7200, 5):
        out = session.play(t)["output"]
        if not out:
            continue
        snapshot = out["snapshot"]
        open_stoppage = any(e[2] == "timeout" and e[0] == snapshot["elapsed"] for e in snapshot["log"])
        at_timeout += [a for a in out["alerts"] if a["id"] == "fatigue_high" and open_stoppage]
    assert at_timeout == []
