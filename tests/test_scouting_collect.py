"""What the live engine sees of ONE team over its games (issue #299): the data of the rival scouting report.

The team is a parameter: nothing here knows a team id except through the fixture game.
"""

import copy

import pytest

from src.live_prep.scouting_collect import scout_team

A, B = "982047", "981204"          # the two teams of the sample game


def dated(doc, start):
    out = copy.deepcopy(doc)
    out["HEADER"]["starttime"] = start
    return out


@pytest.fixture()
def two_games(feb_game_doc):
    return [dated(feb_game_doc, "10-10-2026 - 17:00"), dated(feb_game_doc, "17-10-2026 - 17:00")]


@pytest.fixture(scope="module")
def one(feb_game_doc):
    return scout_team([dated(feb_game_doc, "10-10-2026 - 17:00")], A)


def test_the_team_and_its_games(one):
    assert one["team"]["id"] == A and one["team"]["name"]
    assert one["sample_games"] == 1
    [game] = one["games"]
    assert game["opponent_id"] == B and game["opponent"]
    assert game["margin"] == game["score_for"] - game["score_against"]
    assert game["date"].startswith("2026-10-10") and isinstance(game["home"], bool)


def test_it_works_for_either_side_of_the_game(feb_game_doc):
    other = scout_team([dated(feb_game_doc, "10-10-2026 - 17:00")], B)
    mine = scout_team([dated(feb_game_doc, "10-10-2026 - 17:00")], A)
    assert other["games"][0]["margin"] == -mine["games"][0]["margin"]
    assert other["games"][0]["home"] != mine["games"][0]["home"]


def test_a_team_without_games_is_an_error_not_an_empty_report(feb_game_doc):
    with pytest.raises(ValueError, match="no tiene partidos"):
        scout_team([feb_game_doc], "000")


def test_players_with_their_production_and_clutch(one):
    players = one["players"]
    assert players and players == sorted(players, key=lambda p: -p["pts"])
    top = players[0]
    assert top["games"] == 1 and top["minutes"] > 0 and top["pts_per_game"] == top["pts"]
    assert set(top["clutch"]) >= {"fga", "fta", "ftm", "tov", "pts", "sec"}
    assert 0 < sum(p["share"] for p in players) <= 1.0001


def test_lineups_most_used_first_with_names_and_net_per_40(one):
    rows = one["lineups"]
    assert rows and [r["seconds"] for r in rows] == sorted((r["seconds"] for r in rows), reverse=True)
    assert all(len(r["players"]) == 5 and all(isinstance(n, str) for n in r["players"]) for r in rows)
    r = rows[0]
    assert r["net40"] == pytest.approx((r["pts_for"] - r["pts_against"]) / r["seconds"] * 2400, abs=0.1)


def test_zones_of_its_shots_and_of_the_shots_it_conceded(one):
    own, conceded, league = one["zones"]["own"], one["zones"]["conceded"], one["zones"]["league"]
    assert own and conceded and league
    assert all(set(c) >= {"a", "m", "pts"} for c in own.values())
    assert sum(c["a"] for c in own.values()) > 0


def test_quarter_scoring_adds_up_to_the_final_score(one):
    quarters = one["quarters"]
    assert set(quarters) >= {"1", "2", "3", "4"}
    game = one["games"][0]
    assert sum(q["for"] for q in quarters.values()) == pytest.approx(game["score_for"])
    assert sum(q["against"] for q in quarters.values()) == pytest.approx(game["score_against"])
    assert all(q["margin"] == pytest.approx(q["for"] - q["against"]) for q in quarters.values())


def test_quarter_starts_and_closes(one):
    edges = one["edges"]
    assert set(edges) == {"start", "close"}
    assert set(edges["start"]) == {"1", "2", "3", "4"} == set(edges["close"])


def test_timeouts_and_what_follows_them(one):
    t = one["timeouts"]
    assert set(t) >= {"per_game", "first_half", "second_half", "after_for", "after_against", "after_n"}
    assert t["per_game"] == pytest.approx(t["first_half"] + t["second_half"], abs=1e-9) or t["per_game"] >= t["first_half"] + t["second_half"]


def test_four_factors_pace_and_possessions(one):
    f = one["factors"]
    assert set(f["own"]) == set(f["rival"]) == {"efg", "tov", "orb", "ftr"}
    assert 40 < one["pace"] < 120


def test_alerts_of_its_side_with_how_often_and_when(one):
    alerts = one["alerts"]
    assert alerts == sorted(alerts, key=lambda a: -a["count"])
    for a in alerts:
        assert a["count"] >= 1 and a["games"] == 1 and 0 <= a["avg_minute"] <= 40 and a["message"]
        assert a["per_game"] == a["count"] / one["sample_games"]


def test_two_games_average_and_the_second_sees_the_first(two_games):
    both = scout_team(two_games, A)
    assert both["sample_games"] == 2 and len(both["games"]) == 2
    assert both["players"][0]["games"] == 2
    assert both["players"][0]["pts_per_game"] == both["players"][0]["pts"] / 2


def test_games_can_be_a_generator_and_progress_is_reported(two_games):
    seen = []
    result = scout_team((g for g in two_games), A, progress=seen.append)
    assert result["sample_games"] == 2 and seen and seen[-1] == 2


def test_only_plain_python_types(one):
    import json

    json.dumps(one)       # numpy scalars or sets would fail here


def test_alerts_about_the_opponents_of_the_team_are_not_part_of_its_scouting(one):
    """The engine also warns about the RIVAL of the perspective (hot shooters, fouls...): that is not about the scouted team."""
    ids = {a["id"] for a in one["alerts"]}
    assert not {i for i in ids if i.startswith("rival_") and i != "rival_run"}
    assert "period_summary" not in ids
