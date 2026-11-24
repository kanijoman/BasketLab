"""A game of the Euroleague as the canonical document of an external source (#1038, D6a of epic #872): the result of ``euroleague_page.parse_game`` as the FEB document, with ``_league: euroleague`` and every id
prefixed (``euroleague:E2025_1``; the teams by their club code, ``euroleague:IST``; the players by their code, ``euroleague:009849``, the same in every season and competition).

It is written as the engine and the pipelines read the FEB document (the line writer is the one of ``fiba_canonical``, which ACB reuses too), so that nothing forks: ``HEADER`` (the kick-off in the time of Madrid,
the two teams with their points of each period), ``BOXSCORE.TEAM[]`` (the OFFICIAL box with the minutes in seconds and the bio of each player: birth, height, country and position; the TOTAL of the players and,
apart, what the team itself did; the rebounds of the team are only in its own part, its turnovers are in both) and ``PLAYBYPLAY.LINES``.

**The codes of the play by play** are the ones the real games prove (``KNOWN_CODES``; the spike measured the nine seasons since 2017/18 and the EuroCup and U18 ones): a block is ``AG`` (the shot that was
rejected) and ``FV`` (the block, for the blocker). Codes that change no statistic and FEB has no type for stay ``other`` lines with a Spanish text. The old codes of before 2017/18 (``DUNK``, ``LAYUPMD``…) are not
here: those seasons are not loaded (the play by play does not agree with the box before 2017/18).

**The shot chart** is written only when it is complete: every field goal of the play by play has its shot (they join by the number of the play), as FEB's chart is exactly the field goals of the play by play and
one with some missing would make every zone look different. The coordinates are centimetres from the hoop (``x`` across, ``y`` along) and go through ``feb_coordinates`` of ACB. The side (left or right) of the
shots across the court has no source to be checked against: the zone families (corner, wing, top) do not depend on it.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple
from zoneinfo import ZoneInfo

from src.external.acb_canonical import feb_coordinates
from src.external.euroleague_page import FIELD_GOALS
from src.external.fiba_canonical import Lines
from src.market.canonical import period_scheme, source_id

SOURCE = "euroleague"
_MADRID = ZoneInfo("Europe/Madrid")
_BOX = {"points": "pts", "freeThrowsMade": "p1m", "freeThrowsAttempted": "p1a", "fieldGoalsMade2": "p2m", "fieldGoalsAttempted2": "p2a", "fieldGoalsMade3": "p3m", "fieldGoalsAttempted3": "p3a",
        "fieldGoalsMadeTotal": "fgm", "fieldGoalsAttemptedTotal": "fga", "assistances": "assist", "blocksFavour": "bs", "steals": "st", "turnovers": "to", "offensiveRebounds": "ro",
        "defensiveRebounds": "rd", "totalRebounds": "rt", "foulsCommited": "pf", "foulsReceived": "rf", "valuation": "val"}
_SHOTS = {"2FGM": ("P2", True), "2FGA": ("P2", False), "3FGM": ("P3", True), "3FGA": ("P3", False), "FTM": ("FT", True), "FTA": ("FT", False)}
_FOULS = {"CM": "Foul", "OF": "Offensive Foul", "CMU": "Unsportsmanlike Foul", "CMT": "Technical Foul"}          # all of them move the ``foulsCommited`` of their player
_ACTIONS = {"AS": "ASS", "ST": "ST", "FV": "BS"}
# lines that change no statistic and that FEB has no type for: they stay ``other`` lines with a Spanish text
_INFO = {"AG": "TAPÓN RECIBIDO", "TOUT_TV": "TIEMPO MUERTO DE TELEVISIÓN", "JB": "SALTO", "CCH": "RECLAMACIÓN DEL ENTRENADOR", "B": "FALTA DE BANQUILLO", "C": "FALTA DEL ENTRENADOR", "EG": "FIN DEL PARTIDO"}
KNOWN_CODES = frozenset({*_SHOTS, *_FOULS, *_ACTIONS, *_INFO, "O", "D", "TO", "RV", "IN", "OUT", "TOUT", "BP", "EP"})


def _period(number: int) -> str:
    return f"Q{number}" if number <= 4 else f"OT{number - 4}"


def _starttime(utc: str) -> str:
    """``2025-09-30T17:45:00Z`` -> ``30-09-2025 - 19:45``: the time of Madrid, as FEB writes it."""
    if not utc:
        return ""
    return datetime.strptime(utc.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z").astimezone(_MADRID).strftime("%d-%m-%Y - %H:%M")


def _number(value: Any) -> str:
    return str(int(value or 0))


def _player_box(player: Dict[str, Any]) -> Dict[str, Any]:
    box = {feb: _number(player["stats"].get(key)) for key, feb in _BOX.items()}
    return {**box, "id": source_id(SOURCE, player["id"]), "name": player["name"], "no": player["number"], "min": str(player["seconds"]), "sta": "*" if player["started"] else None,
            "birth": player["birth"], "height": str(player["height_cm"]) if player["height_cm"] else None, "nationality": player["nationality"], "position": player["position"], "club": None}


def _team_box(team: Dict[str, Any], won: bool) -> Dict[str, Any]:
    boxes = [_player_box(p) for p in team["players"]]
    total = {feb: str(sum(int(b[feb]) for b in boxes)) for feb in _BOX.values()}
    own = {feb: _number(team["own"].get(key)) for key, feb in (("offensiveRebounds", "ro"), ("defensiveRebounds", "rd"), ("totalRebounds", "rt"), ("turnovers", "to"), ("foulsCommited", "pf"))}
    total["to"] = _number(team["totals"].get("turnovers"))                       # as FEB and the other sources do: the turnovers of the team itself are in the official total (the play by play counts them all)
    return {"id": source_id(SOURCE, team["code"]), "name": team["name"], "teamCode": team["code"], "win_lose": "W" if won else "L", "TOTAL": total, "TEAMACTIONS": own, "PLAYER": boxes}


def _clock(play: Dict[str, Any]) -> str:
    """The clock that remains; the marks of a period have none: it begins with all its minutes and ends at zero."""
    if play["clock"]:
        return play["clock"]
    return ("10:00" if play["period"] <= 4 else "05:00") if play["type"] == "BP" else "00:00"


def _events(game: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The plays as the events ``fiba_canonical.Lines`` writes. A play that says no score keeps the last one."""
    events: List[Dict[str, Any]] = []
    score = [0, 0]
    for play in game["plays"]:
        for side, key in enumerate(("score_home", "score_away")):
            score[side] = play[key] if play[key] is not None else score[side]
        kind = play["type"]
        event = {"code": "OTHER", "team": play["team"], "player": play["player"], "player2": None, "made": False, "text": _INFO.get(kind, f"Euroliga código {kind}"), "in": None,
                 "period": _period(play["period"]), "clock": _clock(play), "score_a": score[0], "score_b": score[1]}
        if kind in _SHOTS:
            event.update(code=_SHOTS[kind][0], made=_SHOTS[kind][1], text="")
        elif kind in ("O", "D"):
            event.update(code="REB" if play["player"] else "TREB", text="Offensive Rebound" if kind == "O" else "Defensive Rebound")
        elif kind in _ACTIONS:
            event.update(code=_ACTIONS[kind], text="")
        elif kind == "TO":
            event.update(code="TO" if play["player"] else "TTO", text="")
        elif kind in _FOULS:
            event.update(code="FOUL", text=_FOULS[kind])
        elif kind == "RV":
            event.update(code="RFOUL", text="Foul Received")
        elif kind in ("IN", "OUT"):
            event.update(code="SUBST", text="", **{"in": kind})
        elif kind == "TOUT":
            event.update(code="TIMO", text="")
        elif kind in ("BP", "EP"):
            event.update(code="STARTP" if kind == "BP" else "ENDP", text="")
        events.append(event)
    return events


