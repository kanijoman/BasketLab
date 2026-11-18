"""A FIBA game as the canonical document of an external source (#887, D3a of epic #872): the result of ``fiba_page.parse_game`` as the FEB document, with ``_league: fiba`` and every id prefixed (``fiba:59``).

What the document has, written as the engine and the pipelines read the FEB one (the same way ``live_core.fbcyl_adapter`` does for FBCYL), so that nothing forks:

* ``HEADER``: the game, the competition, the kick-off (``dd-mm-yyyy - HH:MM``, local), the two teams with their score and the points of each period (``QUARTERS``, an overtime is a fifth one);
* ``BOXSCORE.TEAM[]``: the OFFICIAL box of the page (every player's statistics with the minutes in seconds, the team totals and, apart, what the team itself did: team rebounds and turnovers);
* ``PLAYBYPLAY.LINES``: every event as a line with ``action``, a Spanish ``text`` with the keywords the engine matches (``TIRO DE 2 ANOTADO``, ``MATE``, ``Faltas: n.``), the remaining clock, the period and the ids.
  A «foul drawn» is not a line of its own: it goes in ``logParam4`` of the foul it belongs to, as FEB writes it. A code that is not known is kept as an ``other`` line, so nothing of the page is lost.

Not in this version: the shot chart (FIBA gives the court coordinates of each shot; their mapping to the zones of the engine is a block of its own). Pure functions, no I/O, nothing of the page is changed.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.market.canonical import source_id

SOURCE = "fiba"
_GENDERS = {"Men": "M", "Women": "F"}
# the keys of the official box of the page and the FEB keys they become (statistic by statistic)
_BOX = {"FTM": "p1m", "FTA": "p1a", "FG2M": "p2m", "FG2A": "p2a", "FG3M": "p3m", "FG3A": "p3a", "FGM": "fgm", "FGA": "fga", "AS": "assist", "BS": "bs", "ST": "st", "TO": "to",
        "OR": "ro", "DR": "rd", "REB": "rt", "PF": "pf", "FD": "rf", "PTS": "pts", "EFF": "val"}


def gender_of(competition: Dict[str, Any]) -> str:
    """``M`` or ``F`` from what the page says of its competition; anything else is refused, never guessed."""
    gender = _GENDERS.get(competition.get("gender"))
    if gender is None:
        raise ValueError(f"the competition does not say a gender FIBA's way (Men or Women): {competition.get('gender')!r}")
    return gender


def _period_number(period: str) -> int:
    """``Q1``..``Q4`` are periods 1 to 4 and ``OT1``, ``OT2``… the overtimes after them."""
    match = re.fullmatch(r"(Q|OT)(\d+)", period)
    if not match:
        raise ValueError(f"unknown period {period!r}")
    return int(match.group(2)) + (4 if match.group(1) == "OT" else 0)


def _clock(text: Optional[str]) -> str:
    minutes, _, seconds = (text or "0:00").partition(":")
    return f"{int(minutes):02d}:{int(seconds or 0):02d}"


def _seconds(played: Optional[str]) -> str:
    minutes, _, seconds = (played or "0:0").partition(":")
    return str(int(minutes) * 60 + int(seconds or 0))


def _starttime(iso: Optional[str]) -> str:
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S").strftime("%d-%m-%Y - %H:%M") if iso else ""


def _player_box(person: Dict[str, Any]) -> Dict[str, Any]:
    stats = person["stats"]
    box = {feb: str(stats.get(fiba, 0)) for fiba, feb in _BOX.items()}
    return {**box, "id": source_id(SOURCE, person["person_id"]), "name": person["name"], "no": person["number"], "min": _seconds(stats.get("TP")), "sta": "*" if stats.get("Starter") else None,
            "birth": person.get("birth"), "height": str(person["height_cm"]) if person.get("height_cm") else None, "nationality": person.get("nationality"), "club": person.get("club")}


def _team_box(team: Dict[str, Any], won: bool) -> Dict[str, Any]:
    totals = team["totals"]
    total = {feb: str(totals.get(fiba, 0)) for fiba, feb in _BOX.items()}
    # FIBA's totals of a team already add what the team itself did (its rebounds): the FEB convention keeps the TOTAL to its players and the team's own apart, so that TOTAL + TEAMACTIONS is FIBA's figure
    for fiba, own, feb in (("OR", "T_OR", "ro"), ("DR", "T_DR", "rd"), ("REB", "T_REB", "rt")):
        total[feb] = str(int(totals.get(fiba, 0)) - int(totals.get(own, 0)))
    actions = {"ro": str(totals.get("T_OR", 0)), "rd": str(totals.get("T_DR", 0)), "rt": str(totals.get("T_REB", 0)), "to": str(totals.get("T_TO", 0)), "pf": str(totals.get("T_PF", 0))}
    return {"id": source_id(SOURCE, team["org_id"]), "name": team["name"], "teamCode": team["code"], "win_lose": "W" if won else "L", "TOTAL": total, "TEAMACTIONS": actions,
            "PLAYER": [_player_box(p) for p in team["players"]]}


def _foul_text(text: str, name: str, count: int) -> str:
    lower = (text or "").lower()
    if "technical" in lower:
        return f"{name}: FALTA TÉCNICA"
    if "unsportsmanlike" in lower:
        return f"{name}: FALTA ANTIDEPORTIVA"
    return f"{name}: FALTA PERSONAL. Faltas: {count}."


class _Lines:
    """The play-by-play of the page written as the lines of a FEB document."""

    def __init__(self, game: Dict[str, Any]) -> None:
        self.teams = {t["org_id"]: t["name"] for t in game["teams"]}
        self.players = {p["person_id"]: p["name"] for t in game["teams"] for p in t["players"]}
        self.fouls: Counter = Counter()
        self.lines: List[Dict[str, Any]] = []

    def build(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        drawn = []
        for event in events:
            if event["code"] == "RFOUL":
                drawn.append(event)
            elif event["code"] == "SUBST" and event["player2"] is not None:
                # one event that names who comes in (``player``) and who goes out (``player2``): FEB writes two lines, the one who leaves first
                self.lines.append(self._line({**event, "player": event["player2"], "in": "OUT"}))
                self.lines.append(self._line(event))
            else:
                self.lines.append(self._line(event))
        for event in drawn:
            self._attach(event)
        for number, line in enumerate(self.lines, start=1):
            line["num"] = str(number)
        return self.lines

    def _who(self, event: Dict[str, Any]) -> str:
        team, player = self.teams.get(event["team"], ""), self.players.get(event["player"], "")
        return f"({team}) {player}" if player else f"({team})" if team else ""

    def _line(self, event: Dict[str, Any]) -> Dict[str, Any]:
        code, who = event["code"], self._who(event)
        action, text = "other", event["text"] or ""
        if code in ("P2", "P3", "FT"):
            made, value = "ANOTADO" if event["made"] else "FALLADO", {"P2": 2, "P3": 3, "FT": 1}[code]
            dunk = code == "P2" and "dunk" in text.lower()
            action, text = ("fthrow" if code == "FT" else "shoot"), f"{who}: " + (f"MATE {made}" if dunk else f"TIRO DE {value} {made}")
        elif code in ("REB", "TREB"):
            lower = text.lower()                                               # the senior game writes ``Offensive rebound``, the U18 ones ``offensive rebound``
            kind = " OFENSIVO" if "offensive" in lower else " DEFENSIVO" if "defensive" in lower else ""        # a text that says neither is left without a label: the tracker decides
            action, text = "rebound", f"{who}: REBOTE{kind}" if code == "REB" else f"{who} REBOTE DE EQUIPO{kind}"
        elif code in ("ASS", "ST", "TO", "TTO", "BS"):
            action = {"ASS": "assist", "ST": "recovery", "TO": "lose", "TTO": "lose", "BS": "blockshot"}[code]
            word = {"ASS": "ASISTENCIA", "ST": "RECUPERACIÓN", "TO": "PÉRDIDA", "TTO": "PÉRDIDA DE EQUIPO", "BS": "TAPÓN"}[code]
            text = f"{who}: {word}" if event["player"] else f"{who} {word}"
        elif code == "FOUL":
            self.fouls[event["player"]] += 1
            action, text = "foul", _foul_text(text, who, self.fouls[event["player"]])
        elif code == "SUBST":
            action, text = "subst", f"{who}: " + ("ENTRA A PISTA" if event["in"] == "IN" else "SALE DE PISTA")
        elif code == "TIMO":
            action, text = "timeout", f"{who} TIEMPO MUERTO"
        elif code in ("STARTP", "ENDP"):
            number = _period_number(event["period"])
            overtime = number > 4
            action = "period"
            text = ("Comienzo" if code == "STARTP" else "Fin") + (f" de la Prórroga {number - 4}" if overtime else f" del Cuarto {number}")
        return {"num": "", "quarter": str(_period_number(event["period"])), "time": _clock(event["clock"]), "idTeam": source_id(SOURCE, event["team"]) if event["team"] is not None else None,
                "idPlayer": source_id(SOURCE, event["player"]) if event["player"] is not None else None, "idLicense": source_id(SOURCE, event["player"]) if event["player"] is not None else None,
                "action": action, "text": text, "deleted": None, "scoreA": str(event["score_a"]), "scoreB": str(event["score_b"])}

    def _attach(self, event: Dict[str, Any]) -> None:
        """A «foul drawn» goes on the foul of the other team with the same clock; with none, it stays as a line that the engine ignores."""
        victim = source_id(SOURCE, event["player"])
        clock, period = _clock(event["clock"]), str(_period_number(event["period"]))
        for line in self.lines:
            if line["action"] == "foul" and (line["quarter"], line["time"]) == (period, clock) and not line.get("logParam4") and line["idTeam"] != source_id(SOURCE, event["team"]):
                line["logParam4"] = victim
                return
        self.lines.append({**self._line({**event, "code": "RFOUL"}), "action": "other", "text": f"{self._who(event)}: FALTA RECIBIDA"})


def to_canonical(game: Dict[str, Any]) -> Dict[str, Any]:
    """The canonical document of a game as ``fiba_page.parse_game`` read it (``ValueError`` if the competition does not say a gender: it is not guessed). The game read is not changed."""
    gender_of(game["competition"])
    home, away = game["teams"]
    competition = game["competition"]
    quarters = [{"n": str(i), "scoreA": str(a["score"]), "scoreB": str(b["score"])} for i, (a, b) in enumerate(zip(home["periods"], away["periods"]), start=1)]
    header = {"CompID": str(competition["id"]), "competition": competition["name"], "round": game["round"], "quarter": len(game["periods"]), "time": "FINAL", "logo": None, "duration": None,
              "starttime": _starttime(game["start"]), "place": game["venue"], "field": game["venue"], "status": "3", "statusText": "FINISHED",
              "TEAM": [{"pts": str(t["score"]), "fouls": None, "id": source_id(SOURCE, t["org_id"]), "name": t["name"], "logo": None, "teamCode": t["code"], "clubCode": None} for t in (home, away)],
              "QUARTERS": {"QUARTER": quarters}, "game_code": str(game["game_id"])}
    return {"_id": source_id(SOURCE, game["game_id"]), "_league": SOURCE, "_season": str(competition["season"]), "HEADER": header,
            "PLAYBYPLAY": {"duration": None, "hasExtension": len(game["periods"]) > 4, "LINES": _Lines(game).build(game["events"])},
            "BOXSCORE": {"duration": None, "TEAM": [_team_box(home, home["score"] > away["score"]), _team_box(away, away["score"] > home["score"])]},
            "SHOTCHART": {"SHOTS": [], "TEAM": []}}
