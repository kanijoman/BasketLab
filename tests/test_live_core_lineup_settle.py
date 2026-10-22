"""Alerts about who is on court wait while a stoppage is going on (issue #413).

FEB writes the substitutions of a stoppage some seconds AFTER the dead ball, with the clock of the stoppage (Leon-Unibasket: the timeout of
Q2 at 19:12:40, its substitutions at 19:14:01; fouls and free throws the same). A poll in between sees the old five on court, and an alert
about who plays (fatigue, lineup, plus/minus, rest) names someone who has already left. #400 held the fatigue alert while a timeout was the
last event; this generalises it: while the last event is a stoppage (timeout, foul, free throw, substitution, end of period) those rules say
nothing. The alert is not lost: its key is only stored when it is emitted, so it comes with the first live event if it is still true.
What cannot be seen is a plain lag: the lines of the real feed come 10-50 s after the header clock all the time, so a clock that runs
ahead of the last line says nothing (holding on it silenced half of the alerts for minutes), and neither does a clock that stands still
(the first poll of a dead ball still sees the clock running).
"""
import copy
from pathlib import Path

import pytest

from src.live_core.events import parse_line
from src.live_core.package import PreparationPackage
from src.live_core.recorded_feed import RecordedFeed
from src.live_core.session import LiveSession
from src.live_core.state import LiveGame
from tests.test_live_core_rule_registry import SCENARIOS, _engine

RECORDINGS = Path(__file__).parent / "recordings"
LINEUP_RULES = ("fatigue_high", "player_plus_minus", "lineup_net", "rest_starters", "formation_lineup")   # #481: the formation rule too
STOPPAGES = ("timeout", "foul", "ft", "sub_in", "sub_out", "period_end")


def with_last_event(snapshots, kind, ago=0):
    """The scenario's snapshot(s) saying that their last event was ``kind``, ``ago`` game-seconds before the game clock."""
    out = []
    for s in snapshots if isinstance(snapshots, list) else [snapshots]:
        s = copy.deepcopy(s)
        s["last_event"] = {"kind": kind, "elapsed": s["elapsed"] - ago}
        out.append(s)
    return out


def moved(snapshots, seconds):
    """The same snapshots ``seconds`` later: the clock runs between polls, as it does in a live match (a clock that stands still is held)."""
    out = []
    for s in snapshots:
        s = copy.deepcopy(s)
        s["elapsed"] += seconds
        if s.get("last_event"):
            s["last_event"]["elapsed"] += seconds
        for p in s.get("players", {}).values():
            if p.get("on_court"):
                p["stint"] = p.get("stint", 0) + seconds             # who is on court keeps playing: the stint (and so the key) is the same one
                p["minutes"] = p.get("minutes", 0) + seconds
        out.append(s)
    return out


def emitted(rule_id, snapshots, polls=3):
    """The ids a live engine says over ``polls`` polls (a lineup alert of a live feed needs two in a row), the clock running a second each."""
    _build, _emits, kw = SCENARIOS[rule_id]
    engine = _engine(**kw)
    ids = set()
    for k in range(polls):
        for s in moved(snapshots, k):
            ids |= {a.id for a in engine.evaluate(s)}
    return ids


@pytest.mark.parametrize("rule_id", LINEUP_RULES)
@pytest.mark.parametrize("kind", STOPPAGES)
def test_a_stoppage_as_the_last_event_holds_the_alerts_about_the_lineup_regression(rule_id, kind):
    build, wanted, _kw = SCENARIOS[rule_id]
    assert wanted <= emitted(rule_id, with_last_event(build(), "rebound")), "the scenario must fire when the lineup is settled"
    assert not (wanted & emitted(rule_id, with_last_event(build(), kind)))


@pytest.mark.parametrize("rule_id", LINEUP_RULES)
def test_a_live_event_settles_it_and_a_snapshot_without_last_event_is_not_held(rule_id):
    build, wanted, _kw = SCENARIOS[rule_id]
    for kind in ("shoot", "rebound", "turnover", "fg2", "other"):
        assert wanted <= emitted(rule_id, with_last_event(build(), kind))
    assert wanted <= emitted(rule_id, [s for s in (build() if isinstance(build(), list) else [build()])])


def test_the_lag_between_the_clock_and_the_lines_is_not_a_stoppage_regression():
    """Found measuring #413: the lines of the real feed come 10-50 s after the header clock all the time; holding on that lag silenced the
    rest alerts for minutes."""
    build, wanted, kw = SCENARIOS["fatigue_high"]
    [lagging] = with_last_event(build(), "rebound", ago=45)
    assert wanted <= emitted("fatigue_high", [lagging])


def test_what_was_held_comes_with_the_first_live_event_and_is_not_lost():
    build, wanted, kw = SCENARIOS["fatigue_high"]
    engine = _engine(**kw)
    [stopped] = with_last_event(build(), "foul")
    fired = lambda snapshot: [a for a in engine.evaluate(snapshot) if a.id in wanted]  # noqa: E731
    assert not fired(stopped) and not fired(copy.deepcopy(stopped))                  # a poll that brings nothing new says nothing either
    running = copy.deepcopy(stopped)
    running["last_event"] = {"kind": "rebound", "elapsed": running["elapsed"]}
    assert fired(moved([running], 10)[0])                                              # the ball is alive and it is still true: it comes


