"""Properties of ``LiveEngine`` on the DOCUMENTS of the feed (#1116, epic #1108).

``test_live_core_properties.py`` plays events through ``LiveGame``; the bugs of the review of 26/11/2026 lived one level up, in what the engine does with a SEQUENCE of documents:
corrected, retracted, duplicated, late and stale lines. A match is played with ``tests/builders.Match`` (only states the engine can reach, overtime and technical fouls included),
written as the FEB document it would be (``Match.document()``) and served like the feed does: growing prefixes of its lines, some of them spoiled on the way, ending with the whole
document. Properties:

* the engine that followed the whole sequence says what a fresh engine says about the final document (score, players, teams, possessions);
* a stale document (older than what was applied) in the middle of the sequence changes nothing.
"""
import copy
import os
from typing import Any, Dict, List, Tuple

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from src.live_core.engine import LiveEngine
from tests.builders import OWN, RIVAL, Match

settings.register_profile("ci", max_examples=40, deadline=None, derandomize=True, suppress_health_check=[HealthCheck.too_slow])
settings.register_profile("explore", max_examples=500, deadline=None, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

FIVE = {OWN: ["a", "b", "c", "d", "e"], RIVAL: ["v", "w", "x", "y", "z"]}
ACTIONS = ("score", "score", "miss", "turnover", "foul", "technical", "timeout", "ft")

# a step: (wait in s, action, team, a pick for who and what); the match lasts up to the overtime
steps = st.lists(st.tuples(st.integers(1, 90), st.sampled_from(ACTIONS), st.sampled_from((OWN, RIVAL)), st.integers(0, 99)), min_size=8, max_size=70)
# how the feed serves it: (how many lines of the match the document has, how it is spoiled)
SPOILS = ("none", "none", "none", "correct", "retract", "twin", "stale")
versions = st.lists(st.tuples(st.floats(0.05, 1.0), st.sampled_from(SPOILS), st.integers(0, 999)), min_size=1, max_size=8)


def play(generated: List[Tuple[int, str, str, int]]) -> Match:
    m, at = Match(), 0
    for team, five in FIVE.items():
        m.lineup(team, five, at=0)
    for wait, action, team, pick in generated:
        at += wait
        other = RIVAL if team == OWN else OWN
        who = FIVE[team][pick % 5]
        if action == "score":
            m.score(team, (2, 2, 3)[pick % 3], at=at, player=who)
        elif action == "ft":
            m.score(team, 1, at=at, player=who)
        elif action == "miss":
            m.miss(team, at=at, kind=("fg2", "fg3")[pick % 2], player=who).rebound((team, other)[pick % 2], at=at, player=FIVE[(team, other)[pick % 2]][pick % 5])
        elif action == "turnover":
            m.turnover(team, at=at, player=who)
        elif action in ("foul", "technical"):
            m.foul(team, who, at=at, drawn_by=FIVE[other][pick % 5], kind="personal" if action == "foul" else "technical")
        elif action == "timeout":
            m.timeout(team, at=at)
    return m


def prefix(doc: Dict[str, Any], count: int) -> Dict[str, Any]:
    """The document as it was when it had its first ``count`` lines (the feed lists the newest first, and numbers grow)."""
    out = copy.deepcopy(doc)
    lines = sorted(out["PLAYBYPLAY"]["LINES"], key=lambda ln: int(ln["num"]))[:count]
    out["PLAYBYPLAY"]["LINES"] = list(reversed(lines))
    return out


def spoil(doc: Dict[str, Any], how: str, pick: int) -> Dict[str, Any]:
    lines = doc["PLAYBYPLAY"]["LINES"]
    if how == "correct" and lines:                    # FEB corrects a line that was applied: a made shot turns into a missed one
        shots = [ln for ln in lines if "ANOTADO" in ln["text"]]
        if shots:
            shots[pick % len(shots)]["text"] = shots[pick % len(shots)]["text"].replace("ANOTADO", "FALLADO")
    elif how == "retract" and len(lines) > 2:         # a line that is in the middle is gone with no mark (the newest stays, so it is not a stale copy)
        del lines[1 + pick % (len(lines) - 2)]
    elif how == "twin" and lines:                     # the same number twice with other content
        twin = copy.deepcopy(lines[pick % len(lines)])
        twin["text"] = twin["text"].replace("ANOTADO", "FALLADO")
        lines.append(twin)
    return doc


def seen(snap: Dict[str, Any]) -> Tuple[Any, ...]:
    return (snap["score"], {pid: (p["pts"], p["pf"], p["on_court"], p["technical"]) for pid, p in snap["players"].items()}, snap["teams"], snap["possessions"]["counted"])


FINAL = st.tuples(st.sampled_from(("none", "correct", "retract", "twin")), st.integers(0, 999))


@given(steps, versions, FINAL)
def test_following_a_sequence_of_documents_ends_where_a_fresh_engine_does(generated, served, final):
    """The last document may itself be the spoiled one (a line taken back with no mark, a number twice): the engine says what a fresh one says about it, and polling it again
    changes nothing and rebuilds nothing."""
    match = play(generated)
    truth = match.document()
    total = len(truth["PLAYBYPLAY"]["LINES"])
    engine = LiveEngine()
    for share, how, pick in served:
        engine.update(spoil(prefix(truth, max(1, int(total * share))), how, pick))
    last = spoil(copy.deepcopy(truth), *final)
    first = seen(engine.update(last))
    game = engine._game
    assert first == seen(LiveEngine().update(last))
    assert seen(engine.update(last)) == first and engine._game is game, "the same document twice must not rebuild the game"


@given(steps, st.floats(0.2, 0.95))
def test_a_stale_document_in_the_middle_of_the_sequence_changes_nothing(generated, share):
    truth = play(generated).document()
    total = len(truth["PLAYBYPLAY"]["LINES"])
    engine = LiveEngine()
    cut = max(1, int(total * share))
    assume(cut < total)
    before = seen(engine.update(truth))
    game = engine._game
    assert seen(engine.update(prefix(truth, cut))) == before
    assert engine._game is game, "a stale document must not rebuild the game"
