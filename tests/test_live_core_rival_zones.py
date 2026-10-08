"""Rival shot-zone alerts: "they are punishing us from a zone".

Zones are grouped by family (corner, wing, centre, mid-range, paint, rim) so the alert does
not depend on the left/right mirroring of the shot converter. Efficiency alert: enough
attempts and makes with points per shot far above what is expected (league average, or the
rival's own season rate shrunk to the league). Volume alert: a large and unusual share of
their shots from one family.
"""

import pytest

from live_helpers import OWN, RIVAL, snap
from src.live_core.advice import AdviceEngine
from src.live_core.config import RuleConfig
from src.live_core.zones import DEFAULT_ZONE_PPS, ZONES, zone_family


def zsnap(rival_zones, own_zones=None, elapsed=1500):
    s = snap(elapsed=elapsed)
    s["zones"] = {OWN: own_zones or {}, RIVAL: rival_zones}
    return s


def cell(a, m, points):
    return {"a": a, "m": m, "pts": m * points}


def eng(zone_ref=None, **cfg):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, zone_ref=zone_ref,
                        config=RuleConfig(**cfg) if cfg else None)


def zone_alerts(advices):
    return [a for a in advices if a.id == "rival_zone"]


def test_defaults_cover_every_zone():
    assert set(DEFAULT_ZONE_PPS) == set(ZONES)
    assert all(0.4 < v < 1.5 for v in DEFAULT_ZONE_PPS.values())


def test_hot_corner_raises_an_efficiency_alert():
    [a] = zone_alerts(eng().evaluate(zsnap({"left_corner_three": cell(6, 4, 3)})))
    assert a.severity == "warning" and a.category == "rival" and a.evidence["kind"] == "eficiencia"
    assert a.evidence["family"] == "esquina" and (a.evidence["attempts"], a.evidence["makes"]) == (6, 4)
    assert "esquina" in a.message.lower() and "4/6" in a.message


def test_left_and_right_wings_are_combined_into_one_family():
    [a] = zone_alerts(eng().evaluate(zsnap({"left_wing_three": cell(4, 3, 3), "right_wing_three": cell(3, 2, 3)})))
    assert a.evidence["family"] == "ala" and (a.evidence["attempts"], a.evidence["makes"]) == (7, 5)


@pytest.mark.parametrize("zones", [
    {"left_corner_three": cell(4, 4, 3)},        # too few attempts
    {"left_corner_three": cell(8, 2, 3)},        # not enough makes
    {"left_corner_three": cell(8, 3, 3)},        # 1.12 pts/shot vs 0.95: not unusual enough
    {"restricted_area": cell(8, 6, 2)},          # 1.5 at the rim vs 1.15 expected
])
def test_no_efficiency_alert_when_it_is_not_unusual(zones):
    assert [a for a in zone_alerts(eng().evaluate(zsnap(zones))) if a.evidence["kind"] == "eficiencia"] == []


def test_a_large_unusual_share_of_shots_from_one_family_is_an_info_alert():
    zones = {"left_wing_three": cell(6, 1, 3), "right_wing_three": cell(5, 1, 3),
             "restricted_area": cell(4, 2, 2), "long_mid_range": cell(5, 2, 2), "key_area": cell(4, 1, 2)}
    [a] = [x for x in zone_alerts(eng().evaluate(zsnap(zones))) if x.evidence["kind"] == "volumen"]
    assert a.severity == "info" and a.evidence["family"] == "ala"
    assert a.evidence["attempts"] == 11 and a.evidence["total"] == 24


def test_the_rivals_own_season_changes_what_is_expected():
    live = {"left_corner_three": cell(6, 3, 3)}          # 1.5 pts/shot
    assert zone_alerts(eng().evaluate(zsnap(live)))      # vs the league's 0.95: unusual
    ref = {"rival": {"left_corner_three": {"a": 100, "m": 53, "pts": 160, "share": 0.2, "pps": 1.6}},
           "league": {}}
    assert zone_alerts(eng(zone_ref=ref).evaluate(zsnap(live))) == []   # a team that is always this good


def test_only_the_rival_is_scouted():
    assert zone_alerts(eng().evaluate(zsnap({}, own_zones={"left_corner_three": cell(8, 7, 3)}))) == []


def test_each_zone_alert_is_emitted_once():
    e = eng()
    s = zsnap({"left_corner_three": cell(6, 4, 3)})
    assert zone_alerts(e.evaluate(s)) and zone_alerts(e.evaluate(s)) == []
    s2 = zsnap({"left_corner_three": cell(7, 5, 3)})
    assert zone_alerts(e.evaluate(s2)) == []


def test_snapshots_without_zones_or_rival_are_fine():
    assert zone_alerts(eng().evaluate(snap())) == []
    assert zone_alerts(AdviceEngine(own_team_id=OWN).evaluate(zsnap({"left_corner_three": cell(6, 4, 3)}))) == []


def test_thresholds_come_from_the_config():
    strict = eng(zone_pps_excess=5.0)
    assert zone_alerts(strict.evaluate(zsnap({"left_corner_three": cell(6, 4, 3)}))) == []


def test_zone_families_are_stable():
    assert zone_family("center_three") == "centro del arco"


def test_default_family_shares_form_a_distribution():
    from src.live_core.zones import DEFAULT_FAMILY_SHARE
    assert sum(DEFAULT_FAMILY_SHARE.values()) == pytest.approx(1.0, abs=0.011)
    assert DEFAULT_FAMILY_SHARE["zona"] > 0.2, "the paint family is large in this 10-zone geometry"