def test_a_player_who_left_in_the_late_lines_is_never_alerted():
    build, wanted, kw = SCENARIOS["fatigue_high"]
    engine = _engine(**kw)
    [stopped] = with_last_event(build(), "timeout")
    fired = lambda snapshot: [a for a in engine.evaluate(snapshot) if a.id in wanted]  # noqa: E731
    assert not fired(stopped)
    after = moved([stopped], 10)[0]
    after["last_event"]["kind"] = "rebound"
    for p in after["players"].values():
        p["on_court"] = False                                                          # the substitutions arrived: nobody is fatigued on court
    assert not fired(after)


def test_an_illegal_lineup_is_not_said_in_the_middle_of_a_block_of_substitutions_regression():
    """#481 (Copa 21/10/2026): a block of substitutions is several lines written one after the other. The formación player who comes in for
    a formación player arrives after the non-formación one who comes in for another: in between, the five on court look illegal for a
    moment. The lineup is evaluated at the next play, when the whole block is written."""
    build, wanted, kw = SCENARIOS["formation_lineup"]
    engine = _engine(**kw)
    fired = lambda snapshot: {a.id for a in engine.evaluate(snapshot)} & wanted  # noqa: E731
    mid_block = with_last_event(build(), "sub_in")
    assert not any(fired(s) for k in range(3) for s in moved(mid_block, k))             # the block is still being written: nothing is said
    assert not any(fired(s) for k in range(3) for s in moved(with_last_event(build(), "timeout"), k))


def test_an_illegal_lineup_that_is_still_there_at_the_next_play_is_said():
    build, wanted, kw = SCENARIOS["formation_lineup"]
    assert wanted <= emitted("formation_lineup", with_last_event(build(), "rebound"))


# --- the game says what its last event was ---------------------------------------------------------------------------------------

def test_the_snapshot_carries_the_last_event_of_the_game():
    game = LiveGame([("1", "A"), ("2", "B")], {})
    assert game.snapshot()["last_event"] is None
    feed = RecordedFeed.loads((RECORDINGS / "2524470.rec.json.gz").read_bytes())
    lines = feed.document_at(feed.duration)["PLAYBYPLAY"]["LINES"]
    events = sorted((e for e in map(parse_line, lines) if e and not e.deleted), key=lambda e: e.num)
    for event in events[:30]:
        game.apply(event)
    last = game.snapshot()["last_event"]
    assert last["kind"] == events[29].kind and last["elapsed"] == events[29].elapsed


def test_the_last_event_carries_the_text_of_the_line_for_the_app_issue_490():
    """The app shows the last text received from the feed under the scoreboard (feedback of 0.3.2)."""
    game = LiveGame([("1", "A"), ("2", "B")], {})
    feed = RecordedFeed.loads((RECORDINGS / "2524470.rec.json.gz").read_bytes())
    lines = feed.document_at(feed.duration)["PLAYBYPLAY"]["LINES"]
    events = sorted((e for e in map(parse_line, lines) if e and not e.deleted), key=lambda e: e.num)
    for event in events[:40]:
        game.apply(event)
    last = game.snapshot()["last_event"]
    assert last["text"] == events[39].text and last["text"]
    assert last["period"] == events[39].period and last["remaining"] == events[39].remaining and last["team_id"] == events[39].team_id


# --- the real match ---------------------------------------------------------------------------------------------------------------

def package_for(rival):
    package = PreparationPackage.loads((RECORDINGS / "2524470.package.json").read_text(encoding="utf-8"))
    if rival:
        package.rival = rival
    # about the timing of the alerts, not their thresholds: the floors and the minimum sample of fatigue (#479) are off here
    package.rule_config = {**package.rule_config, **{"fatigue_min_games": 0, "fatigue_min_stints": 0, "fatigue_floor_warning_s": 0, "fatigue_floor_critical_s": 0}}
    return package.dumps()


def lineup_alerts(recording, rival=None):
    """(rule id, kind of the last event of the snapshot it came with) of every alert about who plays in a replay of the recorded match."""
    session = LiveSession(package_for(rival))
    session.load_recording((RECORDINGS / recording).read_bytes())
    found = []
    for t in range(0, 8000, 5):
        out = session.play(t)["output"]
        found += [(a["id"], out["snapshot"]["last_event"]["kind"]) for a in (out["alerts"] if out else []) if a["id"] in LINEUP_RULES]
    return found


def test_no_alert_about_the_lineup_comes_with_a_stoppage_as_the_last_event_in_the_real_matches_regression():
    for recording, rival in (("2524475.rec.json.gz", {"id": "1008895", "name": "BOSONIT UNIBASKET"}), ("2524470.rec.json.gz", None)):
        found = lineup_alerts(recording, rival)
        assert len(found) > 5, "the replay must raise alerts about the lineup for the check to mean something"
        assert [f for f in found if f[1] in STOPPAGES] == []
