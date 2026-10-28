"""The invariants of the live engine, shared by the generated matches (test_live_core_properties, B1 #544) and the real ones (test_live_core_weird_games, B3 #546).

Each ``check_*`` takes the snapshot and the alerts of ONE poll of ONE engine (plus what it remembers between polls) and asserts what the staff were once wrong about.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from src.live_core.clock import period_start
from src.live_core.coherence import stance_of
from tests.builders import OWN, RIVAL

def _points(log: list, team: str, start: int, end: int) -> int:
    return sum(e[3] for e in log if e[1] == team and e[2] == "pts" and start <= e[0] <= end)


def check_runs(snap: Dict[str, Any], alerts: list, own_id: str = OWN, rival_id: str = RIVAL) -> None:
    """#515: a run counts no point the team scored before the quarter in play began."""
    now, start, log = snap["elapsed"], period_start(snap["period"]), snap["log"]
    own, rival = _points(log, own_id, start, now), _points(log, rival_id, start, now)
    for a in alerts:
        if a.id == "rival_run":
            assert a.evidence["rival_points"] <= rival and a.evidence["own_points"] <= own, f"#515 {a.message} (en el cuarto: {own}-{rival})"
        elif a.id == "own_run":
            assert a.evidence["net"] <= own, f"#515 {a.message} (el equipo lleva {own} en el cuarto)"
        elif a.id == "long_run":
            assert a.evidence["net"] <= rival, f"#515 {a.message} (el rival lleva {rival} en el cuarto)"


FLOW_COUNTS = {"rival_turnovers": ("turnovers", "tov"), "rival_orb_window": ("orb", "orb")}


def check_flow_repeats(snap: Dict[str, Any], alerts: list, said: Dict[str, int], rival_id: str = RIVAL) -> None:
    """#517: a flow alert said again counts only events after the last time it was said."""
    now = snap["elapsed"]
    for a in alerts:
        if a.id not in FLOW_COUNTS:
            continue
        field, kind = FLOW_COUNTS[a.id]
        if a.id in said:
            new = sum(1 for e in snap["log"] if e[1] == rival_id and e[2] == kind and said[a.id] < e[0] <= now)
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