def _lines_game(game: Dict[str, Any]) -> Dict[str, Any]:
    """What ``fiba_canonical.Lines`` asks of a game: its teams (``org_id`` and name) and their players (``person_id`` and name)."""
    return {"teams": [{"org_id": t["code"], "name": t["name"], "players": [{"person_id": p["id"], "name": p["name"]} for p in t["players"]]} for t in game["teams"]]}


def chart_shots(game: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], int, int]:
    """``(FEB shots, how many field goals have one, how many field goals there are)``: the shots of ``Points`` put on the field goals of the play by play by the number of the play and written as FEB writes
    them: ``m`` (``1`` in), ``t`` (the clock that remains), ``x`` and ``y`` (percentages of the court), ``team`` (the slot, ``0`` home), ``player`` (the dorsal) and ``quarter``. In the order of the game."""
    goals = {p["number"]: p for p in game["plays"] if p["type"] in FIELD_GOALS}
    home = game["teams"][0]["code"]
    chart = []
    for shot in game["shots"]:
        play = goals.get(shot["number"])
        if play is None:
            continue
        slot = 0 if play["team"] == home else 1
        x_pct, y_pct = feb_coordinates(shot["y"] * 10.0, shot["x"] * 10.0, slot)             # the API: x across and y along, in centimetres; ACB: along and across, in millimetres
        chart.append({"m": "1" if shot["made"] else "0", "t": _clock(play), "x": str(x_pct), "y": str(y_pct), "team": str(slot), "player": play["dorsal"] or "", "quarter": str(play["period"])})
    return chart, len(chart), len(goals)


