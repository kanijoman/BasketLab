"""Invariants of the live engine on generated games (issue #544, phase B1 of the testing strategy #540).

Every example is a match played event by event through the real state machine (``tests/builders.Match``: only states the engine can reach), polled
like the app does, every few events, with ONE engine that keeps its memory. Each invariant comes from a bug the staff found; Hypothesis shrinks a
counterexample to the shortest match that breaks it.

* #515: a run (parcial) counts only points of the quarter in play.
* #517: a flow alert said again counts only what happened after it was said the last time.
* #568: an alert that takes the opposite stance of the last one said on its topic, within ``conflict_window_s``, says that it changes what was said.
* #561: a finished game lasts what it played, with or without the closing line ``Fin del Cuarto N``.

Profiles: ``ci`` (default: derandomized, the same examples every run, so the CI does not flake) and ``explore`` (``HYPOTHESIS_PROFILE=explore``:
random and many more examples, to look for new counterexamples by hand).
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.live_core.advice import AdviceEngine
from src.live_core.clock import period_length, period_start
from src.live_core.coherence import stance_of
from src.live_core.config import RuleConfig
from src.live_core.session import LiveSession
from src.live_core.vectors import unwrap_extended_json
from tests.builders import OWN, RIVAL, Match

settings.register_profile("ci", max_examples=40, deadline=None, derandomize=True, suppress_health_check=[HealthCheck.too_slow])
settings.register_profile("explore", max_examples=500, deadline=None, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

ROOT = Path(__file__).resolve().parents[1]
PLAYERS = {OWN: [f"p{i}" for i in range(1, 11)], RIVAL: [f"r{i}" for i in range(1, 11)]}
ACTIONS = ("score", "score", "miss", "turnover", "foul", "timeout", "sub", "quiet")


# --- the generated match ------------------------------------------------------------------------------------------------------------------

# a step: (wait in s, action, team, a pick for who and what, how many times in a row): the repeats make the streaks the rules look for (a run, three
# turnovers in a row, offensive rebounds), which a fresh coin per action almost never draws
steps = st.lists(st.tuples(st.integers(1, 45), st.sampled_from(ACTIONS), st.sampled_from((OWN, RIVAL)), st.integers(0, 99), st.integers(1, 4)),
                 min_size=20, max_size=160)
polls = st.integers(2, 8)
REPEAT_GAP = 6


class Played:
    """A match being played from generated steps, with who is on court and the fouls and timeouts of each side (to stay a real game)."""

    def __init__(self) -> None:
        self.match = Match()
        self.on_court = {team: players[:5] for team, players in PLAYERS.items()}
        self.fouls: Dict[str, int] = {}
        self.timeouts = {OWN: 0, RIVAL: 0}
        for team, five in self.on_court.items():
            self.match.lineup(team, five, at=0)

    def _other(self, team: str) -> str:
        return RIVAL if team == OWN else OWN

    def _sub(self, team: str, out: str, at: int, pick: int) -> None:
        bench = [p for p in PLAYERS[team] if p not in self.on_court[team] and self.fouls.get(p, 0) < 5]
        into = bench[pick % len(bench)]
        self.on_court[team] = [into if p == out else p for p in self.on_court[team]]
        self.match.substitution(team, out, into, at=at)

    def act(self, action: str, team: str, pick: int, at: int) -> None:
        m, five, other = self.match, self.on_court[team], self._other(team)
        player = five[pick % 5]
        if action == "score":
            m.score(team, (1, 2, 2, 3)[pick % 4], at=at, player=player)
        elif action == "miss":
            m.miss(team, at=at, kind=("fg2", "fg3")[pick % 2], player=player)
            rebounder = team if pick % 3 == 0 else other              # a third of the misses are offensive rebounds
            m.rebound(rebounder, at=at, player=self.on_court[rebounder][pick % 5])
        elif action == "turnover":
            m.turnover(team, at=at, player=player)
            if pick % 2:
                m.steal(other, at=at, player=self.on_court[other][pick % 5])
        elif action == "foul":
            self.fouls[player] = self.fouls.get(player, 0) + 1
            m.foul(team, player, at=at, drawn_by=self.on_court[other][pick % 5])
            if self.fouls[player] == 5:
                self._sub(team, player, at, pick)                        # fouled out
        elif action == "timeout" and self.timeouts[team] < 5:
            self.timeouts[team] += 1
            m.timeout(team, at=at)
        elif action == "sub":
            self._sub(team, player, at, pick)


def play(generated: List[Tuple[int, str, str, int, int]], every: int) -> Iterator[Tuple[Dict[str, Any], list]]:
    """Play the match and yield ``(snapshot, alerts)`` at every poll of ONE engine (every ``every`` steps and at the end of each quarter)."""
    game, engine, period, at = Played(), AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL), 1, 0
    for i, (wait, action, team, pick, repeat) in enumerate(generated, start=1):
        end = period_start(period) + period_length(period)
        if at + wait + REPEAT_GAP * (repeat - 1) >= end:                 # the quarter is over before this step
            game.match.period_end(period)
            snap = game.match.snapshot()
            yield snap, engine.evaluate(snap)
            if period == 4:
                return
            period, at = period + 1, end
        for k in range(repeat):
            at += wait if k == 0 else REPEAT_GAP
            game.act(action, team, pick + k, at)
        if i % every == 0:
            snap = game.match.snapshot()
            yield snap, engine.evaluate(snap)


# --- the invariants -----------------------------------------------------------------------------------------------------------------------

def _points(log: list, team: str, start: int, end: int) -> int:
    return sum(e[3] for e in log if e[1] == team and e[2] == "pts" and start <= e[0] <= end)


def check_runs(snap: Dict[str, Any], alerts: list) -> None:
    """#515: a run counts no point the team scored before the quarter in play began."""
    now, start, log = snap["elapsed"], period_start(snap["period"]), snap["log"]
    own, rival = _points(log, OWN, start, now), _points(log, RIVAL, start, now)
    for a in alerts:
        if a.id == "rival_run":
            assert a.evidence["rival_points"] <= rival and a.evidence["own_points"] <= own, f"#515 {a.message} (en el cuarto: {own}-{rival})"
        elif a.id == "own_run":
            assert a.evidence["net"] <= own, f"#515 {a.message} (el equipo lleva {own} en el cuarto)"
        elif a.id == "long_run":
            assert a.evidence["net"] <= rival, f"#515 {a.message} (el rival lleva {rival} en el cuarto)"


