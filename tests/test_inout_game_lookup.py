"""What the IN/OUT of a player asks of ONE game document before counting it (#200): who the player is, whether the player and the team played."""
import pytest

from src.database._inout_game_lookup import (find_fbcyl_player, find_feb_team_id, normalize_name, player_minutes_played, team_participated)

UUID = "ab280249-d022-4ec8-bb33-a05fecefce05"


def _fbcyl(players, team_id=1, extern=None):
    team = {"players": players}
    team.update({"teamIdIntern": team_id} if team_id is not None else {})
    if extern is not None:
        team["teamIdExtern"] = extern
    return {"stats": {"teams": [team]}}


@pytest.mark.parametrize("name, expected", [
    ("ANA PEREZ LOPEZ", "A PEREZ LOPEZ"), ("ANA MARIA PEREZ LOPEZ", "A PEREZ LOPEZ"), ("ANA PEREZ", "A PEREZ"), ("ANA", "ANA"), ("", ""), (None, ""),
])
def test_normalize_name(name, expected):
    assert normalize_name(name) == expected


class TestFindFbcylPlayer:
    def test_by_uuid_gives_the_actor_and_the_team_of_that_game(self):
        game = _fbcyl([{"uuid": UUID, "actorId": 7, "name": "X"}], team_id=46519)
        assert find_fbcyl_player(game, UUID) == (7, 46519)

    def test_by_normalized_name_when_the_id_is_not_a_uuid(self):
        game = _fbcyl([{"uuid": "other", "actorId": 7, "name": "ANA MARIA PEREZ LOPEZ"}])
        assert find_fbcyl_player(game, "ANA PEREZ LOPEZ") == (7, 1)

    def test_a_uuid_is_never_matched_by_name(self):
        game = _fbcyl([{"uuid": "other", "actorId": 7, "name": UUID}])
        assert find_fbcyl_player(game, UUID) is None

    def test_the_external_team_id_stands_in_for_a_missing_internal_one(self):
        game = _fbcyl([{"uuid": UUID, "actorId": 7}], team_id=None, extern=99)
        assert find_fbcyl_player(game, UUID) == (7, 99)

    @pytest.mark.parametrize("player", [{"uuid": UUID}, {"uuid": UUID, "actorId": 0}, {"uuid": "other", "actorId": 7}])
    def test_none_when_the_player_is_absent_or_has_no_actor(self, player):
        assert find_fbcyl_player(_fbcyl([player]), UUID) is None

    def test_none_without_stats(self):
        assert find_fbcyl_player({}, UUID) is None


def test_feb_team_of_a_player_comes_from_the_game_that_has_it():
    doc = {"BOXSCORE": {"TEAM": [{"id": "A", "PLAYER": [{"id": "P1"}]}, {"id": "B", "PLAYER": [{"id": "Q1"}]}]}}
    assert find_feb_team_id(doc, "Q1") == "B"
    assert find_feb_team_id(doc, "nobody") is None
    assert find_feb_team_id(None, "P1") is None


def _feb(minutes):
    return {"BOXSCORE": {"TEAM": [{"id": "A", "PLAYER": [{"id": "P1", "min": minutes}]}]}}


@pytest.mark.parametrize("raw, expected", [
    ("10:30", 10.5), ("5", 5.0), (5, 5.0), (7.5, 7.5), ("0:00", 0.0), ("0", 0.0), ("", 0.0), (None, 0.0), ("x:y", 0.0), ("abc", 0.0), ("5:", 0.0), (" 2:30 ", 2.5),
])
def test_feb_minutes_of_every_format(raw, expected):
    assert player_minutes_played(_feb(raw), "P1", False) == pytest.approx(expected)


def test_a_player_not_in_the_box_played_zero_minutes():
    assert player_minutes_played(_feb("10:00"), "P9", False) == 0.0
    assert player_minutes_played({}, "P9", False) == 0.0
    assert player_minutes_played(_fbcyl([{"actorId": 7, "timePlayed": 12}]), 8, True) == 0.0


class TestFbcylMinutes:
    def test_the_minutes_of_the_actor_of_the_game(self):
        assert player_minutes_played(_fbcyl([{"actorId": 7, "timePlayed": 12.5}]), 7, True) == 12.5

    def test_none_is_zero(self):
        assert player_minutes_played(_fbcyl([{"actorId": 7, "timePlayed": None}]), 7, True) == 0.0

    def test_forty_minutes_with_no_activity_is_a_phantom_player(self):
        assert player_minutes_played(_fbcyl([{"actorId": 7, "timePlayed": 40, "data": {"score": 0, "assists": None}}]), 7, True) == 0.0

    def test_forty_minutes_with_activity_is_real(self):
        assert player_minutes_played(_fbcyl([{"actorId": 7, "timePlayed": 40, "data": {"steals": 1}}]), 7, True) == 40.0


@pytest.mark.parametrize("game, team, is_fbcyl, expected", [
    (_fbcyl([{"actorId": 1}], team_id=5), 5, True, True),
    (_fbcyl([{"actorId": 1, "timePlayed": 0}], team_id=5), 5, True, True),       # a box with players and no minutes still counts
    (_fbcyl([], team_id=5), 5, True, False),
    (_fbcyl([{"actorId": 1}], team_id=5), 6, True, False),
    ({"BOXSCORE": {"TEAM": [{"id": "A", "PLAYER": [{"id": "P1", "min": "0:00"}]}]}}, "A", False, True),
    ({"BOXSCORE": {"TEAM": [{"id": "A", "PLAYER": []}]}}, "A", False, False),
    ({"BOXSCORE": {"TEAM": [{"id": "A", "PLAYER": [{"id": "P1"}]}]}}, "B", False, False),
    ({}, "A", False, False),
])
def test_team_participated(game, team, is_fbcyl, expected):
    assert team_participated(game, team, is_fbcyl) is expected