def to_canonical(game: Dict[str, Any], entry: Dict[str, Any]) -> Dict[str, Any]:
    """The canonical document of a game as ``euroleague_page.parse_game`` read it, for the competition ``entry`` of the catalogue (its name, season and gender: ``ValueError`` if the gender is not ``M`` or ``F``).
    The game read is not changed."""
    scheme = period_scheme(SOURCE, entry["gender"])
    home, away = game["teams"]
    quarters = [{"n": str(i), "scoreA": str(a), "scoreB": str(b)} for i, (a, b) in enumerate(zip(home["periods"], away["periods"]), start=1)]
    header = {"CompID": game["season_code"], "competition": entry["competition"], "round": game["round"], "quarter": len(quarters), "time": "FINAL", "logo": None, "duration": None,
              "starttime": _starttime(game["utc_date"]), "place": None, "field": None, "status": "3", "statusText": "FINISHED",
              "TEAM": [{"pts": str(t["score"]), "fouls": None, "id": source_id(SOURCE, t["code"]), "name": t["name"], "logo": None, "teamCode": t["code"], "clubCode": None} for t in (home, away)],
              "QUARTERS": {"QUARTER": quarters}, "game_code": str(game["game_code"])}
    boxes = [_team_box(home, home["score"] > away["score"]), _team_box(away, away["score"] > home["score"])]
    shots, covered, total = chart_shots(game)
    complete = total > 0 and covered == total
    teams = [{"id": b["id"], "name": b["name"], "teamCode": b["teamCode"], "PLAYER": [{"id": p["id"], "no": p["no"], "name": p["name"]} for p in b["PLAYER"]]} for b in boxes]
    return {"_id": source_id(SOURCE, f"{game['season_code']}_{game['game_code']}"), "_league": SOURCE, "_season": str(entry["season_value"]), "HEADER": header,
            "PLAYBYPLAY": {"duration": None, "hasExtension": len(quarters) > scheme.periods, "LINES": Lines(_lines_game(game), SOURCE).build(_events(game))},
            "BOXSCORE": {"duration": None, "TEAM": boxes},
            "SHOTCHART": {"quarters": None, "duration": None, "TEAM": teams if complete else [], "SHOTS": shots if complete else []}}
