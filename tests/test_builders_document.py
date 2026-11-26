"""The ``Match`` builder writes the FEB document of what it played (``document()``) and logs actions late (``late()``), foul kinds included (#1117, epic #1108): the engine reading
that document ends where the state machine of the builder is."""
import pytest

from src.live_core.engine import LiveEngine
from tests.builders import OWN, RIVAL, Match


def _match():
    m = Match().lineup(OWN, ["a", "b", "c", "d", "e"]).lineup(RIVAL, ["v", "w", "x", "y", "z"])
    return (m.score(OWN, 3, at=60, player="a").miss(RIVAL, at=90, player="v").rebound(OWN, at=91, player="b").foul(OWN, "c", at=120, drawn_by="w")
            .foul(RIVAL, "x", at=150, kind="technical").score(RIVAL, 1, at=151, player="w").turnover(OWN, at=200, player="a"))


def _seen(snap):
    return {pid: (p["pts"], p["pf"], p["on_court"]) for pid, p in snap["players"].items()}


def test_the_engine_reading_the_document_of_a_match_agrees_with_the_builder():
    m = _match()
    snap = LiveEngine().update(m.document())
    assert snap["score"] == m.snapshot()["score"]
    assert _seen(snap) == _seen(m.snapshot())


def test_a_technical_foul_is_written_and_read_as_a_technical_one():
    m = _match()
    assert m.snapshot()["players"]["x"]["technical"] == 1
    assert LiveEngine().update(m.document())["players"]["x"]["technical"] == 1


def test_a_late_line_gets_the_next_number_and_an_earlier_clock_and_time_still_refuses_to_go_back_otherwise():
    m = Match().score(OWN, 2, at=100).late("turnover", RIVAL, at=60)
    assert [e.num for e in m.events] == [1, 2] and [e.elapsed for e in m.events] == [100, 60]
    with pytest.raises(ValueError):
        m.turnover(OWN, at=10)


def test_an_unknown_kind_of_foul_is_refused():
    with pytest.raises(ValueError):
        Match().foul(OWN, "a", at=10, kind="flopping")
