"""A FBCYL game in the shape of a FEB document (issue #445, epic #435).

``{uuid, moves[], stats}`` -> ``{_id, HEADER, BOXSCORE (roster), PLAYBYPLAY.LINES, SHOTCHART}``: what the live engine, the package builder, the
rule evaluator and the demo generator read, so they work on FBCYL without a second code path. Differences of the feed that this resolves:

* ``idTeam`` of a move is ``teamIdIntern`` (per game); the document uses ``teamIdExtern`` (stable between games and seasons), home first.
* ``min``/``sec`` of a move is the time REMAINING in the period, the same as FEB's ``time``; the moves have no number, their position is the order.
* The text of a move is matched without accents (the stored data has mojibake). "Falta recibida" is the same foul seen from the victim and has
  no FEB counterpart: it is dropped. Offensive and defensive rebounds are one ``rebound`` line (the engine decides which it is, as in FEB).
* The shots come with the coordinates in the players' stats (``shootingOf{Two,Three}{Successful,Failed}Point``): they become ``SHOTCHART.SHOTS`` with ``folded`` (FBCYL folds both teams
  into one half court, so the zone of a shot is that of ``feb_to_fiba(x, y, 0)`` whoever shot it). No roster mark of "formación".
* The play-by-play is annotated by the clubs and has errors the feed does not fix: ``HEADER.source = "fbcyl"`` lets consumers label it experimental.

``from_streaming`` does the same for a match IN PROGRESS, read from the web's streaming service (``streaming/match-id/{adGameId}``, issue #446): its body is the stats and the moves
together, its moves are written in CATALAN (``idMove`` is the same number as in ``msstats``, so it decides what a move is) and the header carries the period and the clock remaining.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Tuple

SOURCE = "fbcyl"
_TIME = re.compile(r"([A-Za-z]{3})\w*\s+(\d{1,2}),\s*(\d{4}),\s*(\d{1,2}):(\d{2}):(\d{2})\W*([AP]M)", re.IGNORECASE)
_FOUL_N = re.compile(r"(\d+)a falta", re.IGNORECASE)
_SHOT = re.compile(r"^(canasta|intento fallado) de ([123])$")
_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}


def starttime(stats: Dict[str, Any]) -> Optional[str]:
    """``Oct 3, 2026, 6:30:00 PM`` (the feed's text, with a narrow no-break space or its mojibake before PM) as FEB's ``03-10-2026 - 18:30``."""
    match = _TIME.search(str(stats.get("time") or ""))
    if not match or match.group(1).lower() not in _MONTHS:
        return None
    hour = int(match.group(4)) % 12 + (12 if match.group(7).upper() == "PM" else 0)
    when = datetime(int(match.group(3)), _MONTHS[match.group(1).lower()], int(match.group(2)), hour, int(match.group(5)))
    return when.strftime("%d-%m-%Y - %H:%M")


# idMove -> the text msstats gives it (Castilian). The streaming service writes the same moves in Catalan («Cistella de 2», «Surt del camp») with the SAME idMove, so the code decides;
# a code that is not here (a type of move none of the real games had) keeps its own text and, if the words do not say what it is, it is ``other`` (ignored by the engine).
_MOVE_ES = {
    92: "Canasta de 1", 93: "Canasta de 2", 94: "Canasta de 3", 96: "Intento fallado de 1", 97: "Intento fallado de 2", 98: "Intento fallado de 3",
    101: "Rebote ofensivo", 102: "Tapón", 103: "Recuperación", 104: "Rebote defensivo", 106: "Pérdida", 107: "Asistencia", 110: "Falta recibida",
    112: "Entra al campo", 113: "Tiempo muerto", 115: "Sale del campo", 116: "Fin de período",
}
_FOUL_CODE = 531      # «Falta, 3a falta» (msstats) and «Falta» / «Falta, 3a falta» (streaming): the count is the player's, the adapter counts it when the text has none


def _spanish(move: Dict[str, Any]) -> str:
    """The text of a move as msstats writes it, whatever language the feed spoke."""
    text = str(move.get("move") or "")
    if move.get("idMove") in _MOVE_ES:
        return _MOVE_ES[move["idMove"]]
    if move.get("idMove") == _FOUL_CODE and not _FOUL_N.search(text):
        return "Falta,"
    return text


def _classify(move: str) -> Tuple[str, str]:
    """``(FEB action, FEB text without the "(team) player:" prefix)`` of a move text."""
    low = move.lower().strip()
    shot = _SHOT.match(low)
    if shot:
        made, value = shot.group(1) == "canasta", int(shot.group(2))
        return ("fthrow" if value == 1 else "shoot"), f"TIRO DE {value} {'ANOTADO' if made else 'FALLADO'}"
    if low in ("mate", "mate fuera"):
        return "shoot", f"MATE {'ANOTADO' if low == 'mate' else 'FALLADO'}"
    if low.startswith("rebote"):
        return "rebound", "REBOTE"
    if low.startswith("p") and "rdida" in low:
        return "lose", "PERDIDA"
    if low.startswith("recuperaci"):
        return "recovery", "ROBO"
    if low.startswith("asistencia"):
        return "assist", "ASISTENCIA"
    if low.startswith("tap"):
        return "blockshot", "TAPON"
    if low.startswith("entra al campo"):
        return "subst", "Sustitucion (Entra a pista)"
    if low.startswith("sale del campo"):
        return "subst", "Sustitucion (Sale de pista)"
    if low.startswith("tiempo muerto"):
        return "timeout", "Tiempo muerto"
    if low.startswith("fin de"):
        return "period", "FIN"
    if low.startswith(("falta,", "falta antideportiva", "antideportiva", "falta t", "t", "falta descalificante", "descalificante", "falta en ataque")):
        return "foul", move
    return "other", move


def _foul_text(move: str, count: int) -> str:
    low = move.lower()
    kind = ("Antideportiva" if "antideportiva" in low else "Tecnica" if "cnica" in low or low.startswith("falta t") or low.startswith("t")
            else "Descalificante" if "descalificante" in low else "Ataque" if "ataque" in low else "Personal")
    return f"FALTA {kind} (Faltas: {count}. Faltas de equipo: 0)."


def _period_lengths(stats: Dict[str, Any]) -> List[int]:
    listed = [int(m) for m in (stats.get("periodDurationList") or []) if str(m).isdigit()]
    return listed or [10, 10, 10, 10]


def _teams(stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The two teams of the stats, home (``localId``) first."""
    teams = list(stats.get("teams") or [])
    home = [t for t in teams if t.get("teamIdIntern") == stats.get("localId")]
    return home + [t for t in teams if t not in home]


def _header(game: Dict[str, Any], teams: List[Dict[str, Any]], live: bool = False) -> Dict[str, Any]:
    """The header of a match that is over; ``live``: of one in progress (streaming): not FINAL, with the period and the clock remaining, and the score of the scoreboard."""
    stats = game.get("stats") or {}
    code = str(stats.get("idMatchExtern") or game.get("uuid") or "")
    last = max((int(m.get("period") or 1) for m in game.get("moves") or []), default=1)
    points = [str((t.get("data") or {}).get("score") or 0) for t in teams]
    status, text, quarter, clock = "3", "FINISHED", str(last), "FINAL"
    if live:
        board, now = stats.get("score") or {}, stats.get("matchTime") or {}
        points = [str(board.get("local", points[0])), str(board.get("visit", points[-1]))]
        status, text, quarter = "2", "EN DIRECTO", str(stats.get("period") or last)
        clock = f"{int(now.get('minute') or 0):02d}:{int(now.get('second') or 0):02d}"
    return {
        "TEAM": [{"id": str(t["teamIdExtern"]), "name": str(t.get("name") or t["teamIdExtern"]).strip(), "pts": pts} for t, pts in zip(teams, points)],
        "status": status, "statusText": text, "quarter": quarter, "time": clock, "starttime": starttime(stats),
        "game_code": code, "uuid": game.get("uuid"), "competition": game.get("_competition"), "round": None, "source": SOURCE,
    }


def _player_id(player: Dict[str, Any]) -> Any:
    """The id the moves call a player by: ``actorId`` in msstats, ``id`` in the streaming service (the same number)."""
    return player.get("actorId") or player.get("id")


def _boxscore(teams: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"TEAM": [{
        "id": str(t["teamIdExtern"]), "name": str(t.get("name") or "").strip(),
        "PLAYER": [{"id": str(_player_id(p)), "no": str(p.get("dorsal") or ""), "name": str(p.get("name") or "").strip(), "captain": bool(p.get("captain"))}
                   for p in t.get("players") or [] if _player_id(p)],
    } for t in teams]}


def _lines(game: Dict[str, Any], teams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ext = {t.get("teamIdIntern"): str(t["teamIdExtern"]) for t in teams}
    names = {str(t["teamIdExtern"]): str(t.get("name") or "").strip() for t in teams}
    lengths = _period_lengths(game.get("stats") or {})
    lines: List[Dict[str, Any]] = []
    fouls: Dict[str, int] = {}
    waiting: Dict[Any, Optional[str]] = {}       # a «Falta recibida» whose foul has not been written yet, by clock
    seen_periods = set()

    def add(period: int, minutes: int, seconds: int, team: Optional[str], player: Optional[str], action: str, text: str, score: Optional[str] = None) -> None:
        home, away = (score.split("-") + [None, None])[:2] if score else (None, None)
        lines.append({"num": str(len(lines) + 1), "quarter": str(period), "time": f"{minutes:02d}:{seconds:02d}", "idTeam": team, "idPlayer": player,
                      "idLicense": player,      # in FBCYL the licence of a player is his id: what lets the engine find who a foul was suffered by (#593)
                      "action": action, "text": text, "deleted": None, "scoreA": home, "scoreB": away, "Position": ""})

    def receiver(period: int, minutes: int, seconds: int, victim: Optional[str]) -> None:
        """«Falta recibida»: the foul it belongs to is next to it, at the same clock, before or after (checked on a real game: 37 and 37, always adjacent)."""
        clock = (str(period), f"{minutes:02d}:{seconds:02d}")
        last = lines[-1] if lines else None
        if victim and last and last["action"] == "foul" and (last["quarter"], last["time"]) == clock and not last.get("logParam4"):
            last["logParam4"] = victim
        else:
            waiting[clock] = victim            # the foul comes next

    for move in game.get("moves") or []:
        text = _spanish(move)
        try:
            period, minutes, seconds = int(move.get("period") or 1), int(move.get("min") or 0), int(move.get("sec") or 0)
        except (TypeError, ValueError):
            continue
        if text.lower().startswith("falta recibida"):
            receiver(period, minutes, seconds, str(move["actorId"]) if move.get("actorId") else None)
            continue
        if period not in seen_periods:
            seen_periods.add(period)
            length = lengths[period - 1] if period <= len(lengths) else 5
            add(period, length, 0, None, None, "period", f"Comienzo del Cuarto {period}")
        team = ext.get(move.get("idTeam"))
        player = str(move["actorId"]) if move.get("actorId") else None
        action, body = _classify(text)
        if action == "period":
            add(period, minutes, seconds, None, None, "period", f"Fin del Cuarto {period}")
            continue
        if action == "foul":
            counted = _FOUL_N.search(text)
            fouls[player or ""] = int(counted.group(1)) if counted else fouls.get(player or "", 0) + 1
            body = _foul_text(text, fouls[player or ""])
            victim = waiting.pop((str(period), f"{minutes:02d}:{seconds:02d}"), None)
        made = action in ("shoot", "fthrow") and "ANOTADO" in body
        who = str(move.get("actorName") or "").strip()
        prefix = f"({names.get(team or '', '')}) {who}: " if player else f"({names.get(team or '', '')}) "
        add(period, minutes, seconds, team, player, action, prefix + body, str(move.get("score")) if made and move.get("score") else None)
        if action == "foul" and victim:
            lines[-1]["logParam4"] = victim
    return lines


_POINT_KEYS = (("shootingOfTwoSuccessfulPoint", 1), ("shootingOfTwoFailedPoint", 0), ("shootingOfThreeSuccessfulPoint", 1), ("shootingOfThreeFailedPoint", 0))


def _points(player: Dict[str, Any]) -> Iterator[Tuple[Dict[str, Any], int]]:
    """The field goals of a player that have coordinates, with 1 if made (free throws have none that matter)."""
    for key, made in _POINT_KEYS:
        for point in (player.get("data") or {}).get(key) or []:
            if isinstance(point, dict) and "xnormalize" in point and "ynormalize" in point:
                yield point, made


def _shots(game: Dict[str, Any], teams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """``SHOTCHART.SHOTS`` of FEB from the coordinates of the players' stats. ``team`` is the index in the header's order, ``player`` the jersey number, ``t`` the clock remaining of the
    move the point belongs to (by ``eventUuid``; None when the point has no move: it still counts for its zone, only the inference of numbers needs the clock) and ``folded`` says the
    coordinates are already of one half court."""
    clocks = {m["eventUuid"]: f"{int(m.get('min') or 0):02d}:{int(m.get('sec') or 0):02d}" for m in game.get("moves") or [] if m.get("eventUuid")}
    shots: List[Dict[str, Any]] = []
    for index, team in enumerate(teams):
        for player in team.get("players") or []:
            for point, made in _points(player):
                shots.append({"m": str(made), "t": clocks.get(point.get("eventUuid")), "x": str(point["xnormalize"]), "y": str(point["ynormalize"]), "team": str(index),
                              "player": str(player.get("dorsal") or ""), "quarter": str(point.get("period") or 1), "folded": True})
    return shots


def to_feb_document(game: Dict[str, Any], live: bool = False) -> Dict[str, Any]:
    """The FEB-shaped document of a FBCYL game; the given one is not modified. ``live``: it is in progress (see ``from_streaming``)."""
    stats = game.get("stats") or {}
    teams = _teams(stats)
    header = _header(game, teams, live)
    return {
        "_id": header["game_code"], "_season": game.get("_season"), "_league": game.get("_league"), "HEADER": header, "BOXSCORE": _boxscore(teams),
        "PLAYBYPLAY": {"LINES": _lines(game, teams)}, "SHOTCHART": {"quarters": None, "duration": None, "TEAM": [], "SHOTS": _shots(game, teams)},
    }


def from_streaming(body: Dict[str, Any], finished: bool = False) -> Dict[str, Any]:
    """The FEB document of a match read from the streaming service (``streaming/match-id/{adGameId}``): its body is the stats and the moves in one, in Catalan. ``finished``: the match is
    over (the calendar says so), the header is FINAL; until then it is in progress."""
    return to_feb_document({"uuid": None, "moves": body.get("moves") or [], "stats": body}, live=not finished)
