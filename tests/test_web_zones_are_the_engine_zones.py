"""The web classifies shots with the zones of the engine (issue #452, block 2, step 2 of 3).

The web had its own geometry (``feb_zones``: paint, mid_left/center/right, wing_left, top_three...) and the app and the scouting reports the one of ``live_core.zones``: the same shot
fell in different zones depending on the screen (only 64 % of the half court was equivalent). The user chose the engine's system as the canonical one. ``feb_zones`` keeps its API (the
router, the services and the exporters call it) and answers with the engine's zones, so there is ONE geometry; the files of ``web-data`` that carry zones say ``zone_system: "engine"``,
which is what the frontend (already reading both systems, step 1) uses to pick the list of zones.
"""
import json
from pathlib import Path

import pytest

from src.live_core import zones as engine
from src.shotcharts import feb_zones as web

ANCHORS = json.loads((Path(__file__).resolve().parents[1] / "frontend/src/lib/engineZones.json").read_text(encoding="utf-8"))


def _half_court(step=0.1):
    """Every point of the half court (x across 0..15 m, y from the baseline 0..14 m), the way the zones of the engine are defined."""
    for i in range(0, int(15 / step) + 1):
        for j in range(0, int(14 / step) + 1):
            yield round(i * step, 4), round(j * step, 4)


def test_the_web_classifies_every_point_of_the_half_court_as_the_engine_does_regression():
    different = [(x, y) for x, y in _half_court() if web.classify_zone(x, y) != engine.classify_fiba(x, y)["zone"]]
    assert different == [], f"{len(different)} points where the web and the engine say different zones, first: {different[:3]}"


def test_the_zones_the_web_lists_are_the_ones_of_the_engine_in_its_order_with_its_labels_and_points():
    assert list(web.ZONE_META) == list(engine.ZONES)
    for key, meta in web.ZONE_META.items():
        assert (meta["label"], meta["points"]) == (engine.ZONES[key]["name"], engine.ZONES[key]["points"])


def test_the_labels_and_the_order_of_the_frontend_file_are_the_same_ones():
    assert list(ANCHORS) == list(web.ZONE_META)
    assert [a["label"] for a in ANCHORS.values()] == [m["label"] for m in web.ZONE_META.values()]


@pytest.mark.parametrize("team", [0, 1])
def test_the_conversion_of_the_coordinates_of_a_shot_is_the_one_of_the_engine(team):
    for x in range(0, 101, 4):
        for y in range(0, 101, 4):
            assert web.feb_to_fiba(x, y, team) == engine.feb_to_fiba(x, y, team)


def test_the_counting_lists_every_zone_of_the_engine_even_without_shots():
    table = web.aggregate_zones({"key_area": {"fga": 4, "fgm": 3}})
    assert [row["zone"] for row in table] == list(engine.ZONES)
    assert next(row for row in table if row["zone"] == "key_area") == {"zone": "key_area", "zone_label": "Zona", "points": 2, "fga": 4, "fgm": 3, "fg_pct": 75.0}


def test_the_shots_file_says_which_zone_system_it_is_in():
    from src.local_data.shots_export import export_shots

    class Empty:
        def count_documents(self, _query):
            return 0

        def find(self, *_args, **_kwargs):
            return iter(())

    assert export_shots(Empty(), "LF_X")["zone_system"] == "engine"
