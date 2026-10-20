"""Shot-zone rules (issue #247): Z1 own hot zone, Z2 own cold zone or poor selection, Z3 a zone the rival concedes (confirmed live),
Z4 a rival player hot from a zone, Z5 the battle for the paint.

Zones are grouped in families (aro, zona, media distancia, esquina, ala, centro del arco) like the rival zone alerts; the references come
from the package (``tables.zones``: league, own, rival_conceded) and fall back to the league defaults of ``zones.py``.
"""
import json

import pytest

from src.live_core.advice import RULES, AdviceEngine
from src.live_core.config import RULE_IDS, RuleConfig
from tests.test_live_core_advice import OWN, RIVAL, snap

RULE_GROUPS = ("own_zones", "rival_defence_zones", "rival_zone_player", "paint_battle")


def cell(a, m, pts):
    return {"a": a, "m": m, "pts": pts}


def zone_snap(own=None, rival=None, players=None, zone_players=None, period=2, elapsed=1000):
    s = snap(period=period, elapsed=elapsed, players=players or {})
    s["zones"] = {OWN: own or {}, RIVAL: rival or {}}
    s["zone_players"] = zone_players or {OWN: {}, RIVAL: {}}
    return s


def engine(zone_ref=None, **kw):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, zone_ref=zone_ref, **kw)


def by_id(advices, advice_id):
    return [a for a in advices if a.id == advice_id]


def player(name, team):
    return {"name": name, "team_id": team, "on_court": True, "minutes": 600, "stint": 0, "pf": 0, "pts": 0, "pf_by_period": {}}


def test_the_rules_are_registered_and_can_be_switched_off():
    for rule_id in RULE_GROUPS:
        assert rule_id in RULE_IDS and rule_id in [rid for rid, _ in RULES]
    off = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, config=RuleConfig(rules_off=("own_zones",)))
    assert not by_id(off.evaluate(zone_snap(own={"restricted_area": cell(6, 6, 12)})), "own_zone_hot")


# --- Z1: own hot zone ---------------------------------------------------------------------------------------------

def test_z1_a_zone_where_we_score_far_above_what_is_expected_says_to_insist():
    [alert] = by_id(engine().evaluate(zone_snap(own={"restricted_area": cell(6, 6, 12)})), "own_zone_hot")
    assert alert.severity == "info" and alert.category == "four_factors" and "el aro" in alert.message and "6/6" in alert.message
    assert alert.proposal[0]["type"] == "tactic" and "Insistir" in alert.proposal[0]["message"]
    assert alert.evidence["family"] == "aro" and alert.evidence["pps"] > alert.evidence["expected_pps"] + 0.5


@pytest.mark.parametrize("zone", [cell(4, 4, 8), cell(6, 2, 4), cell(6, 4, 8)])
def test_z1_it_needs_attempts_makes_and_an_excess(zone):
    assert not by_id(engine().evaluate(zone_snap(own={"restricted_area": zone})), "own_zone_hot")


def test_z1_the_expected_value_is_the_own_season_shrunk_to_the_league():
    league = {"left_wing_three": cell(200, 70, 210)}                           # 1.05 points per shot for the league
    usual = {"league": league, "own": {"left_wing_three": cell(100, 45, 135)}}   # 1.35 for us: we are expected to score more than the league
    [alert] = by_id(engine(usual).evaluate(zone_snap(own={"left_wing_three": cell(6, 5, 15)})), "own_zone_hot")
    assert 1.05 < alert.evidence["expected_pps"] < 1.35
    high = {"league": league, "own": {"left_wing_three": cell(100, 60, 180)}}  # 1.8: the same night is only a little above what we usually do
    assert not by_id(engine(high).evaluate(zone_snap(own={"left_wing_three": cell(6, 4, 12)})), "own_zone_hot")


# --- Z2: own cold zone or poor selection --------------------------------------------------------------------------------

def test_z2_a_zone_where_we_score_far_below_what_is_expected_says_to_change_the_selection():
    [alert] = by_id(engine().evaluate(zone_snap(own={"left_wing_three": cell(7, 0, 0)})), "own_zone_cold")
    assert alert.severity == "info" and "las alas" in alert.message and "0/7" in alert.message
    assert alert.proposal[0]["type"] == "tactic" and "selección" in alert.proposal[0]["message"].lower()


def test_z2_it_needs_five_attempts_and_a_deficit():
    assert not by_id(engine().evaluate(zone_snap(own={"left_wing_three": cell(4, 0, 0)})), "own_zone_cold")
    assert not by_id(engine().evaluate(zone_snap(own={"left_wing_three": cell(7, 3, 9)})), "own_zone_cold")


def test_z2_too_many_mid_range_shots_is_a_poor_selection():
    own = {"short_mid_range": cell(9, 3, 6), "restricted_area": cell(5, 3, 6), "left_wing_three": cell(6, 2, 6)}
    [alert] = by_id(engine().evaluate(zone_snap(own=own)), "own_zone_selection")
    assert alert.severity == "info" and "media distancia" in alert.message and "9 de 20" in alert.message
    calm = {"short_mid_range": cell(3, 1, 2), "restricted_area": cell(9, 5, 10), "left_wing_three": cell(8, 3, 9)}
    assert not by_id(engine().evaluate(zone_snap(own=calm)), "own_zone_selection")