FLOW_COUNTS = {"rival_turnovers": ("turnovers", "tov"), "rival_orb_window": ("orb", "orb")}


def check_flow_repeats(snap: Dict[str, Any], alerts: list, said: Dict[str, int]) -> None:
    """#517: a flow alert said again counts only events after the last time it was said."""
    now = snap["elapsed"]
    for a in alerts:
        if a.id not in FLOW_COUNTS:
            continue
        field, kind = FLOW_COUNTS[a.id]
        if a.id in said:
            new = sum(1 for e in snap["log"] if e[1] == RIVAL and e[2] == kind and said[a.id] < e[0] <= now)
            assert a.evidence[field] <= new, f"#517 #619 {a.message} (dicho antes a los {said[a.id]} s; nuevos desde entonces: {new})"
        said[a.id] = now


CHANGES = "Cambia lo dicho antes"


def check_coherence(snap: Dict[str, Any], alerts: list, last: Dict[str, Tuple[str, int]], window: int) -> None:
    """#568: a poll that turns a topic to the opposite of the last stance said on it within the window (or says both stances at once) says that it
    changes what was said, in one of its alerts: once the change is said, the alerts after it in the same poll agree with it (five «riesgo de
    fatiga» after a «no romper el quinteto»: the first one carries the note)."""
    now = snap["elapsed"]
    stances = [(a, s) for a, s in ((a, stance_of(a)) for a in alerts) if s]
    for topic in {s[0] for _, s in stances}:
        here = [(a, s) for a, s in stances if s[0] == topic]
        before = last.get(topic)
        turns = bool(before) and now - before[1] < window and any(s[1] != before[0] for _, s in here)
        if turns or len({s[1] for _, s in here}) > 1:
            assert any(CHANGES in a.message for a, _ in here), (
                f"#568 {[a.message for a, _ in here]} contradice lo dicho a los {before[1] if before else now} s sin decirlo")
        newest = next((s for a, s in here if CHANGES in a.message), here[-1][1])
        last[topic] = (newest[1], now)


