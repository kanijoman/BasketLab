"""Zone data for the zone rules (issue #247): shots per player (the SHOTCHART gives the jersey number, the box score maps it to a
player), and in the package the own team's zones and the zones the rival concedes."""
import pytest

from src.live_core.engine import LiveEngine
from src.live_core.shots import ShotTracker
from src.live_prep.package_builder import SeasonAccumulator

A, B = "982047", "981204"
STAMP = "2026-10-08T00:00:00Z"


def test_every_shot_of_the_sample_game_is_given_to_a_player_through_the_jersey_number(feb_game_doc):
    snapshot = LiveEngine().update(feb_game_doc)
    assert set(snapshot["zone_players"]) == {A, B}
    for tid in (A, B):
        by_zone = {}
        for pid, zones in snapshot["zone_players"][tid].items():
            assert pid in snapshot["players"] and snapshot["players"][pid]["team_id"] == tid
            for zone, cell in zones.items():
                total = by_zone.setdefault(zone, {"a": 0, "m": 0, "pts": 0})
                for key in total:
                    total[key] += cell[key]
        assert by_zone == snapshot["zones"][tid]               # the players add up to the team, zone by zone


def test_the_jersey_number_is_matched_without_leading_zeros_and_a_shot_without_a_known_player_still_counts_for_the_team():
    tracker = ShotTracker([A, B], dorsals={A: {"4": "p4"}, B: {}})
    tracker.update({"SHOTS": [
        {"m": "1", "t": "03:30", "x": "10", "y": "50", "team": "0", "player": "04", "quarter": "1"},
        {"m": "0", "t": "03:00", "x": "10", "y": "50", "team": "0", "player": "9", "quarter": "1"},
    ]})
    team = tracker.snapshot()[A]
    assert sum(c["a"] for c in team.values()) == 2
    players = tracker.player_snapshot()
    assert list(players[A]) == ["p4"] and sum(c["a"] for c in players[A]["p4"].values()) == 1 and players[B] == {}


def test_the_package_carries_the_own_zones_and_the_zones_the_rival_concedes(feb_game_doc):
    acc = SeasonAccumulator()
    acc.add_game(feb_game_doc)
    package = acc.to_package("FEB_TEST", "2025-2026", A, B, None, STAMP)
    zones, snapshot = package.tables["zones"], LiveEngine().update(feb_game_doc)["zones"]
    assert zones["own"] == snapshot[A] and zones["rival"] == snapshot[B]
    assert zones["rival_conceded"] == snapshot[A]              # what B's defence let A shoot is what A shot against it
    assert set(zones) >= {"league", "rival", "own", "rival_conceded"}


def test_a_team_that_did_not_play_has_no_zone_rows(feb_game_doc):
    acc = SeasonAccumulator(track=(A, "999999"))
    acc.add_game(feb_game_doc)
    zones = acc.to_package("FEB_TEST", "2025-2026", A, "999999", None, STAMP).tables["zones"]
    assert zones["rival"] == {} and zones["rival_conceded"] == {} and zones["own"]
