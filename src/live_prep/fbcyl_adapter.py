"""A FBCYL game in the shape of a FEB document (issue #445, epic #435).

``{uuid, moves[], stats}`` -> ``{_id, HEADER, BOXSCORE (roster), PLAYBYPLAY.LINES, SHOTCHART}``: what the live engine, the package builder, the
rule evaluator and the demo generator read, so they work on FBCYL without a second code path. Differences of the feed that this resolves:

* ``idTeam`` of a move is ``teamIdIntern`` (per game); the document uses ``teamIdExtern`` (stable between games and seasons), home first.
* ``min``/``sec`` of a move is the time REMAINING in the period, the same as FEB's ``time``; the moves have no number, their position is the order.
* The text of a move is matched without accents (the stored data has mojibake). "Falta recibida" is the same foul seen from the victim and has
  no FEB counterpart: it is dropped. Offensive and defensive rebounds are one ``rebound`` line (the engine decides which it is, as in FEB).
* No shot chart (``SHOTCHART.SHOTS`` is empty: the zone rules stay quiet) and no roster mark of "formación".
* The play-by-play is annotated by the clubs and has errors the feed does not fix: ``HEADER.source = "fbcyl"`` lets consumers label it experimental.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

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


def _header(game: Dict[str, Any], teams: List[Dict[str, Any]]) -> Dict[str, Any]:
    stats = game.get("stats") or {}
    code = str(stats.get("idMatchExtern") or game.get("uuid") or "")
    last = max((int(m.get("period") or 1) for m in game.get("moves") or []), default=1)
    return {
        "TEAM": [{"id": str(t["teamIdExtern"]), "name": str(t.get("name") or t["teamIdExtern"]).strip(), "pts": str((t.get("data") or {}).get("score") or 0)}
                 for t in teams],
        "status": "3", "statusText": "FINISHED", "quarter": str(last), "time": "FINAL", "starttime": starttime(stats),
        "game_code": code, "uuid": game.get("uuid"), "competition": game.get("_competition"), "round": None, "source": SOURCE,
    }


def _boxscore(teams: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"TEAM": [{
        "id": str(t["teamIdExtern"]), "name": str(t.get("name") or "").strip(),
        "PLAYER": [{"id": str(p["actorId"]), "no": str(p.get("dorsal") or ""), "name": str(p.get("name") or "").strip(), "captain": bool(p.get("captain"))}
                   for p in t.get("players") or [] if p.get("actorId")],
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
        text = str(move.get("move") or "")
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


def to_feb_document(game: Dict[str, Any]) -> Dict[str, Any]:
    """The FEB-shaped document of a FBCYL game; the given one is not modified."""
    stats = game.get("stats") or {}
    teams = _teams(stats)
    header = _header(game, teams)
    return {
        "_id": header["game_code"], "_season": game.get("_season"), "_league": game.get("_league"), "HEADER": header, "BOXSCORE": _boxscore(teams),
        "PLAYBYPLAY": {"LINES": _lines(game, teams)}, "SHOTCHART": {"quarters": None, "duration": None, "TEAM": [], "SHOTS": []},
    }
