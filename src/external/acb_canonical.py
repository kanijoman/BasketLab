"""A game of ACB as the canonical document of an external source (#886, D2e of epic #872): the result of ``acb_page.parse_game`` as the FEB document, with ``_league: acb`` and every id prefixed (``acb:105383``).

It is written as the engine and the pipelines read the FEB document (the same way ``fiba_canonical`` does for FIBA, whose line writer it reuses: the plays of ACB are turned into the same events), so that
nothing forks: ``HEADER`` (the game, the kick-off in local time, the two teams with their points of each quarter), ``BOXSCORE.TEAM[]`` (the OFFICIAL box: every player's statistics with the minutes in seconds, the
TOTAL of the players and, apart, what the team itself did) and ``PLAYBYPLAY.LINES``. The competition, the round and the kick-off are not on the pages of the game: they come from the calendar (``match``) and the
catalogue (``entry``).

**The plays of ACB are numeric codes with no table.** The ones below are the ones the real games PROVE (a made two moves the score by 2 and the ``twoPointers`` of its player, a substitution out is the first one of
every starter...); ``KNOWN_CODES`` lists them and ``UNKNOWN_CODES`` the ones seen and not understood (kept as ``other`` lines, so nothing of the page is lost, and never counted as a statistic). A code in neither is
new: the converter keeps it as ``other`` too, and ``reconcile_game`` (play by play against the official box) is what says whether the game can be trusted. Not in this version: the shot chart (the shots with
coordinates are on the page of each player, a block of its own) nor the bio of the players.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from src.external.fiba_canonical import Lines
from src.market.canonical import source_id

SOURCE = "acb"
_MADRID = ZoneInfo("Europe/Madrid")
_BOX = {"points": "pts", "freeThrowsMade": "p1m", "freeThrowsAttempted": "p1a", "twoPointersMade": "p2m", "twoPointersAttempted": "p2a", "threePointersMade": "p3m", "threePointersAttempted": "p3a",
        "assists": "assist", "blocks": "bs", "steals": "st", "turnovers": "to", "offRebounds": "ro", "defRebounds": "rd", "totalRebounds": "rt", "personalFouls": "pf", "foulsDrawn": "rf", "rating": "val"}

# code -> (kind, made, text the line writer reads). Each one is proved by the real games of tests/fixtures/acb (see tests/test_external_acb_canonical.py).
_SHOTS = {92: ("FT", True, ""), 96: ("FT", False, ""), 93: ("P2", True, ""), 97: ("P2", False, ""), 100: ("P2", True, "Dunk"), 533: ("P2", False, "Dunk Missed"), 94: ("P3", True, ""), 98: ("P3", False, "")}
_REBOUNDS = {101: "Offensive Rebound", 104: "Defensive Rebound"}                          # with no player they are the team's own
_ACTIONS = {107: "ASS", 108: "ASS", 119: "ASS", 103: "ST", 106: "TO", 102: "BS"}          # a turnover with no player is the team's
_FOULS = {109, 159, 160, 161, 162}                                                         # the ``personalFouls`` of the player moves with each one (162 is in a game of 2019/20)
_FOUL_DRAWN = 110
_SUBSTITUTIONS = {115: "OUT", 112: "IN"}                                                   # the first one of every starter is 115: he leaves
_BLOCK_RECEIVED = 105                                                                      # the shooter of a miss that is blocked: after his miss and before the block (102) of the other team, in every game; it changes no statistic
# lines that change no statistic and that FEB has no type for: they stay ``other`` lines with a Spanish text. Each one is proved by its place in the real games: 599 names exactly the ten starters of the box at
# 10:00 of the first quarter, 123 is the last play of the game right after the end of the last quarter, 178 and 179 are the opening jump ball (the team of 178 takes the first shot in both games)
_INFO = {_BLOCK_RECEIVED: "TAPÓN RECIBIDO", 599: "QUINTETO INICIAL", 123: "FIN DEL PARTIDO", 178: "SALTO GANADO", 179: "SALTO PERDIDO"}
_STRUCTURE = {113: "TIMO", 121: "STARTP", 116: "ENDP"}                                      # a time-out (7 in the game, with a team and no player); the start (10:00) and the end (0:00) of each quarter
KNOWN_CODES = frozenset({*_SHOTS, *_REBOUNDS, *_ACTIONS, *_FOULS, _FOUL_DRAWN, *_SUBSTITUTIONS, *_STRUCTURE, *_INFO})
# seen in the real games and not understood: kept as ``other`` lines. 416, 417, 748, 749, 406 and 411 gather around fouls and substitutions with no team or with the team that was fouled (they could be what the
# foul brings: free throws, the bonus, the throw-in) and nothing proves it; 118, 405 and 541 are only in the game of 2019/20
UNKNOWN_CODES = frozenset({118, 405, 406, 411, 416, 417, 541, 748, 749})


def _period(number: int) -> str:
    return f"Q{number}" if number <= 4 else f"OT{number - 4}"


def _starttime(iso: Optional[str]) -> str:
    """``2026-09-27T17:00:00Z`` -> ``27-09-2026 - 19:00``: the local time of Madrid, as FEB writes it."""
    if not iso:
        return ""
    moment = datetime.strptime(iso.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z").astimezone(_MADRID)
    return moment.strftime("%d-%m-%Y - %H:%M")


def _player_box(player: Dict[str, Any]) -> Dict[str, Any]:
    stats = player["totals"]
    box = {feb: str(stats.get(acb, 0)) for acb, feb in _BOX.items()}
    box["fgm"] = str(stats.get("twoPointersMade", 0) + stats.get("threePointersMade", 0))
    box["fga"] = str(stats.get("twoPointersAttempted", 0) + stats.get("threePointersAttempted", 0))
    return {**box, "id": source_id(SOURCE, player["id"]), "name": player["name"], "no": player["number"], "min": str(player["seconds"]), "sta": "*" if player["started"] else None,
            "birth": None, "height": None, "nationality": None, "club": None}


def _team_box(team: Dict[str, Any], won: bool) -> Dict[str, Any]:
    totals, own = team["totals"], team["team_extra"]
    total = {feb: str(totals.get(acb, 0)) for acb, feb in _BOX.items()}
    total["fgm"] = str(totals.get("twoPointersMade", 0) + totals.get("threePointersMade", 0))
    total["fga"] = str(totals.get("twoPointersAttempted", 0) + totals.get("threePointersAttempted", 0))
    # the total of ACB already adds what the team itself did (its rebounds and turnovers): the FEB convention keeps the TOTAL to its players and the team's own apart, so that TOTAL + TEAMACTIONS is ACB's figure
    for acb, feb in (("offRebounds", "ro"), ("defRebounds", "rd"), ("totalRebounds", "rt")):
        total[feb] = str(totals.get(acb, 0) - own.get(acb, 0))
    actions = {"ro": str(own.get("offRebounds", 0)), "rd": str(own.get("defRebounds", 0)), "rt": str(own.get("totalRebounds", 0)), "to": str(own.get("turnovers", 0)), "pf": str(own.get("personalFouls", 0))}
    return {"id": source_id(SOURCE, team["team"]["id"]), "name": team["team"]["name"], "teamCode": team["team"].get("short"), "win_lose": "W" if won else "L", "TOTAL": total, "TEAMACTIONS": actions,
            "PLAYER": [_player_box(p) for p in team["players"]]}


def _events(game: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The plays of the page as the events ``fiba_canonical.Lines`` writes. A play with no score keeps the last one."""
    events: List[Dict[str, Any]] = []
    score = (0, 0)
    for play in game["plays"]:
        if play["score_home"] is not None and play["score_away"] is not None:
            score = (play["score_home"], play["score_away"])
        code, player = play["type"], play["player_id"]
        base = {"code": "OTHER", "team": play["team_id"], "player": player, "player2": None, "made": False, "text": f"ACB código {code}", "in": None, "period": _period(play["period"]),
                "clock": f"{play['minute']}:{play['second']:02d}", "score_a": score[0], "score_b": score[1]}
        if code in _SHOTS:
            kind, made, text = _SHOTS[code]
            base.update(code=kind, made=made, text=text)
        elif code in _REBOUNDS:
            base.update(code="REB" if player else "TREB", text=_REBOUNDS[code])
        elif code in _ACTIONS:
            kind = _ACTIONS[code]
            base.update(code="TTO" if kind == "TO" and not player else kind, text="")
        elif code in _FOULS:
            base.update(code="FOUL", text="Foul")
        elif code == _FOUL_DRAWN:
            base.update(code="RFOUL", text="Foul Received")
        elif code in _SUBSTITUTIONS:
            base.update(code="SUBST", **{"in": _SUBSTITUTIONS[code]})
        elif code in _STRUCTURE:
            base.update(code=_STRUCTURE[code], text="")
        elif code in _INFO:
            base["text"] = _INFO[code]
        events.append(base)
    return events


