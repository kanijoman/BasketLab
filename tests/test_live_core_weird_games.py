"""The weird games (issue #546, B3 of the testing strategy #540): real matches with an oddity the engine once got wrong, replayed the way the app lives them.

``tests/fixtures/weird_games/index.json`` says what is odd about each (and from which incident); the README explains how to add one. Every game is polled every 30 seconds
of the recording by ONE engine with ITS package, as the staff's tablet does, and gets:

* the invariants of the alerts (``tests/engine_invariants``: the same B1 checks, here on real data);
* the engine's own consistency: no failure, the same alerts on a second replay (determinism), each alert key said once, a duration that is what was played (#561);
* the probe of its oddity: the number that proves the game still has it (a fixture that lost its quirk would test nothing).
"""
from __future__ import annotations

import gzip
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from src.live_core.advice_types import Advice
from src.live_core.coherence import Coherence  # noqa: F401  (the invariants import it through the stance table)
from src.live_core.config import RuleConfig
from src.live_core.session import LiveSession
from tests.engine_invariants import check_coherence, check_flow_repeats, check_runs

ROOT = Path(__file__).resolve().parent
CATALOGUE = json.loads((ROOT / "fixtures" / "weird_games" / "index.json").read_text(encoding="utf-8"))
RECORDINGS = ROOT / "recordings"
POLL_S = 30


class Replay:
    """One pass over a recording: ``polls`` are ``(snapshot, alerts)`` of every poll that answered; ``gaps`` the polls FEB did not answer."""

    def __init__(self, polls: List[Tuple[Dict[str, Any], List[Advice]]], gaps: int, duration: float, own: str, rival: str, quality: Dict[str, Any], rival_tables: int) -> None:
        self.polls, self.gaps, self.duration, self.own, self.rival, self.quality, self.rival_tables = polls, gaps, duration, own, rival, quality, rival_tables


def play_through(code: str) -> Replay:
    package = (RECORDINGS / f"{code}.package.json").read_text(encoding="utf-8")
    session = LiveSession(package)
    session.load_recording((RECORDINGS / f"{code}.rec.json.gz").read_bytes())
    from src.live_core.package import PreparationPackage

    info = PreparationPackage.loads(package)
    polls, gaps, t = [], 0, 0.0
    quality: Dict[str, Any] = {}
    while t <= session._feed.duration:
        answer = session.play(t)
        t += POLL_S
        if answer["feed"] == "gap":
            gaps += 1
        if answer["feed"] != "ok":
            continue
        out = answer["output"]
        polls.append((out["snapshot"], [Advice(**a) for a in out["alerts"]]))
        quality = (out["snapshot"].get("possessions") or {}).get("quality") or quality
    return Replay(polls, gaps, session._feed.duration, str(info.team["id"]), str(info.rival["id"]), quality, len((info.tables or {}).get("rival_players") or {}))


@lru_cache(maxsize=None)
def replay(code: str) -> Replay:
    """The replay of a game, made once for all the tests of the module."""
    return play_through(code)


# --- the probes: the number that proves each oddity is still in the game ---------------------------------------------------------------------

def probe_feed_gaps(r: Replay, oddity: Dict[str, Any]) -> float:
    return r.gaps


def probe_log_lag_s(r: Replay, oddity: Dict[str, Any]) -> float:
    """The most the scoreboard clock was ahead of the last event of the log at a poll."""
    return max(snap["elapsed"] - max((e[0] for e in snap["log"]), default=0) for snap, _ in r.polls)


def probe_alternation_breaks(r: Replay, oddity: Dict[str, Any]) -> float:
    return r.quality.get("breaks_raw", 0)


def probe_short_recording(r: Replay, oddity: Dict[str, Any]) -> float:
    """1 when the recording lasts less than the real game would (it was compressed)."""
    return 1 if r.duration < 3600 else 0


def probe_no_rival_tables(r: Replay, oddity: Dict[str, Any]) -> float:
    """1 when the package has no table of the rival's players: the rival comes from another category (a cup game) and its season is not in the competition."""
    return 1 if r.rival_tables == 0 else 0


