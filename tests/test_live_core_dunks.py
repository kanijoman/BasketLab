"""Dunks ("MATE ANOTADO" / "MATE FALLADO") are field goals of the live state (#365).

Regression: the FEB feed writes a dunk as ``MATE ...`` instead of ``TIRO DE 2 ...``; they were parsed as "other",
so a made dunk did not add its 2 points (2524455 ended 99-67 instead of the official 101-71) and a missed one did
not open a rebound (the tip-in rebound after it was then counted as defensive).
"""
from src.live_core.events import parse_line
from src.live_core.state import LiveGame


def _line(num, team, player, action, text, clock="09:00"):
    return {"num": str(num), "quarter": "1", "time": clock, "idTeam": team, "idPlayer": player,
            "action": action, "text": f"(X) {text}", "deleted": None}


def _play(*lines):
    game = LiveGame([("T1", "Home"), ("T2", "Away")])
    for line in lines:
        game.apply(parse_line(line))
    return game


def test_made_dunk_scores_two_points_and_counts_as_a_field_goal_regression():
    game = _play(_line(1, "T1", "P1", "shoot", "A. PLAYER: MATE ANOTADO (Puntos: 2)"))

    assert game.score == {"T1": 2, "T2": 0}
    stats = game.teams["T1"].stats
    assert (stats["fg2m"], stats["fg2a"], stats["pts"]) == (1, 1, 2)


def test_missed_dunk_opens_an_offensive_rebound_for_the_same_team_regression():
    game = _play(
        _line(1, "T1", "P1", "shoot", "A. PLAYER: MATE FALLADO", "09:00"),
        _line(2, "T1", "P1", "rebound", "A. PLAYER: REBOTE (Rebotes: 1)", "08:59"),
    )

    stats = game.teams["T1"].stats
    assert (stats["fg2a"], stats["fg2m"]) == (1, 0)
    assert (stats["orb"], stats["drb"]) == (1, 0)


def test_missed_dunk_followed_by_a_rival_rebound_is_a_defensive_rebound():
    game = _play(
        _line(1, "T1", "P1", "shoot", "A. PLAYER: MATE FALLADO", "09:00"),
        _line(2, "T2", "P9", "rebound", "B. PLAYER: REBOTE (Rebotes: 1)", "08:59"),
    )

    assert (game.teams["T2"].stats["drb"], game.teams["T2"].stats["orb"]) == (1, 0)