def _lines_game(game: Dict[str, Any]) -> Dict[str, Any]:
    """What ``fiba_canonical.Lines`` asks of a game: its teams (``org_id`` and name) and their players (``person_id`` and name)."""
    return {"teams": [{"org_id": t["team"]["id"], "name": t["team"]["name"], "players": [{"person_id": p["id"], "name": p["name"]} for p in t["players"]]} for t in (game["home"], game["away"])]}


def _round(match: Dict[str, Any]) -> str:
    number = match.get("roundNumber")
    return f"Jornada {number}" if match.get("roundType") == "LR" and number else " ".join(str(x) for x in (match.get("roundType"), number) if x)


def to_canonical(game: Dict[str, Any], match: Dict[str, Any], entry: Dict[str, Any]) -> Dict[str, Any]:
    """The canonical document of a finished game as ``acb_page.parse_game`` read it, with its calendar line (``match``: the id, the kick-off and the round) and its catalogue entry (the competition and the season).
    ``ValueError`` if the game is not finished or the calendar line is of another game. The game read is not changed."""
    if not game["finished"]:
        raise ValueError("the game is not finished: only a finished game is converted")
    if match.get("id") != game["match_id"]:
        raise ValueError(f"the calendar line is not of the same game ({match.get('id')} and {game['match_id']})")
    home, away = game["home"], game["away"]
    points = (home["totals"]["points"], away["totals"]["points"])
    quarters = [{"n": str(q), "scoreA": str(home["periods"][q]["points"]), "scoreB": str(away["periods"][q]["points"])} for q in sorted(home["periods"])]
    header = {"CompID": str(entry["acb"]["competition_id"]), "competition": entry["competition"], "round": _round(match), "quarter": len(quarters), "time": "FINAL", "logo": None, "duration": None,
              "starttime": _starttime(match.get("startDateTime")), "place": game.get("arena"), "field": game.get("arena"), "status": "3", "statusText": "FINISHED",
              "TEAM": [{"pts": str(pts), "fouls": None, "id": source_id(SOURCE, t["team"]["id"]), "name": t["team"]["name"], "logo": None, "teamCode": t["team"].get("short"), "clubCode": None}
                       for t, pts in zip((home, away), points)],
              "QUARTERS": {"QUARTER": quarters}, "game_code": str(game["match_id"])}
    lines = Lines(_lines_game(game), SOURCE).build(_events(game))
    return {"_id": source_id(SOURCE, game["match_id"]), "_league": SOURCE, "_season": str(entry["season_value"]), "HEADER": header,
            "PLAYBYPLAY": {"duration": None, "hasExtension": len(quarters) > 4, "LINES": lines},
            "BOXSCORE": {"duration": None, "TEAM": [_team_box(home, points[0] > points[1]), _team_box(away, points[1] > points[0])]},
            "SHOTCHART": {"SHOTS": [], "TEAM": []}}
