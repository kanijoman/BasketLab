"""truncate_doc: a finished game cut at a clock point, shaped like a live FEB document."""

import copy

from src.live_core.clock import elapsed_seconds
from src.live_core.replay import truncate_doc


def _max_elapsed(doc):
    return max(elapsed_seconds(int(l["quarter"]), _secs(l["time"])) for l in doc["PLAYBYPLAY"]["LINES"])


def _secs(t):
    m, s = t.split(":")
    return int(m) * 60 + int(s)


def test_only_events_up_to_the_cut_survive(feb_game_doc):
    doc = truncate_doc(feb_game_doc, period=2, remaining=300)
    assert doc["PLAYBYPLAY"]["LINES"]
    assert _max_elapsed(doc) <= elapsed_seconds(2, 300)
    assert len(doc["PLAYBYPLAY"]["LINES"]) < len(feb_game_doc["PLAYBYPLAY"]["LINES"])


def test_original_is_not_modified(feb_game_doc):
    before = copy.deepcopy(feb_game_doc)
    truncate_doc(feb_game_doc, period=1, remaining=100)
    assert feb_game_doc == before


def test_header_looks_live(feb_game_doc):
    doc = truncate_doc(feb_game_doc, period=3, remaining=330)
    h = doc["HEADER"]
    assert h["status"] != "3" and h["statusText"] != "FINISHED"
    assert str(h["quarter"]) == "3" and h["time"] == "05:30"


def test_final_stats_do_not_leak_into_the_partial_box_score(feb_game_doc):
    doc = truncate_doc(feb_game_doc, period=1, remaining=300)
    for team in doc["BOXSCORE"]["TEAM"]:
        assert "TOTAL" not in team
        for p in team["PLAYER"]:
            assert p.get("id") and p.get("name")
            assert "pf" not in p and "pts" not in p and "min" not in p


def test_cut_at_the_very_end_keeps_every_event(feb_game_doc):
    doc = truncate_doc(feb_game_doc, period=4, remaining=0)
    assert len(doc["PLAYBYPLAY"]["LINES"]) == len(feb_game_doc["PLAYBYPLAY"]["LINES"])


def test_lines_keep_the_feb_descending_order(feb_game_doc):
    nums = [int(l["num"]) for l in truncate_doc(feb_game_doc, period=3, remaining=100)["PLAYBYPLAY"]["LINES"]]
    assert nums == sorted(nums, reverse=True)