# --- Z3: the zone the rival concedes ---------------------------------------------------------------------------------------

LEAGUE_ARO = {"restricted_area": cell(100, 65, 130)}
CONCEDED = {"restricted_area": cell(60, 48, 96)}


def concede(own_aro, conceded=None, league=None):
    ref = {"league": league or LEAGUE_ARO, "rival_conceded": conceded or CONCEDED}
    return by_id(engine(ref).evaluate(zone_snap(own={"restricted_area": own_aro})), "rival_concedes_zone")


def test_z3_a_zone_the_rival_concedes_in_the_season_and_where_we_already_score_is_to_be_attacked():
    [alert] = concede(cell(3, 3, 6))
    assert alert.severity == "info" and alert.category == "rival" and "el aro" in alert.message and "3/3" in alert.message
    assert alert.proposal[0]["type"] == "tactic" and "Atacar" in alert.proposal[0]["message"]
    assert alert.evidence["conceded_pps"] > alert.evidence["league_pps"] + 0.15


@pytest.mark.parametrize("kw", [
    dict(own_aro=cell(2, 2, 4)),                                              # not confirmed live: too few attempts
    dict(own_aro=cell(4, 1, 2)),                                              # confirmed by nothing: we score below the league
    dict(own_aro=cell(3, 3, 6), conceded={"restricted_area": cell(60, 40, 80)}),    # it does not concede more than the league
    dict(own_aro=cell(3, 3, 6), conceded={"restricted_area": cell(15, 14, 28)}),    # too few season shots to trust
])
def test_z3_it_needs_a_real_season_excess_and_a_live_confirmation(kw):
    assert not concede(**kw)


def test_z3_without_the_rival_conceded_zones_in_the_package_it_says_nothing():
    assert not by_id(engine({"league": LEAGUE_ARO}).evaluate(zone_snap(own={"restricted_area": cell(3, 3, 6)})), "rival_concedes_zone")


# --- Z4: a rival player hot from a zone ---------------------------------------------------------------------------------------

def hot(a, m, pts, zone="right_wing_three", team=RIVAL):
    s = zone_snap(players={"r1": player("Rita", RIVAL), "p1": player("Ana", OWN)},
                  zone_players={OWN: {"p1": {zone: cell(a, m, pts)}} if team == OWN else {}, RIVAL: {"r1": {zone: cell(a, m, pts)}} if team == RIVAL else {}})
    return by_id(engine().evaluate(s), "rival_player_zone")


def test_z4_a_rival_hot_from_one_zone_is_to_be_denied_that_zone():
    [alert] = hot(4, 3, 9)
    assert alert.severity == "warning" and alert.category == "rival" and "Rita" in alert.message and "3/4" in alert.message and "las alas" in alert.message
    assert alert.proposal[0]["player_id"] == "r1" and "Negarle" in alert.proposal[0]["message"]


@pytest.mark.parametrize("a, m, pts", [(3, 3, 9), (6, 2, 6), (6, 3, 6)])
def test_z4_it_needs_four_attempts_three_makes_and_a_high_value(a, m, pts):
    assert not hot(a, m, pts)


def test_z4_our_own_players_are_not_a_threat_and_it_is_said_once_per_player_and_family():
    assert not hot(4, 3, 9, team=OWN)
    e = engine()
    s = zone_snap(players={"r1": player("Rita", RIVAL)}, zone_players={OWN: {}, RIVAL: {"r1": {"right_wing_three": cell(4, 3, 9)}}})
    assert by_id(e.evaluate(s), "rival_player_zone") and not by_id(e.evaluate(s), "rival_player_zone")


# --- Z5: the paint ------------------------------------------------------------------------------------------------------------------

def paint(own, rival, period=2):
    s = zone_snap(own={"restricted_area": cell(6, 3, own[0]), "key_area": cell(4, 2, own[1])},
                  rival={"restricted_area": cell(9, 7, rival[0]), "key_area": cell(5, 4, rival[1])}, period=period)
    return by_id(engine().evaluate(s), "paint_battle")


def test_z5_ten_points_less_in_the_paint_says_to_close_the_zone():
    [alert] = paint(own=(6, 4), rival=(14, 8))
    assert alert.severity == "warning" and "-12" in alert.message and "10-22" in alert.message
    assert "cerrar" not in alert.message.lower() and alert.proposal[0]["type"] == "tactic" and "Cerrar la zona" in alert.proposal[0]["message"]


def test_z5_ten_points_more_in_the_paint_says_to_keep_attacking_inside():
    [alert] = paint(own=(20, 10), rival=(10, 8))
    assert alert.severity == "info" and "+12" in alert.message and "dentro" in alert.proposal[0]["message"]


def test_z5_a_difference_below_ten_or_a_repeat_in_the_same_period_says_nothing():
    assert not paint(own=(8, 4), rival=(9, 8))
    e = engine()
    s = zone_snap(own={"restricted_area": cell(6, 3, 6)}, rival={"restricted_area": cell(9, 7, 22)})
    assert by_id(e.evaluate(s), "paint_battle") and not by_id(e.evaluate(s), "paint_battle")


def test_the_alerts_are_json_serialisable():
    [alert] = hot(4, 3, 9)
    assert json.loads(json.dumps(alert.proposal)) == alert.proposal
