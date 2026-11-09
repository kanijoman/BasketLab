"""Where the web draws the bubble of each zone of the engine (issue #452, block 2).

The web reads the zones of the engine from one file, order, label and points (``localdata/shots.ts``) and the anchor of each bubble of its zone courts: ``frontend/src/lib/engineZones.json`` (metres on the half court, the same axes as ``live_core.zones``).
The engine's zones are rings and columns, not blobs (the short mid-range is two slivers beside the hoop), so the centroid of a zone is often outside it: the anchors are chosen by
hand, and this test keeps them honest against the classifier itself (an anchor must be IN its zone) and apart from each other.
"""
import json
import math
from pathlib import Path

import pytest

from src.live_core.zones import ZONES, classify_fiba

ANCHORS = json.loads((Path(__file__).resolve().parents[1] / "frontend/src/lib/engineZones.json").read_text(encoding="utf-8"))


def test_there_is_an_anchor_for_every_zone_of_the_engine_and_only_for_them():
    assert list(ANCHORS) == list(ZONES)


@pytest.mark.parametrize("zone", list(ZONES))
def test_the_anchor_is_inside_its_zone_and_the_label_is_the_one_of_the_engine(zone):
    anchor = ANCHORS[zone]
    assert classify_fiba(anchor["x"], anchor["y"])["zone"] == zone
    assert anchor["label"] == ZONES[zone]["name"] and anchor["points"] == ZONES[zone]["points"]


def test_no_two_anchors_are_closer_than_a_big_bubble_is_wide():
    keys = list(ANCHORS)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            assert math.hypot(ANCHORS[a]["x"] - ANCHORS[b]["x"], ANCHORS[a]["y"] - ANCHORS[b]["y"]) >= 1.4, (a, b)
