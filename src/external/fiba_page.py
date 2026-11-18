"""The public page of a FIBA game (``/events/<event>/games/<id>-<teams>``) as data (#887, D3a of epic #872).

The page is a Next application whose data travels in the ``self.__next_f.push([1, "…"])`` chunks of its HTML: ``extract_flight`` joins them and ``parse_game`` reads from that text what the page shows of a finished
game: the game (teams, venue, kick-off, competition), the OFFICIAL box (every player's statistics and every team's totals, minutes and starters included), the rosters and the full play-by-play grouped by period. No
key and no API: it is the public HTML of the match centre. Pure functions, no I/O: ``fiba_client`` (D3b) fetches the page and retries; ``fiba_canonical`` turns the result into the canonical document.

A page can come back generic (a version of the site with no game data, seen 2 times in ~10 requests by the spike #915): ``parse_game`` raises ``GenericPage`` so the client asks again, and ``FibaPageError`` for a
page that is not a FIBA game at all or whose format changed.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

_CHUNK = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', re.S)
_DECODER = json.JSONDecoder()


class FibaPageError(ValueError):
    """The page is not a FIBA game page or its format is not the one this reader knows."""


class GenericPage(FibaPageError):
    """The page is a version of the site with no data of the game: ask again."""


class CutPage(FibaPageError):
    """The page has the data of the game but cut in the middle (a response that ended early): ask again."""


def extract_flight(html: str) -> str:
    """The text of the data chunks of a Next page, joined and unescaped."""
    chunks = _CHUNK.findall(html or "")
    if not chunks:
        raise GenericPage("the page has no Next data chunks")                  # an error page, a maintenance page: it can be asked again
    return "".join(json.loads(f'"{chunk}"') for chunk in chunks if chunk)


# What the flight must hold for a page to be a game, in the order they are read: the marker that opens each block and the way to decode what follows it.
_MARKERS = {"game": '"game":{"gameId":', "pbp": '"playByPlay":{"items":', "details": '"gameDetails":{', "rosterA": '"playersTeamA":[', "rosterB": '"playersTeamB":['}
_UNDEFINED = "$undefined"


def _block(flight: str, name: str) -> Any:
    """The JSON value of a block of the flight, or ``None`` when the page does not have it. A block that is there and cannot be decoded (a page cut in the middle) is a format error."""
    marker = _MARKERS[name]
    at = flight.find(marker)
    if at < 0:
        return None
    start = at + marker.index(":") + 1                       # the value begins right after the colon that follows the name of the block
    try:
        return _DECODER.raw_decode(flight[start:])[0]
    except ValueError as error:
        raise CutPage(f"the {name} data of the page is cut or not valid JSON") from error


def _order(raw: Dict[str, Any]) -> int:
    """The position of an event in its period (the page writes it as a number or as a text)."""
    try:
        return int(str(raw.get("order")))
    except ValueError:
        return 0


def _clean(value: Any) -> Any:
    """What the page writes for «nothing» (``"$undefined"``) as ``None``."""
    return None if value == _UNDEFINED else value


def _event(period: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    return {"period": period, "id": str(raw.get("Id")), "order": _order(raw), "clock": raw.get("Time"), "time_ms": raw.get("GT"), "score_a": raw.get("SA"), "score_b": raw.get("SB"),
            "act": raw.get("act"), "code": raw.get("ac"), "text": raw.get("txt"), "team": _clean(raw.get("oId")), "player": _clean(raw.get("pId")), "player2": _clean(raw.get("p2Id")),
            "made": raw.get("made"), "points": raw.get("pts"), "x": raw.get("x"), "y": raw.get("y"), "in": raw.get("in")}


def _bios(flight: str, side: str) -> Dict[int, Dict[str, Any]]:
    """The bio of the players of a team (``rosterA``/``rosterB`` of the page: date of birth, height, nationality, club) by person. Optional: a page without the block, or one that cannot be read, gives none and the
    game is read all the same (the bio is extra, never a reason to lose a game)."""
    marker = f'"roster{side}":{{"teamId"'
    at = flight.find(marker)
    if at < 0:
        return {}
    try:
        block = _DECODER.raw_decode(flight[at + len(f'"roster{side}":'):])[0]
        return {int(p["personId"]): p for p in block.get("players") or []}
    except (ValueError, KeyError, TypeError, AttributeError):
        return {}


def _bio_of(raw: Dict[str, Any]) -> Dict[str, Any]:
    height = raw.get("heightInCm")
    return {"birth": raw.get("dateOfBirth") or None, "height_cm": int(height) if isinstance(height, (int, float)) and height > 0 else None, "nationality": raw.get("nationality") or None, "club": raw.get("clubName") or None}


def _team(side: str, meta: Dict[str, Any], boxes: Dict[str, Dict[str, Any]], roster: List[Dict[str, Any]], bios: Optional[Dict[int, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """A team: who it is, its score by period, its official totals and its players with their official box."""
    org = meta["organisationId"]
    box = boxes.get(f"T_{org}")
    if box is None:
        raise FibaPageError(f"the page has no official box for team {org}")
    people = {r["personId"]: r for r in roster}
    players = []
    for child in box.get("Children") or []:
        person_id = int(str(child["Id"]).split("_", 1)[1])
        known = people.get(person_id, {})
        name = " ".join(part for part in (known.get("firstName"), known.get("lastName")) if part) or f"Player {person_id}"
        players.append({"person_id": person_id, "name": name, "number": known.get("uniformNumber"), "position": known.get("position"), "captain": bool(known.get("isCaptain")), **_bio_of((bios or {}).get(person_id, {})), "stats": child.get("Stats") or {}})
    return {"side": side, "org_id": org, "team_id": meta.get("teamId"), "code": meta.get("code"), "name": meta.get("officialName"), "score": box["Score"],
            "periods": [{"period": p["Id"], "score": p["Score"]} for p in box.get("Periods") or []], "totals": {k: v for k, v in (box.get("Stats") or {}).items() if k != "Leaders"}, "players": players}


def parse_game(flight: str) -> Dict[str, Any]:
    """What the page of a finished game says: the game, the two teams with their official box and the play-by-play by period. ``GenericPage`` when the page has no game data; ``FibaPageError`` when it has it
    cut or in a shape this reader does not know."""
    blocks = {name: _block(flight or "", name) for name in _MARKERS}
    if any(value is None for value in blocks.values()):
        raise GenericPage("the page has no data of a game: " + ", ".join(name for name, value in blocks.items() if value is None) + " missing")
    game, pbp, details = blocks["game"], blocks["pbp"], blocks["details"]
    try:
        boxes = {box["Id"]: box for box in details["c"]}
        teams = [_team("A", game["teamA"], boxes, blocks["rosterA"], _bios(flight, "A")), _team("B", game["teamB"], boxes, blocks["rosterB"], _bios(flight, "B"))]
        periods = list(pbp["items"])
        events = [_event(period, raw) for period in periods for raw in sorted(pbp["items"][period]["items"], key=_order)]
        competition = game["competition"]
    except (KeyError, TypeError, ValueError) as error:
        raise FibaPageError(f"the data of the page has a shape this reader does not know: {error!r}") from error
    return {"game_id": game["gameId"], "name": game.get("gameName"), "number": game.get("gameNumber"), "status": game.get("statusCode"), "start": game.get("gameDateTime"), "start_utc": game.get("gameDateTimeUTC"),
            "venue": game.get("venueName"), "city": game.get("hostCity"), "country": game.get("hostCountry"), "round": (game.get("round") or {}).get("roundName"), "round_code": (game.get("round") or {}).get("roundCode"),
            "competition": {"id": competition.get("competitionId"), "code": competition.get("competitionCode"), "name": competition.get("officialName"), "season": competition.get("season"),
                            "age_category": competition.get("ageCategory"), "gender": competition.get("gender")},
            "teams": teams, "periods": periods, "events": events}


_EVENT_MARKER = '"games":[{"gameId"'


def _finished(game: Dict[str, Any]) -> bool:
    """A game is finished when the page says it is valid and its last period is over; one to play is ``INIT`` and has no period status. Only a finished game has a play-by-play to read."""
    return game.get("statusCode") == "VALID" and game.get("currentPeriodStatus") == "E" and not game.get("isLive")


def parse_event_games(flight: str) -> List[Dict[str, Any]]:
    """The games an event page lists, in the order they are played (by kick-off, ties by id): who plays, when, the score of the finished ones and the ``slug`` of the page of each (``<id>-<code>-<code>``).
    A game that is only a ``gameId`` (the shell the site keeps for an event that has not been played) has no teams, no ``slug`` and is not finished. ``GenericPage`` when the page lists no games (the generic
    version, or a page that is not an event's); ``FibaPageError`` when the list is cut."""
    flight = flight or ""
    if _MARKERS["game"] in flight:
        raise FibaPageError("this is the page of a game, not of an event")                  # a game's page also mentions other games
    at = flight.find(_EVENT_MARKER)
    if at < 0:
        raise GenericPage("the page lists no games")
    try:
        raw = _DECODER.raw_decode(flight[at + len('"games":'):])[0]
    except ValueError as error:
        raise CutPage("the list of games of the page is cut or not valid JSON") from error
    games = []
    try:
        for item in raw:
            home, away = item.get("teamA"), item.get("teamB")
            if not home or not away:                                           # the shell of an event: a game that is only a ``gameId`` (no teams, no date, no status), with no page to ask for
                games.append({"game_id": item["gameId"], "slug": None, "number": None, "start": None, "start_utc": None, "finished": False, "postponed": False, "teams": [], "score": None})
                continue
            finished = _finished(item)
            games.append({"game_id": item["gameId"], "slug": f"{item['gameId']}-{home['code']}-{away['code']}", "number": item.get("gameNumber"), "start": item.get("gameDateTime"),
                          "start_utc": item.get("gameDateTimeUTC"), "finished": finished, "postponed": bool(item.get("isPostponed")),
                          "teams": [{"code": t["code"], "name": t.get("officialName"), "org_id": t.get("organisationId")} for t in (home, away)],
                          "score": (item["teamAScore"], item["teamBScore"]) if finished else None})
    except (KeyError, TypeError) as error:
        raise FibaPageError(f"the games of the page have a shape this reader does not know: {error!r}") from error
    return sorted(games, key=lambda g: (g["start_utc"] or "", g["game_id"]))
