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


def without(doc, num):
    out = copy.deepcopy(doc)
    out["PLAYBYPLAY"]["LINES"] = [ln for ln in lines(out) if str(ln["num"]) != str(num)]
    return out


def a_made_basket(doc, period):
    """The number of a made basket of ``period``: a line whose loss changes the score."""
    return next(ln["num"] for ln in lines(doc) if "ANOTADO" in ln["text"] and int(ln["quarter"]) == period)


def final(snap):
    """What a user sees: the score, the points and fouls of every player and the teams."""
    return snap["score"], {pid: (p["pts"], p["on_court"], p["pf"]) for pid, p in snap["players"].items()}, snap["teams"]


def test_a_line_that_vanishes_from_the_middle_of_the_document_is_a_retraction_regression(feb_game_doc):
    """#1120: a basket of the 2nd quarter is not in the document any more (no mark) but the 3rd is: the engine rebuilds and gives what a fresh one gives."""
    seen = truncate_doc(feb_game_doc, 3, 300)
    taken_back = a_made_basket(seen, 2)
    engine = LiveEngine()
    before = engine.update(seen)
    after = engine.update(without(seen, taken_back))
    assert final(after) == final(LiveEngine().update(without(seen, taken_back)))
    assert sum(after["score"].values()) < sum(before["score"].values())


def test_a_document_that_lost_its_last_lines_is_stale_and_changes_nothing_regression(feb_game_doc):
    """#1120: the last basket is missing from a document that is older than the applied one (every missing line is after the last one it has): nothing changes, nothing is rebuilt."""
    seen = truncate_doc(feb_game_doc, 3, 300)
    last_basket = max((ln for ln in lines(seen) if "ANOTADO" in ln["text"]), key=lambda ln: int(ln["num"]))["num"]
    stale = without(truncate_doc(feb_game_doc, 3, 300), last_basket)
    stale["PLAYBYPLAY"]["LINES"] = [ln for ln in lines(stale) if int(ln["num"]) < int(last_basket)]
    engine = LiveEngine()
    before = engine.update(seen)
    game = engine._game
    after = engine.update(stale)
    assert engine._game is game, "a stale document must not rebuild the game"
    assert final(after) == final(before)


def test_an_empty_answer_in_the_middle_of_the_match_changes_nothing(feb_game_doc):
    """#1120: a feed that answers with no lines for a moment is the same case as a stale document: the state of the match stays."""
    seen = truncate_doc(feb_game_doc, 3, 300)
    empty = copy.deepcopy(seen)
    empty["PLAYBYPLAY"]["LINES"] = []
    engine = LiveEngine()
    before = engine.update(seen)
    assert final(engine.update(empty)) == final(before)


def test_after_a_stale_document_the_next_good_one_is_followed(feb_game_doc):
    """#1120: ignoring a stale document does not make the engine deaf: the next complete one is applied like a fresh engine would."""
    seen, later = truncate_doc(feb_game_doc, 2, 300), truncate_doc(feb_game_doc, 3, 300)
    stale = copy.deepcopy(seen)
    stale["PLAYBYPLAY"]["LINES"] = lines(seen)[: len(lines(seen)) // 2]
    engine = LiveEngine()
    engine.update(seen)
    engine.update(stale)
    assert final(engine.update(later)) == final(LiveEngine().update(later))


def test_a_shorter_document_of_another_match_is_not_taken_for_a_stale_one(feb_game_doc):
    """#1120: «fewer lines» is stale only when what the document does have IS what was applied: the shorter document of another game (an engine that is reused) rebuilds."""
    other = truncate_doc(feb_game_doc, 1, 300)
    assert any("ANOTADO" in ln["text"] for ln in lines(other)), "the other game must differ in at least one line"
    other["PLAYBYPLAY"]["LINES"] = [{**ln, "text": ln["text"].replace("ANOTADO", "FALLADO")} for ln in lines(other)]
    engine = LiveEngine()
    engine.update(truncate_doc(feb_game_doc, 3, 300))
    assert final(engine.update(other)) == final(LiveEngine().update(other))


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