def probe_alert_count(r: Replay, oddity: Dict[str, Any]) -> float:
    return sum(1 for _, alerts in r.polls for a in alerts if a.id == oddity["alert"])


def probe_max_period(r: Replay, oddity: Dict[str, Any]) -> float:
    return max(snap["period"] for snap, _ in r.polls)


PROBES = {"no_rival_tables": probe_no_rival_tables, "alert_count": probe_alert_count, "max_period": probe_max_period, "feed_gaps": probe_feed_gaps, "log_lag_s": probe_log_lag_s, "alternation_breaks": probe_alternation_breaks, "short_recording": probe_short_recording}
GAMES = [pytest.param(g, id=g["id"]) for g in CATALOGUE["games"]]


# --- every weird game keeps the invariants of the engine -------------------------------------------------------------------------------------

@pytest.mark.parametrize("game", GAMES)
def test_the_alerts_of_a_real_game_keep_every_invariant(game):
    r = replay(game["code"])
    window, said, last = RuleConfig().conflict_window_s, {}, {}
    for snap, alerts in r.polls:
        check_runs(snap, alerts, r.own, r.rival)
        check_flow_repeats(snap, alerts, said, r.rival)
        check_coherence(snap, alerts, last, window)


@pytest.mark.parametrize("game", GAMES)
def test_a_real_game_replays_the_same_and_says_each_alert_once(game):
    first, second = replay(game["code"]), play_through(game["code"])      # the second one is an independent pass
    keys = [[a.key for a in alerts] for _, alerts in first.polls]
    assert keys == [[a.key for a in alerts] for _, alerts in second.polls], "the same recording gave different alerts"
    flat = [k for poll in keys for k in poll]
    assert len(flat) == len(set(flat)), f"keys said twice: {sorted({k for k in flat if flat.count(k) > 1})}"


@pytest.mark.parametrize("game", GAMES)
def test_the_duration_of_a_finished_real_game_is_what_was_played_issue_561(game):
    """A game that ends with ``Fin del Cuarto 4`` at 40:00, also the start of the 5th period, lasts 2400 s, not 2700; one that played an overtime lasts 2700 s."""
    from src.live_core.recorded_feed import RecordedFeed

    feed = RecordedFeed.loads(gzip.open(RECORDINGS / f"{game['code']}.rec.json.gz").read().decode())
    session = LiveSession((RECORDINGS / f"{game['code']}.package.json").read_text(encoding="utf-8"))
    assert session.load_replay(feed.document_at(10**9))["duration"] == 2400 + 300 * (game.get("periods", 4) - 4)


# --- every oddity is still there ---------------------------------------------------------------------------------------------------------------

ODDITIES = [pytest.param(g, o, id=f"{g['id']}-{o['probe']}") for g in CATALOGUE["games"] for o in g["oddities"]]


@pytest.mark.parametrize("game, oddity", ODDITIES)
def test_the_fixture_still_has_the_oddity_it_is_kept_for(game, oddity):
    measured = PROBES[oddity["probe"]](replay(game["code"]), oddity)
    assert measured >= oddity["at_least"], f"{game['id']}: {oddity['probe']} = {measured} (< {oddity['at_least']}): «{oddity['what']}» is not in this game any more"


def test_the_catalogue_names_real_files_and_known_probes():
    for game in CATALOGUE["games"]:
        for name in (f"{game['code']}.rec.json.gz", f"{game['code']}.package.json"):
            assert (RECORDINGS / name).is_file(), name
        for oddity in game["oddities"]:
            assert oddity["probe"] in PROBES and oddity["issues"] and oddity["what"], oddity
        assert game["oddities"] or game.get("regression_only"), f"{game['id']}: no oddity: say why it is here (regression_only)"


def test_an_overtime_is_played_to_its_end_and_the_engine_keeps_saying_things():
    """The game with an overtime (Getafe - Cultural): the last poll is in the 5th period at its 0:00, and the 5th period has polls with alerts evaluated."""
    r = replay("2536139")
    last_snap, _ = r.polls[-1]
    assert last_snap["period"] == 5 and last_snap["elapsed"] == 2700
    assert sum(1 for snap, _ in r.polls if snap["period"] == 5) >= 8             # every 30 s of a 5-minute period
