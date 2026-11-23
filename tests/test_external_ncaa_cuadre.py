"""The reconciliation of the play by play with the official box (#888, D4; criterion of #884): before a game of ESPN is published, what the plays say each team did is compared, statistic by statistic,
with what the box says, and a game that does not match is kept but marked as not reliable.

Measured on 23/11/2026 with real games: points, field goals, threes and free throws match the sum of the players of the box; rebounds, turnovers, steals, blocks and fouls match the TOTALS of the
team (which include what the team itself did: a team rebound or turnover has no player in the box); a technical foul of a player counts as a foul of the team and one of the bench does not.
One real game came with the play by play EMPTY and its box complete (Wyoming at San Diego State): it cannot be checked and is not reliable.
"""
import copy

import pytest

from ncaa_helpers import fixture

from src.external.ncaa_cuadre import reconcile
from src.external.ncaa_page import parse_summary

REAL = ["game_mens_401829197", "game_mens_ot_401812120", "game_mens_nond1_401823428", "game_womens_401825641", "game_womens_ot_401827769", "game_womens_nond1_401817303"]


def game(name):
    return parse_summary(fixture(name))


@pytest.mark.parametrize("name", REAL)
def test_the_real_games_match_in_every_statistic(name):
    result = reconcile(game(name))
    assert result == {"reliable": True, "problems": []}


def test_a_technical_foul_of_a_player_counts_as_a_foul_of_the_team_and_one_of_the_bench_does_not():
    """Coppin State had two technicals in the women's overtime game, one on a player (counted by ESPN) and one on the team (not): 23 personal fouls + 1 = the 24 of the box."""
    assert reconcile(game("game_womens_ot_401827769"))["reliable"] is True


def test_a_game_whose_play_by_play_came_empty_cannot_be_checked_and_is_not_reliable():
    result = reconcile(game("game_womens_noplays_401830444"))
    assert result["reliable"] is False and any("play by play" in p for p in result["problems"])


def test_a_play_that_ESPN_lost_is_said_with_the_team_and_the_statistic():
    broken = game("game_mens_401829197")
    index = next(i for i, p in enumerate(broken["plays"]) if p["text"] == "Jalen Warley Steal.")
    del broken["plays"][index]
    result = reconcile(broken)
    assert result["reliable"] is False and result["problems"] == ["team 2250 stl: the plays say 13, the box 14"]


def test_a_made_shot_missing_breaks_the_points_and_the_shooting_of_its_team():
    broken = game("game_womens_401825641")
    made = next(i for i, p in enumerate(broken["plays"]) if p["scoring"] and p["points_attempted"] == 2)
    team = broken["plays"][made]["team_id"]
    del broken["plays"][made]
    problems = reconcile(broken)["problems"]
    assert any(p.startswith(f"team {team} pts:") for p in problems) and any(p.startswith(f"team {team} fgm:") for p in problems)


def test_a_box_that_does_not_add_up_to_the_score_is_said():
    broken = copy.deepcopy(game("game_mens_401829197"))
    next(p for p in broken["players"]["265"] if p["stats"])["stats"]["pts"] += 2
    assert any("box" in p and "265" in p for p in reconcile(broken)["problems"])
