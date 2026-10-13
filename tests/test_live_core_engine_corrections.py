"""FEB corrects play-by-play lines while the match is on (found with the first real recording, issue #174).

In Zamora - Leon three lines changed after the engine had applied them: a three-pointer turned into a two-pointer,
a substitution "Entra" turned into "Sale" and a foul changed its free-throw count. The engine only noticed
deleted lines and lines arriving out of order, so the corrected shot kept its 3rd point for the rest of the match
(final score 39-59 instead of the official 38-59). The incremental result must always equal a fresh computation.
"""
import copy

from src.live_core.engine import LiveEngine


def corrected(doc, predicate, new_text):
    out = copy.deepcopy(doc)
    for line in out["PLAYBYPLAY"]["LINES"]:
        if predicate(line):
            line["text"] = new_text(line["text"])
            return out, line["num"]
    raise AssertionError("no line matched")


def players(snap):
    return {pid: (p["pts"], p["on_court"], p["pf"]) for pid, p in snap["players"].items()}


def assert_same_as_fresh(engine_snap, doc):
    fresh = LiveEngine().update(doc)
    assert engine_snap["score"] == fresh["score"]
    assert players(engine_snap) == players(fresh)
    assert engine_snap["teams"] == fresh["teams"]


def test_a_shot_corrected_from_three_to_two_points_updates_the_score_regression(feb_game_doc):
    engine = LiveEngine()
    engine.update(feb_game_doc)
    doc, _ = corrected(feb_game_doc, lambda l: "TIRO DE 3 ANOTADO" in l["text"],
                       lambda t: t.replace("TIRO DE 3 ANOTADO", "TIRO DE 2 ANOTADO"))
    snap = engine.update(doc)
    assert_same_as_fresh(snap, doc)
    assert sum(snap["score"].values()) == sum(LiveEngine().update(feb_game_doc)["score"].values()) - 1


def test_a_substitution_corrected_from_in_to_out_updates_who_is_on_court(feb_game_doc):
    engine = LiveEngine()
    engine.update(feb_game_doc)
    doc, _ = corrected(feb_game_doc, lambda l: "Entra a pista" in l["text"] and l["num"] not in ("1", "2"),
                       lambda t: t.replace("Entra a pista", "Sale de pista"))
    assert_same_as_fresh(engine.update(doc), doc)


def test_a_foul_with_a_corrected_free_throw_count_is_applied(feb_game_doc):
    engine = LiveEngine()
    engine.update(feb_game_doc)
    doc, _ = corrected(feb_game_doc, lambda l: "FALTA Personal" in l["text"],
                       lambda t: t.replace("Personal", "Antideportiva"))
    assert_same_as_fresh(engine.update(doc), doc)


def test_a_correction_in_the_middle_of_the_match_is_picked_up_while_it_is_still_live(feb_game_doc):
    """The line is corrected two updates after it was applied, with more lines arriving meanwhile."""
    from src.live_core.replay import truncate_doc

    engine = LiveEngine()
    early = truncate_doc(feb_game_doc, 2, 300)
    engine.update(early)
    later, _ = corrected(truncate_doc(feb_game_doc, 3, 300),
                         lambda l: "TIRO DE 3 ANOTADO" in l["text"] and int(l["quarter"]) <= 2,  # applied by the first update
                         lambda t: t.replace("TIRO DE 3 ANOTADO", "TIRO DE 2 ANOTADO"))
    assert_same_as_fresh(engine.update(later), later)


def test_an_identical_update_or_new_lines_do_not_force_a_rebuild(feb_game_doc):
    """Rebuilding is the expensive path: only a changed line may trigger it."""
    from src.live_core.replay import truncate_doc

    engine = LiveEngine()
    engine.update(truncate_doc(feb_game_doc, 2, 300))
    game = engine._game
    engine.update(truncate_doc(feb_game_doc, 2, 300))
    engine.update(truncate_doc(feb_game_doc, 3, 300))
    assert engine._game is game
