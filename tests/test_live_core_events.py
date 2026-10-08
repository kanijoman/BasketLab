"""Parsing of FEB play-by-play lines into normalised events (no database needed)."""

import pytest

from src.live_core.events import parse_line


def _line(action, text, **kw):
    base = {"num": "7", "quarter": "2", "time": "05:30", "idTeam": "T1", "idPlayer": "P1",
            "action": action, "text": text, "scoreA": None, "scoreB": None, "deleted": None}
    base.update(kw)
    return base


def test_substitution_directions():
    e_in = parse_line(_line("subst", "(A) J. PEREZ: Sustitución (Entra a pista)"))
    e_out = parse_line(_line("subst", "(A) J. PEREZ: Sustitución (Sale de pista)"))
    assert (e_in.kind, e_out.kind) == ("sub_in", "sub_out")
    assert e_in.name == "J. PEREZ" and e_in.player_id == "P1" and e_in.team_id == "T1"


def test_substitution_tolerates_broken_accents():
    """The stored sample has mojibake in accented words."""
    assert parse_line(_line("subst", "(A) X: Sustituci�n (Entra a pista)")).kind == "sub_in"


def test_clock_and_elapsed():
    e = parse_line(_line("shoot", "(A) X: TIRO DE 2 FALLADO", quarter="2", time="05:30"))
    assert (e.period, e.remaining, e.elapsed) == (2, 330, 600 + 270)
    assert e.num == 7


@pytest.mark.parametrize(
    "text, kind, made, points",
    [
        ("(A) X: TIRO DE 2 ANOTADO (Puntos: 10)", "fg2", True, 2),
        ("(A) X: TIRO DE 2 FALLADO", "fg2", False, 0),
        ("(A) X: TIRO DE 3 ANOTADO (Puntos: 3)", "fg3", True, 3),
        ("(A) X: TIRO DE 3 FALLADO", "fg3", False, 0),
    ],
)
def test_field_goals(text, kind, made, points):
    e = parse_line(_line("shoot", text))
    assert (e.kind, e.made, e.points) == (kind, made, points)


def test_free_throws():
    made = parse_line(_line("fthrow", "(A) X: TIRO DE 1 ANOTADO (Puntos: 5)"))
    missed = parse_line(_line("fthrow", "(A) X: TIRO DE 1 FALLADO"))
    assert (made.kind, made.made, made.points) == ("ft", True, 1)
    assert (missed.kind, missed.made, missed.points) == ("ft", False, 0)


def test_personal_foul_carries_player_count():
    e = parse_line(_line(
        "foul", "(A) X: FALTA Personal (Faltas: 3. Faltas de equipo: 17). Tiros libres: 2"))
    assert (e.kind, e.foul_type, e.pf_count) == ("foul", "personal", 3)


def test_unsportsmanlike_foul():
    e = parse_line(_line("foul", "(A) X: FALTA Antideportiva (Faltas: 2. Faltas de equipo: 4). Tiros libres: 2"))
    assert (e.kind, e.foul_type, e.pf_count) == ("foul", "unsportsmanlike", 2)


@pytest.mark.parametrize(
    "action, text, kind",
    [
        ("rebound", "(A) X: REBOTE (Rebotes: 3)", "rebound"),
        ("lose", "(A) X: P�RDIDA (P�rdidas: 2)", "turnover"),
        ("recovery", "(A) X: ROBO (Robos: 1)", "steal"),
        ("assist", "(A) X: ASISTENCIA (Asistencias: 4)", "assist"),
        ("blockshot", "(A) X: TAP�N (Tapones: 1)", "block"),
        ("timeout", "(A) Tiempo muerto", "timeout"),
    ],
)
def test_other_kinds(action, text, kind):
    assert parse_line(_line(action, text)).kind == kind


def test_period_markers():
    start = parse_line(_line("period", "Comienzo del Cuarto 4", quarter="4", time="10:00",
                             idTeam=None, idPlayer=None))
    end = parse_line(_line("period", "Fin del Cuarto 4", quarter="4", time="00:00",
                           idTeam=None, idPlayer=None))
    assert (start.kind, end.kind) == ("period_start", "period_end")


def test_deleted_flag_is_exposed():
    assert parse_line(_line("shoot", "(A) X: TIRO DE 2 FALLADO", deleted="1")).deleted is True
    assert parse_line(_line("shoot", "(A) X: TIRO DE 2 FALLADO")).deleted is False


def test_unknown_or_malformed_lines_return_none_or_other():
    assert parse_line({"num": None, "action": "shoot"}) is None
    assert parse_line(_line("weird", "???")).kind == "other"
