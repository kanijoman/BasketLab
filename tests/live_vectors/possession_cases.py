"""Vector cases of the possession tracker (#350); imported by ``generate.py``.

Each case is ``["lines", ["team A", "team B"]]``: FEB lines (parsed by ``events.parse_line``) in, the possessions of the
game and the quality of its feed out. Python and Pyodide must agree on every field.
"""


def _line(num, team, player, action, text, clock, quarter="1"):
    return {"num": str(num), "quarter": quarter, "time": clock, "idTeam": team, "idPlayer": player, "action": action,
            "text": f"(X) {text}", "scoreA": None, "scoreB": None, "deleted": None}


def _scenario(*rows):
    """rows: (team, player, action, text, clock) in order; num = position."""
    return [_line(i + 1, *row) for i, row in enumerate(rows)]


MADE2, MISS2 = "A. P: TIRO DE 2 ANOTADO (Puntos: 8)", "A. P: TIRO DE 2 FALLADO"
MADE3, MISS3 = "A. P: TIRO DE 3 ANOTADO (Puntos: 8)", "A. P: TIRO DE 3 FALLADO"
FT_OK, FT_MISS = "A. P: TIRO DE 1 ANOTADO (Puntos: 5)", "A. P: TIRO DE 1 FALLADO"
REB, TEAM_REB = "A. P: REBOTE (Rebotes: 3)", "REBOTE (Rebotes: 3)"
TOV, STEAL = "A. P: PÉRDIDA (Pérdidas: 1)", "A. P: ROBO (Robos: 1)"
FOUL = "A. P: FALTA Personal (Faltas: 1. Faltas de equipo: 1)"
TECH = "A. P: FALTA Técnica (Faltas: 1. Faltas de equipo: 1)"
UNSPORT = "A. P: FALTA Antideportiva (Faltas: 1. Faltas de equipo: 1)"


def scenarios():
    return {
        "alternation": _scenario(("A", "a1", "shoot", MADE2, "09:50"), ("B", "b1", "shoot", MADE3, "09:30"),
                                 ("A", "a1", "shoot", MISS2, "09:10"), ("B", "b2", "rebound", REB, "09:09"),
                                 ("B", "b1", "shoot", MADE2, "08:50")),
        "second chance and team rebounds": _scenario(
            ("A", "a1", "shoot", MISS3, "09:50"), ("A", None, "rebound", TEAM_REB, "09:49"), ("A", "a2", "shoot", MADE2, "09:40"),
            ("B", "b1", "shoot", MISS2, "09:20"), ("A", None, "rebound", TEAM_REB, "09:19"), ("A", "a1", "lose", TOV, "09:00")),
        "steal both orders": _scenario(
            ("A", "a1", "lose", TOV, "09:50"), ("B", "b1", "recovery", STEAL, "09:50"), ("B", "b1", "shoot", MADE2, "09:40"),
            ("B", "b2", "recovery", STEAL, "09:20"), ("A", "a1", "lose", TOV, "09:20"), ("A", "a1", "shoot", MADE2, "09:00")),
        "and one and free throw trips": _scenario(
            ("A", "a1", "shoot", MADE2, "09:50"), ("B", "b1", "foul", FOUL, "09:50"), ("A", "a1", "fthrow", FT_OK, "09:50"),
            ("B", "b1", "foul", FOUL, "09:30"), ("A", "a2", "fthrow", FT_OK, "09:30"), ("A", "a2", "fthrow", FT_MISS, "09:30"),
            ("B", "b2", "rebound", REB, "09:29"), ("B", "b1", "shoot", MADE3, "09:10")),
        "technical free throws keep the ball": _scenario(
            ("B", "b1", "lose", TOV, "09:55"), ("A", "a1", "foul", TECH, "09:40"), ("B", "b1", "fthrow", FT_OK, "09:40"),
            ("B", "b1", "fthrow", FT_MISS, "09:40"), ("A", "a2", "shoot", MADE2, "09:30"), ("B", "b2", "shoot", MADE2, "09:10")),
        "technical between a miss and its rebound": _scenario(
            ("A", "a1", "shoot", MISS2, "09:50"), ("B", "b1", "foul", TECH, "09:49"), ("A", "a2", "fthrow", FT_OK, "09:49"),
            ("B", "b2", "rebound", REB, "09:48"), ("B", "b2", "shoot", MADE2, "09:30")),
        "unsportsmanlike trip": _scenario(
            ("B", "b1", "foul", UNSPORT, "09:50"), ("A", "a1", "fthrow", FT_OK, "09:50"), ("A", "a1", "fthrow", FT_MISS, "09:50"),
            ("A", "a2", "shoot", MADE2, "09:30"), ("B", "b1", "shoot", MADE2, "09:10")),
        "feed gap and misattributed rebound": _scenario(
            ("A", "a1", "shoot", MADE2, "09:50"), ("A", "a1", "shoot", MADE2, "09:30"),
            ("A", "a2", "shoot", MISS2, "09:10"), ("B", "b1", "rebound", REB, "09:09"), ("A", "a2", "shoot", MADE2, "09:00"),
            ("B", None, "rebound", TEAM_REB, "08:30"), ("A", "a1", "shoot", MADE3, "08:20")),
        "period boundaries": _scenario(
            ("A", "a1", "shoot", MADE2, "09:50"), ("A", "a2", "shoot", MISS2, "00:05")) + [
            {"num": "3", "quarter": "1", "time": "00:00", "idTeam": None, "idPlayer": None, "action": "period",
             "text": "Fin del Cuarto 1", "scoreA": None, "scoreB": None, "deleted": None},
            {"num": "4", "quarter": "2", "time": "10:00", "idTeam": None, "idPlayer": None, "action": "period",
             "text": "Comienzo del Cuarto 2", "scoreA": None, "scoreB": None, "deleted": None},
            _line(5, "B", "b1", "shoot", MADE2, "09:40", "2")],
    }


def possession_cases(case, game_lines):
    """``case(fn, args)`` builder of generate.py; ``game_lines``: the lines of the sample game (a real excerpt)."""
    out = [case("possessions.track", [lines, ["A", "B"]]) for lines in scenarios().values()]
    excerpt = [l for l in sorted(game_lines, key=lambda l: int(l["num"])) if l.get("action") != "subst"][:160]
    ids = sorted({str(l["idTeam"]) for l in excerpt if l.get("idTeam")})
    out.append(case("possessions.track", [excerpt, ids]))
    return out
