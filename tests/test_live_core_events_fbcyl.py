"""FBCYL moves normalised into the same events as FEB lines (#350), so one possession tracker serves both formats."""
import json
from pathlib import Path

import pytest

from src.live_core.events_fbcyl import parse_move, parse_moves
from src.live_core.possessions import track

_SAMPLE = Path(__file__).resolve().parent.parent / "src" / "JSON_samples" / "fbcyl_game.json"


def _move(text, period=1, minute=9, second=30, team=10, actor=7, **extra):
    base = {"idTeam": team, "actorId": actor, "actorName": "A. PLAYER", "move": text, "period": period, "min": minute,
            "sec": second, "score": "0-0", "teamAction": False}
    base.update(extra)
    return base


@pytest.mark.parametrize("text, kind, made, points", [
    ("Canasta de 2", "fg2", True, 2),
    ("Canasta de 3", "fg3", True, 3),
    ("Canasta de 1", "ft", True, 1),
    ("Intento fallado de 2", "fg2", False, 0),
    ("Intento fallado de 3", "fg3", False, 0),
    ("Intento fallado de 1", "ft", False, 0),
    ("Mate", "fg2", True, 2),            # a dunk line follows its own offensive rebound; the score moves on "Mate"
    ("Mate fuera", "fg2", False, 0),
])
def test_shots_and_free_throws(text, kind, made, points):
    ev = parse_move(_move(text), 5)

    assert (ev.kind, ev.made, ev.points, ev.team_id, ev.player_id, ev.num) == (kind, made, points, "10", "7", 6)


@pytest.mark.parametrize("text, kind", [
    ("Rebote ofensivo", "rebound"), ("Rebote defensivo", "rebound"), ("Pérdida", "turnover"), ("P�rdida", "turnover"),
    ("Recuperación", "steal"), ("Recuperaci�n", "steal"), ("Asistencia", "assist"), ("Tapón", "block"),
    ("Entra al campo", "sub_in"), ("Sale del campo", "sub_out"), ("Falta recibida", "other"), ("Algo nuevo", "other"),
])
def test_other_events(text, kind):
    assert parse_move(_move(text), 0).kind == kind


@pytest.mark.parametrize("text, foul_type", [
    ("Falta, 3a falta", "personal"), ("Personal 2 tiros libres, 1a falta", "personal"),
    ("Antideportiva 2 tiros libres, 4a falta", "unsportsmanlike"), ("Técnica, 1a falta", "technical"),
    ("Falta en ataque, 2a falta", "other"),
])
def test_fouls_carry_their_type_and_the_received_foul_is_not_a_second_foul(text, foul_type):
    ev = parse_move(_move(text), 0)

    assert (ev.kind, ev.foul_type) == ("foul", foul_type)


def test_clock_is_the_time_remaining_in_the_period_and_overtimes_last_five_minutes():
    """``min:sec`` counts down (the first move of a game is at 10:00): 3:15 left in period 2 is 6:45 played."""
    second = parse_move(_move("Canasta de 2", period=2, minute=3, second=15), 0)
    overtime = parse_move(_move("Canasta de 2", period=5, minute=1, second=0), 0)

    assert (second.period, second.remaining, second.elapsed) == (2, 195, 600 + 405)
    assert (overtime.remaining, overtime.elapsed) == (60, 2400 + 240)


def test_team_actions_and_period_markers():
    timeout = parse_move(_move("Tiempo muerto", team=10, teamAction=True), 0)
    end = parse_move(_move("Fin de período", team=0, minute=10, second=0, teamAction=True), 0)

    assert (timeout.kind, timeout.team_id) == ("timeout", "10")
    assert (end.kind, end.team_id) == ("period_end", None)


def test_moves_without_period_or_clock_are_dropped():
    assert parse_move({"move": "Canasta de 2", "idTeam": 1}, 0) is None
    assert parse_moves([_move("Canasta de 2"), {"move": "x"}]) and len(parse_moves([_move("Canasta de 2"), {"move": "x"}])) == 1


def test_tracker_on_the_sample_game_adds_up_to_its_score():
    game = json.loads(_SAMPLE.read_text("utf-8"))
    teams = [str(t["teamIdIntern"]) for t in game["stats"]["teams"]]

    possessions, quality = track(parse_moves(game["moves"]), teams)

    final = sorted(int(x) for x in game["moves"][-1]["score"].split("-"))
    scored = sorted(sum(p.points for p in possessions if p.team_id == t) + quality.technical_points.get(t, 0) for t in teams)
    assert scored == final
