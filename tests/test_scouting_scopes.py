"""The scouting of a team over several competitions (#638): Liga, Copa or both («Agrupado»), like Multifase but across competitions.

A team plays its league and the cup in different collections. The scouting replays ALL its games from its own side; what it learns of the season (the
priors of the engine and the league's zones and origin figures) comes from the games of its LEAGUE only, so a cup game against a team of another division
never moves the league context. Every game is replayed once and counted in its own scope and in the grouped one.
"""
import copy

import pytest

from src.live_prep.scouting_collect import scout_team, scout_team_scopes

A, B = "982047", "981204"          # the two teams of the sample game


def dated(doc, start, code):
    out = copy.deepcopy(doc)
    out["HEADER"]["starttime"] = start
    out["_id"] = code
    return out


@pytest.fixture(scope="module")
def league(feb_game_doc):
    return [dated(feb_game_doc, "10-10-2026 - 17:00", 9001), dated(feb_game_doc, "17-10-2026 - 17:00", 9002)]


@pytest.fixture(scope="module")
def cup(feb_game_doc):
    return [dated(feb_game_doc, "14-10-2026 - 20:00", 9101)]


@pytest.fixture(scope="module")
def scopes(league, cup):
    return scout_team_scopes(iter(league), A, "LIGA", extra={"copa": iter(cup)})


def test_the_scopes_are_the_league_the_cup_and_both(scopes):
    assert set(scopes) == {"liga", "copa", "todo"}
    assert [scopes[s]["sample_games"] for s in ("liga", "copa", "todo")] == [2, 1, 3]


def test_the_grouped_games_are_in_date_order_and_each_says_its_competition(scopes):
    games = scopes["todo"]["games"]
    assert [g["date"][:10] for g in games] == ["2026-10-10", "2026-10-14", "2026-10-17"]
    assert [g["competition"] for g in games] == ["liga", "copa", "liga"]
    assert all(g["competition"] == "liga" for g in scopes["liga"]["games"]) and scopes["copa"]["games"][0]["competition"] == "copa"


def test_the_league_scope_is_what_the_old_scouting_of_the_league_gave(league, scopes):
    """A cup game must not change anything the league scouting says (it is not part of the season the engine learns)."""
    alone = scout_team(iter(league), A, "LIGA")
    assert scopes["liga"]["zones"]["league"] == alone["zones"]["league"]
    assert scopes["liga"]["origin"] == alone["origin"]
    assert {k: v for k, v in scopes["liga"].items() if k != "games"} == {k: v for k, v in alone.items() if k != "games"}


def test_a_team_that_did_not_play_the_extra_games_gets_none_of_them(league, cup):
    result = scout_team_scopes(iter(league), A, "LIGA", extra={"copa": iter([dated(cup[0], "14-10-2026 - 20:00", 9102)])})
    only_other = copy.deepcopy(cup[0])
    for team in only_other["HEADER"]["TEAM"]:
        team["id"] = "555" + str(team["id"])
    only_other["_id"] = 9103
    stranger = scout_team_scopes(iter(league), A, "LIGA", extra={"copa": iter([only_other])})
    assert "copa" not in stranger and "todo" not in stranger and set(stranger) == {"liga"}
    assert set(result) == {"liga", "copa", "todo"}


def test_without_extra_games_there_is_only_the_league_scope(league):
    assert set(scout_team_scopes(iter(league), A, "LIGA")) == {"liga"}


def test_a_team_that_only_played_the_cup_still_has_a_cup_scope(feb_game_doc, cup):
    elsewhere = [dated(feb_game_doc, "10-10-2026 - 17:00", 9201)]
    for team in elsewhere[0]["HEADER"]["TEAM"]:
        team["id"] = "777" + str(team["id"])
    for side in elsewhere[0]["BOXSCORE"]["TEAM"]:
        side["id"] = "777" + str(side["id"])
    result = scout_team_scopes(iter(elsewhere), A, "LIGA", extra={"copa": iter(cup)})
    assert set(result) == {"copa"}                                            # nothing in the league: no league scope and no grouped one repeating the cup


def test_no_games_at_all_is_an_error_as_before(feb_game_doc):
    with pytest.raises(ValueError, match="no tiene partidos"):
        scout_team_scopes(iter([feb_game_doc]), "000", "LIGA", extra={})


def test_a_game_against_a_team_of_another_category_is_marked(league, cup):
    result = scout_team_scopes(iter(league), A, "LIGA", extra={"copa": iter(cup)}, levels={A: 1, B: 3})
    assert {g["other_level"] for g in result["copa"]["games"]} == {True}
    assert {g["level_gap"] for g in result["copa"]["games"]} == {2}                # the rival is two categories below
    same = scout_team_scopes(iter(league), A, "LIGA", extra={"copa": iter(cup)}, levels={A: 1, B: 1})
    assert {g["other_level"] for g in same["copa"]["games"]} == {False}


def test_unknown_levels_say_nothing(league, cup):
    games = scout_team_scopes(iter(league), A, "LIGA", extra={"copa": iter(cup)})["copa"]["games"]
    assert all("other_level" not in g for g in games)


def test_a_scope_name_that_would_clash_with_the_reserved_ones_is_refused(league, cup):
    for reserved in ("liga", "todo"):
        with pytest.raises(ValueError, match="reservad"):
            scout_team_scopes(iter(league), A, "LIGA", extra={reserved: iter(cup)})
