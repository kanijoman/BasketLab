"""The public pages of ACB as data (#886, D2a of epic #872): the match centre (``live.acb.com/partidos/<local>-vs-<visitante>-<id>/<tab>``) and the page of a player (``acb.com/es/liga/jugadores/<nombre>-<id>/<tab>``).

Both are Next applications whose data travels in the ``self.__next_f.push([1, "…"])`` chunks of their HTML, as FIBA's: ``extract_flight`` joins them (the same reader as FIBA's). Only the calendar needs the
API of the site (``acb_client``); everything here is public HTML. Pure functions, no I/O.

A page can come back without its data (a version of the site with the shell only) or cut in the middle: ``check_page`` raises ``GenericPage`` or ``CutPage`` so the client asks again, and ``AcbPageError``
for a page whose format is not the one this reader knows (the site changed: it has to be seen, not asked again).
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from src.external import fiba_page

PAGE_MARKERS = {
    "jugadas": '"plays":[',               # the play by play of a game
    "estadisticas": '"statsByPeriods"',   # the box score of a game
    "temporada": '"birthDate"',           # the bio of a player (and his season)
    "zonas-de-tiro": '"seasonShots"',     # the shots of a player with their coordinates
}


class AcbPageError(ValueError):
    """The page is not the page of ACB this reader knows."""


class GenericPage(AcbPageError):
    """The page has no data (the shell of the site): ask again."""


class CutPage(AcbPageError):
    """The page has its data cut in the middle: ask again."""


def extract_flight(html: str) -> str:
    """The text of the data chunks of a Next page, joined and unescaped (``GenericPage`` when it has none)."""
    try:
        return fiba_page.extract_flight(html)
    except fiba_page.GenericPage as error:
        raise GenericPage(str(error)) from error


def check_page(kind: str, flight: str) -> None:
    """Raise ``CutPage`` when the flight of a page of ``kind`` (a key of ``PAGE_MARKERS``) does not hold the data of that kind: the response ended early, or it is the shell of the site (ask again)."""
    if PAGE_MARKERS[kind] not in flight:
        raise CutPage(f"the page has no {kind} data")


# --- the game: box score and play by play -------------------------------------------------------------------------------------------------------------------------------------------------------------------------

_DECODER = json.JSONDecoder()
_MATCH_ID = re.compile(r"/partidos/[a-z0-9\-]+-(\d+)/")
_NOT_STATS = {"player", "onCourt", "playTime", "isStarted"}


def _value_after(flight: str, marker: str, kind: str, keep: int = 0) -> Any:
    """The JSON value that follows ``marker`` in the flight, ``keep`` characters of the marker included (``CutPage`` if it is not there: the page ended early or is the shell of the site)."""
    start = flight.find(marker)
    if start < 0:
        raise CutPage(f"the page has no {kind} data")
    try:
        return _DECODER.raw_decode(flight[start + len(marker) - keep:])[0]
    except ValueError as error:
        raise CutPage(f"the {kind} data of the page is cut in the middle") from error


def match_id_of(flight: str) -> Optional[int]:
    """The id of the game a page of the match centre is about (its address says it), or ``None``."""
    found = _MATCH_ID.search(flight)
    return int(found.group(1)) if found else None


def _seconds(played: Any) -> int:
    parts = str(played or "0:00").split(":")
    try:
        numbers = [int(p) for p in parts]
    except ValueError:
        return 0
    return sum(n * 60 ** i for i, n in enumerate(reversed(numbers)))


def _stats(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in raw.items() if k not in _NOT_STATS and isinstance(v, (int, float)) and not isinstance(v, bool)}


def _format(what: str) -> AcbPageError:
    return AcbPageError(f"format: {what} is not the one this reader knows (the site changed)")


def _team_box(entry: Dict[str, Any]) -> Dict[str, Any]:
    try:
        team = entry["team"]
        periods = {s["quarter"]: s["stats"] for s in entry["statsByPeriods"]}
        total = periods[0]
        players: Dict[int, Dict[str, Any]] = {}
        for quarter, block in sorted(periods.items()):
            for line in block["players"]:
                person = line["player"]
                row = players.setdefault(person["id"], {
                    "id": person["id"], "name": person.get("nickname") or f"{person.get('firstName', '')} {person.get('lastName', '')}".strip(), "first_name": person.get("firstName"),
                    "last_name": person.get("lastName"), "number": person.get("shirtNumber"), "role": person.get("gameRole"), "started": False, "seconds": 0, "totals": {}, "periods": {}})
                if quarter == 0:
                    row.update(started=bool(line.get("isStarted")), seconds=_seconds(line.get("playTime")), totals=_stats(line))
                else:
                    row["periods"][quarter] = _stats(line)
        return {"team": {"id": team["id"], "club_id": team.get("clubId"), "name": team["fullName"], "short": team.get("shortName")}, "coach": entry.get("headCoach"),
                "assistants": list(entry.get("assistantCoaches") or []), "players": list(players.values()), "totals": _stats(total["total"]), "team_extra": _stats(total["team"]),
                "periods": {q: _stats(b["total"]) for q, b in periods.items() if q != 0}}
    except (KeyError, TypeError) as error:
        raise _format(f"the box score of a team ({error})") from error


def parse_box(flight: str) -> Dict[str, Any]:
    """The box score page (``estadisticas``): ``{finished, arena, attendance, referees, teams: [two team boxes, in the order of the page]}``; each box has the team, its coaches, its players (minutes in seconds,
    totals and the stats of each quarter) and the totals of the team and of each quarter."""
    data = _value_after(flight, '"initialStatistics":', "box score")
    try:
        entries = data["teamBoxscores"]
        if len(entries) != 2:
            raise _format("the number of teams")
        return {"finished": bool(data["matchFinished"]), "arena": data.get("arena"), "attendance": data.get("attendance"), "referees": list(data.get("referees") or []),
                "teams": [_team_box(e) for e in entries]}
    except (KeyError, TypeError) as error:
        raise _format(f"the box score ({error})") from error


def parse_plays(flight: str) -> List[Dict[str, Any]]:
    """The play by play page (``jugadas``), oldest first: one dict per play with its ``order``, ``type`` (the code of ACB, ``tag`` for the variant), clock (``period`` and ``minute``/``second``), the score after it,
    the team and the player (``None`` for what has no team: the start of a quarter, a time-out of the game)."""
    plays = _value_after(flight, '"plays":[', "play by play", keep=1)          # the translations of the page also have a ``plays``: this one is the list
    out: List[Dict[str, Any]] = []
    try:
        for p in plays:
            team = p.get("team") or {}
            out.append({"order": p["order"], "type": p["playType"], "tag": p.get("playTag"), "period": p["quarter"], "minute": p["minute"], "second": p["second"],
                        "home": bool(p["local"]) if team else None, "team_id": team.get("id"), "score_home": p.get("scoreHome"), "score_away": p.get("scoreAway"),
                        "player_id": p.get("playerLicenseId"), "player_name": p.get("playerName"), "player_number": p.get("playerNumber"), "player_stats": p.get("playerStats")})
    except (KeyError, TypeError, AttributeError) as error:
        raise _format(f"a play ({error})") from error
    return sorted(out, key=lambda p: p["order"])


def parse_game(box_flight: str, plays_flight: str) -> Dict[str, Any]:
    """A finished game from its two pages: the box score and the play by play. The home team is the one the play by play says (``local``); the pages must be about the same game."""
    first, second = match_id_of(box_flight), match_id_of(plays_flight)
    if first is None or first != second:
        raise AcbPageError(f"format: the two pages are not about the same game ({first} and {second})")
    box, plays = parse_box(box_flight), parse_plays(plays_flight)
    home_id = next((p["team_id"] for p in plays if p["home"] is True), None)
    teams = {t["team"]["id"]: t for t in box["teams"]}
    if home_id not in teams:
        raise _format("the team that plays at home")
    away = next(t for tid, t in teams.items() if tid != home_id)
    return {"match_id": first, "finished": box["finished"], "arena": box["arena"], "attendance": box["attendance"], "referees": box["referees"], "home": teams[home_id], "away": away, "plays": plays}
