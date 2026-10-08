"""Court zones in the standard library (the existing classifier needs shapely).

Validated for parity against ``src.shotcharts.detailed_zones.DetailedCourtZones`` and the
real shots of the sample game. Left/right depends on the converter's mirroring, so the UI
uses zone FAMILIES (corner, wing, centre, mid-range, paint, rim).
"""

import random

import pytest

from src.live_core.zones import (
    ZONES,
    classify_fiba,
    classify_shot,
    feb_to_fiba,
    zone_family,
)

TEN = {"restricted_area", "key_area", "short_mid_range", "medium_mid_range", "long_mid_range",
       "left_corner_three", "left_wing_three", "center_three", "right_wing_three", "right_corner_three"}


def test_ten_zones_with_points_and_spanish_names():
    assert set(ZONES) == TEN
    assert {z["points"] for k, z in ZONES.items() if k.endswith("three")} == {3}
    assert {z["points"] for k, z in ZONES.items() if not k.endswith("three")} == {2}
    assert all(z["name"] for z in ZONES.values())


@pytest.mark.parametrize(
    "x, y, zone",
    [
        (7.5, 1.8, "restricted_area"),      # right at the rim
        (7.5, 0.6, "key_area"),             # behind the backboard is outside the restricted area
        (7.5, 4.5, "key_area"),             # inside the paint
        (10.2, 1.8, "short_mid_range"),     # 2.7 m from the basket, outside the paint
        (3.0, 3.0, "medium_mid_range"),     # 4.7 m
        (7.5, 6.9, "long_mid_range"),       # 5.3 m, inside the arc, above the paint
        (7.5, 10.0, "center_three"),
        (0.4, 1.0, "left_corner_three"),
        (14.6, 1.0, "right_corner_three"),
        (2.0, 8.0, "left_wing_three"),
        (13.0, 8.0, "right_wing_three"),
    ],
)
def test_known_points(x, y, zone):
    assert classify_fiba(x, y)["zone"] == zone


def test_family_groups():
    assert zone_family("left_corner_three") == zone_family("right_corner_three") == "esquina"
    assert zone_family("left_wing_three") == zone_family("right_wing_three") == "ala"
    assert zone_family("center_three") == "centro del arco"
    assert {zone_family(z) for z in ("short_mid_range", "medium_mid_range", "long_mid_range")} == {"media distancia"}
    assert zone_family("restricted_area") == "aro" and zone_family("key_area") == "zona"


# --- parity with the existing implementation ---------------------------------------

shapely = pytest.importorskip("shapely")


@pytest.fixture(scope="module")
def reference():
    from src.shotcharts.detailed_zones import DetailedCourtZones
    return DetailedCourtZones(detail_level="detailed")


def test_coordinate_conversion_matches_the_existing_converter():
    from src.shotcharts.coordinate_utils import convert_feb_to_fiba

    rng = random.Random(7)
    for _ in range(500):
        x, y, team = rng.uniform(0, 100), rng.uniform(0, 100), rng.choice([0, 1, 2])
        assert feb_to_fiba(x, y, team) == pytest.approx(convert_feb_to_fiba(x, y, team))


def test_every_real_shot_of_the_sample_lands_in_the_same_zone(reference, feb_game_doc):
    from src.shotcharts.coordinate_utils import convert_feb_to_fiba

    shots = feb_game_doc["SHOTCHART"]["SHOTS"]
    mismatches = []
    for s in shots:
        fx, fy = convert_feb_to_fiba(float(s["x"]), float(s["y"]), int(s["team"]))
        if classify_fiba(fx, fy)["zone"] != reference.get_zone_for_shot(fx, fy)["zone"]:
            mismatches.append(s)
    assert not mismatches, f"{len(mismatches)} of {len(shots)} shots differ"


def test_grid_parity_with_the_polygon_implementation(reference):
    """Analytic classifier vs the polygon (arc approximated by segments): only boundary slivers differ."""
    rng = random.Random(11)
    n = differing = 0
    for _ in range(4000):
        x, y = rng.uniform(0, 15), rng.uniform(0, 14)
        n += 1
        differing += classify_fiba(x, y)["zone"] != reference.get_zone_for_shot(x, y)["zone"]
    assert differing / n < 0.004, f"{differing}/{n} points differ"


def test_classify_shot_uses_the_feb_conversion(reference, feb_game_doc):
    s = feb_game_doc["SHOTCHART"]["SHOTS"][0]
    fx, fy = feb_to_fiba(float(s["x"]), float(s["y"]), int(s["team"]))
    assert classify_shot(s)["zone"] == classify_fiba(fx, fy)["zone"]
