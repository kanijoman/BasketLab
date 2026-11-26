"""A play-by-play line that vanishes, or shows up twice, in the documents of the feed (issues #1120 and #1121, epic #1108).

* A line that is NOT in the document any more, with no ``deleted`` mark, used to go unnoticed: the incremental engine kept its points (74-56) while a fresh one said 74-54, against
  the promise of ``engine.py`` that the result always equals a fresh computation. Two cases, told apart by where the line was:
  - it is in the middle (later lines are still there): FEB took it back, so the engine rebuilds;
  - every missing line is after the last one of the document: the document is older than what was applied (a stale CDN copy, an empty answer): it is ignored, like the FBCYL
    stream that goes backwards (``LiveSession.update_streaming``).
* Two lines with the same number and different content in ONE document applied the first and never the second, and the second looked like a "correction" at every poll (a full
  rebuild each time). One line per number, the last of the document wins, so the result is stable and equals a fresh engine.
"""
import copy

from src.live_core.engine import LiveEngine
from src.live_core.replay import truncate_doc


def lines(doc):
    return doc["PLAYBYPLAY"]["LINES"]


def a_made_basket(doc, period):
    """The number of a made basket of ``period``: a line whose loss changes the score."""
    return next(ln["num"] for ln in lines(doc) if "ANOTADO" in ln["text"] and int(ln["quarter"]) == period)


def final(snap):
    """What a user sees: the score, the points and fouls of every player and the teams."""
    return snap["score"], {pid: (p["pts"], p["on_court"], p["pf"]) for pid, p in snap["players"].items()}, snap["teams"]


def with_a_twin(doc, content):
    """A copy of ``doc`` where the line of the last basket of the 2nd quarter shows up twice: its own content, then ``content`` (same number)."""
    out = copy.deepcopy(doc)
    number = a_made_basket(out, 2)
    original = next(ln for ln in lines(out) if ln["num"] == number)
    twin = {**copy.deepcopy(original), "text": content(original["text"])}
    out["PLAYBYPLAY"]["LINES"] = lines(out) + [twin]
    return out


def test_two_lines_with_the_same_number_are_applied_once_and_never_rebuilt_regression(feb_game_doc):
    """#1121: the document says the same line twice with different content: the last wins, and polling it again does not rebuild the game."""
    seen = with_a_twin(truncate_doc(feb_game_doc, 3, 300), lambda t: t.replace("ANOTADO", "FALLADO"))
    engine = LiveEngine()
    first = engine.update(seen)
    game = engine._game
    second = engine.update(seen)
    third = engine.update(seen)
    assert engine._game is game, "the same document twice must not rebuild the game (the second line looked corrected at every poll)"
    assert final(first) == final(second) == final(third) == final(LiveEngine().update(seen))


def test_of_two_lines_with_the_same_number_the_last_one_of_the_document_wins(feb_game_doc):
    """#1121: the rule, stated: the content that comes last is the one applied (a made 2-pointer repeated as a missed shot does not score)."""
    base = truncate_doc(feb_game_doc, 3, 300)
    number = a_made_basket(base, 2)
    twin_missed = with_a_twin(base, lambda t: t.replace("ANOTADO", "FALLADO"))
    scored = sum(LiveEngine().update(base)["score"].values())
    taken = sum(LiveEngine().update(twin_missed)["score"].values())
    assert taken < scored, f"line {number} says made, then missed: the last (missed) wins"
