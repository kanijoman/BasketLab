"""The live engine keeps the possessions of the game incrementally (#357, infrastructure only).

``LiveGame`` feeds every event to a ``PossessionTracker`` and the snapshot carries ``possessions``: the counted possessions of each
team, its points by origin and the quality of the feed, over the possessions already CLOSED (the one in progress is not counted).
No alert uses them yet: the figures that would have fed the rules that were planned for this issue (after-timeout possessions, cold
starts, the effect of timeouts) are noise from game to game and were left out; the infrastructure stays for the stable ones.
"""
import copy
import json

import pytest

from src.live_core.engine import LiveEngine, _events
from src.live_core.events import parse_line
from src.live_core.live_possessions import PossessionCounters
from src.live_core.possessions import PossessionTracker, track
from src.live_core.replay import truncate_doc
from src.live_core.state import LiveGame


def _reference(doc, ids):
    """The same events through a plain tracker, without closing the possession in progress."""
    tracker, closed = PossessionTracker(ids), []
    for event in sorted((e for e in _events(doc) if not e.deleted), key=lambda e: e.num):
        closed += tracker.feed(event)
    return closed, tracker


def _ids(doc):
    return [str(t["id"]) for t in doc["HEADER"]["TEAM"]]


def _counted(possessions):
    out = {}
    for p in possessions:
        if p.counted:
            out[p.team_id] = out.get(p.team_id, 0) + 1
    return out


@pytest.mark.parametrize("cut", [(1, 300), (2, 480), (3, 120), (4, 0)])
def test_the_snapshot_counts_what_a_tracker_fed_with_the_same_events_has_closed(feb_game_doc, cut):
    doc = truncate_doc(feb_game_doc, *cut)
    snap = LiveEngine().update(doc)
    closed, _ = _reference(doc, _ids(doc))

    assert snap["possessions"]["counted"] == _counted(closed)


def test_at_the_end_of_the_game_it_equals_the_one_shot_tracker(feb_game_doc):
    snap = LiveEngine().update(feb_game_doc)
    events = [parse_line(l) for l in feb_game_doc["PLAYBYPLAY"]["LINES"]]
    possessions, quality = track(sorted((e for e in events if e is not None), key=lambda e: (e.elapsed, e.num)), _ids(feb_game_doc))

    assert snap["possessions"]["counted"] == _counted(possessions)
    assert snap["possessions"]["quality"]["breaks_raw"] == quality.breaks_raw and snap["possessions"]["quality"]["level"] == quality.level


def test_the_points_by_origin_add_up_to_the_score_when_the_last_possession_is_closed(feb_game_doc):
    snap = LiveEngine().update(feb_game_doc)
    origins = snap["possessions"]["origins"]

    for team_id, score in snap["score"].items():
        assert sum(v["pts"] for v in origins[team_id].values()) == score


def test_every_origin_has_the_count_of_its_possessions_and_the_points_scored_in_them(feb_game_doc):
    origins = LiveEngine().update(feb_game_doc)["possessions"]["origins"]

    for team in origins.values():
        for entry in team.values():
            assert set(entry) == {"n", "pts"} and entry["n"] >= 0 and entry["pts"] >= 0


def test_the_incremental_result_equals_a_fresh_one(feb_game_doc):
    engine = LiveEngine()
    for cut in [(1, 400), (2, 300), (3, 200), (4, 100)]:
        engine.update(truncate_doc(feb_game_doc, *cut))
    incremental = engine.update(feb_game_doc)["possessions"]

    assert incremental == LiveEngine().update(feb_game_doc)["possessions"]


def test_a_corrected_line_rebuilds_the_possessions_like_a_fresh_engine(feb_game_doc):
    engine = LiveEngine()
    engine.update(feb_game_doc)
    doc = copy.deepcopy(feb_game_doc)
    line = next(l for l in doc["PLAYBYPLAY"]["LINES"] if "TIRO DE 3 ANOTADO" in l["text"])
    line["text"] = line["text"].replace("TIRO DE 3 ANOTADO", "TIRO DE 2 ANOTADO")

    assert engine.update(doc)["possessions"] == LiveEngine().update(doc)["possessions"]


def test_the_snapshot_stays_plain_json(feb_game_doc):
    snap = LiveEngine().update(feb_game_doc)

    assert json.loads(json.dumps(snap["possessions"])) == snap["possessions"]


def test_a_game_that_does_not_have_two_teams_has_no_possessions_and_does_not_fail():
    game = LiveGame([("A", "Equipo A")])

    assert game.snapshot()["possessions"] is None
    assert PossessionCounters(["A"]).snapshot() is None


def test_the_technical_free_throws_are_a_origin_of_their_own_so_the_partition_adds_up():
    counters = PossessionCounters(["A", "B"])
    counters.tracker.technical_points["A"] = 2           # what the tracker reports for the free throws of technical fouls

    assert counters.snapshot()["origins"]["A"]["technical"] == {"n": 0, "pts": 2}