# Only what moves the flow alerts: rival turnovers and offensive rebounds (a miss of the rival with pick 0 is its own rebound) in streaks, rival
# timeouts (a new episode) and quiet stretches. A general match rarely lines up «an event at the second of a poll, a new episode, four more in the
# window», which is what #619 needed.
flow_steps = st.lists(st.tuples(st.integers(1, 40), st.sampled_from(("turnover", "turnover", "miss", "timeout", "quiet")), st.just(RIVAL),
                                 st.just(0), st.integers(1, 4)), min_size=5, max_size=80)


@given(flow_steps, polls)
def test_a_flow_alert_said_again_counts_only_what_came_after(generated, every):
    """#517, #619: the flow alerts on streaks of the rival, polled at any moment, never count an event twice."""
    said: Dict[str, int] = {}
    for snap, alerts in play(generated, every):
        check_flow_repeats(snap, alerts, said)


@given(steps, polls)
def test_the_engine_keeps_its_invariants_on_any_reachable_match(generated, every):
    """The three invariants of the alerts at every poll of a generated match (and the engine never fails on it)."""
    window = RuleConfig().conflict_window_s
    said: Dict[str, int] = {}
    last: Dict[str, Tuple[str, int]] = {}
    for snap, alerts in play(generated, every):
        check_runs(snap, alerts)
        check_flow_repeats(snap, alerts, said)
        check_coherence(snap, alerts, last, window)


# --- #561: the duration of a finished game -------------------------------------------------------------------------------------------------

GAME = unwrap_extended_json(json.loads((ROOT / "src/JSON_samples/feb_game.json").read_text(encoding="utf-8")))
PACKAGE = json.loads((ROOT / "tests/live_vectors/vectors.json").read_text(encoding="utf-8"))["engine"]["package"]
SHOT = next(ln for ln in GAME["PLAYBYPLAY"]["LINES"] if ln.get("action") == "shoot")
CLOSE = next(ln for ln in GAME["PLAYBYPLAY"]["LINES"] if ln.get("action") == "period")


@given(st.integers(1, 6), st.lists(st.integers(0, 599), min_size=1, max_size=12), st.booleans())
def test_a_finished_game_lasts_what_it_played_with_or_without_its_closing_line(played, clocks, closing_line):
    """#561: the review of a game that ended in period ``played`` lasts up to the end of that period (the line ``Fin del Cuarto N`` at 00:00 is the
    end of N, also the start of N + 1: it is no overtime)."""
    lines = []
    for period in range(1, played + 1):
        for left in sorted(clocks, reverse=True)[: 1 + period % 3]:
            lines.append({**copy.deepcopy(SHOT), "quarter": str(period), "time": f"{left // 60:02d}:{left % 60:02d}"})
    if closing_line:
        lines.append({**copy.deepcopy(CLOSE), "quarter": str(played), "time": "00:00", "text": f"Fin del Cuarto {played}", "logParam1": str(played)})
    for n, line in enumerate(lines, start=1):
        line["num"] = str(n)
    doc = {**GAME, "PLAYBYPLAY": {**GAME["PLAYBYPLAY"], "LINES": lines}}
    session = LiveSession(PACKAGE)
    duration = session.load_replay(doc)["duration"]
    latest = max(period_start(int(ln["quarter"])) + period_length(int(ln["quarter"])) - (int(ln["time"][:2]) * 60 + int(ln["time"][3:])) for ln in lines)
    expected_period = played if closing_line or latest > period_start(played) else played - 1
    assert duration == period_start(expected_period) + period_length(expected_period), f"#561 {played} periodos, cierre={closing_line}: {duration} s"
