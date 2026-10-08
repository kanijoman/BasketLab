"""Shot zones tracked from the (incremental) SHOTCHART feed.

Verified on the real sample: the SHOTCHART shots are exactly the field-goal events of the
play-by-play ((quarter, time remaining, made, team) multisets are identical; team 0/1 =
HEADER.TEAM[0]/[1]), so the feed can be cut by the clock like the PBP.
"""

import copy
import json

from src.live_core.engine import LiveEngine
from src.live_core.events import parse_line
from src.live_core.replay import truncate_doc
from src.live_core.shots import ShotTracker


def _ids(doc):
    return [t["id"] for t in doc["HEADER"]["TEAM"]]


def _pbp_fg(doc):
    return [e for e in (parse_line(l) for l in doc["PLAYBYPLAY"]["LINES"]) if e and e.kind in ("fg2", "fg3")]


def test_tracker_counts_match_the_play_by_play_per_team(feb_game_doc):
    ids = _ids(feb_game_doc)
    tracker = ShotTracker(ids)
    tracker.update(feb_game_doc["SHOTCHART"])
    zones = tracker.snapshot()
    for tid in ids:
        mine = [e for e in _pbp_fg(feb_game_doc) if e.team_id == tid]
        assert sum(z["a"] for z in zones[tid].values()) == len(mine)
        assert sum(z["m"] for z in zones[tid].values()) == sum(1 for e in mine if e.made)


def test_zone_points_reproduce_the_field_goal_points(feb_game_doc):
    ids = _ids(feb_game_doc)
    tracker = ShotTracker(ids)
    tracker.update(feb_game_doc["SHOTCHART"])
    zones = tracker.snapshot()
    for tid in ids:
        real = sum(e.points for e in _pbp_fg(feb_game_doc) if e.team_id == tid)
        assert sum(z["pts"] for z in zones[tid].values()) == real


def test_incremental_updates_equal_one_shot(feb_game_doc):
    shots = feb_game_doc["SHOTCHART"]["SHOTS"]
    one = ShotTracker(_ids(feb_game_doc))
    one.update({"SHOTS": shots})
    inc = ShotTracker(_ids(feb_game_doc))
    for upto in (10, 50, 121, 121):
        inc.update({"SHOTS": shots[:upto]})
    assert inc.snapshot() == one.snapshot()


def test_the_same_shot_is_never_counted_twice(feb_game_doc):
    shots = feb_game_doc["SHOTCHART"]["SHOTS"]
    tracker = ShotTracker(_ids(feb_game_doc))
    tracker.update({"SHOTS": shots + shots})
    assert sum(z["a"] for t in tracker.snapshot().values() for z in t.values()) == len(shots)


def test_tolerates_missing_empty_and_malformed_feeds():
    tracker = ShotTracker(["A", "B"])
    for feed in (None, [], {}, {"SHOTS": None}, {"SHOTS": [{"x": "bad", "y": None, "team": "0", "m": "1"}, "junk"]}):
        tracker.update(feed)
    assert tracker.snapshot() == {"A": {}, "B": {}}


def test_a_list_feed_is_accepted_too():
    tracker = ShotTracker(["A", "B"])
    tracker.update([{"x": "10", "y": "50", "team": "0", "m": "1", "t": "05:00", "quarter": "1", "player": "6"}])
    assert sum(z["a"] for z in tracker.snapshot()["A"].values()) == 1


def test_unknown_team_index_is_ignored():
    tracker = ShotTracker(["A", "B"])
    tracker.update({"SHOTS": [{"x": "10", "y": "50", "team": "5", "m": "1", "t": "05:00", "quarter": "1"}]})
    assert tracker.snapshot() == {"A": {}, "B": {}}


# --- engine and replay --------------------------------------------------------------

def test_engine_snapshot_carries_the_zones(feb_game_doc):
    snap = LiveEngine().update(feb_game_doc)
    assert set(snap["zones"]) == set(_ids(feb_game_doc))
    assert sum(z["a"] for t in snap["zones"].values() for z in t.values()) == 121
    json.dumps(snap)


def test_engine_follows_a_growing_shotchart(feb_game_doc):
    engine, totals = LiveEngine(), []
    for period, remaining in [(1, 300), (2, 300), (3, 300), (4, 0)]:
        snap = engine.update(truncate_doc(feb_game_doc, period, remaining))
        totals.append(sum(z["a"] for t in snap["zones"].values() for z in t.values()))
    assert totals == sorted(totals) and totals[0] < totals[-1] == 121


def test_truncated_shotchart_has_exactly_the_shots_up_to_the_cut(feb_game_doc):
    for period, remaining in [(1, 300), (2, 100), (3, 450), (4, 30)]:
        cut = truncate_doc(feb_game_doc, period, remaining)
        assert len(cut["SHOTCHART"]["SHOTS"]) == len(_pbp_fg(cut))


def test_truncation_does_not_leak_final_box_stats_through_the_shotchart(feb_game_doc):
    cut = truncate_doc(feb_game_doc, 2, 300)
    assert not cut["SHOTCHART"].get("TEAM")
    assert feb_game_doc["SHOTCHART"]["TEAM"], "the original must stay untouched"


def test_original_document_is_not_modified_by_truncation(feb_game_doc):
    before = copy.deepcopy(feb_game_doc["SHOTCHART"])
    truncate_doc(feb_game_doc, 1, 100)
    assert feb_game_doc["SHOTCHART"] == before
