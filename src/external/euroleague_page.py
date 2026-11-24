"""What the Euroleague reader takes from the answers of its public API (#1038, D6a of epic #872).

A game is three answers from two servers, none with a key:

* the calendar line and the BOX of ``api-live.euroleague.net/v2`` (``games`` and ``games/<code>/stats``): the official box of each player with his bio (birth, height, country, position) and the total of
  the team, which already adds what the team itself did (its rebounds), and that own part apart;
* the PLAY BY PLAY and the SHOTS of ``live.euroleague.net/api`` (``PlayByPlay`` and ``Points``): the shots carry their coordinates (centimetres from the hoop: ``x`` across the court, ``y`` along it) and
  the number of the play they are, which is how they are put on it.

The same shapes serve the EuroLeague (``E``), the EuroCup (``U``) and the U18 Next Generation Tournament (``J``, each tournament a season of its own). The player code is stable across seasons and competitions
(``009849``); the play by play and the shots write it with a ``P`` and padding (``P009849   ``), which is taken off here.

An answer whose shape is not the one expected is an ``EuroleaguePageError``, never read as an empty season or game: a quiet empty list would hide that the API changed.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

QUARTERS = ("FirstQuarter", "SecondQuarter", "ThirdQuarter", "ForthQuarter")           # the API spells it so
FIELD_GOALS = frozenset({"2FGM", "2FGA", "3FGM", "3FGA"})


class EuroleaguePageError(Exception):
    """The answer is not in a format the reader knows (asking again would not change it, so it is not retried)."""


def _items(data: Any, key: str = "data") -> List[Dict[str, Any]]:
    items = data.get(key) if isinstance(data, dict) else None
    if not isinstance(items, list) or not items or not all(isinstance(i, dict) for i in items):
        raise EuroleaguePageError(f"the answer has no '{key}' list")
    return items


def _side(line: Dict[str, Any], key: str) -> Dict[str, Any]:
    side = line.get(key)
    club = side.get("club") if isinstance(side, dict) else None
    if not isinstance(club, dict) or not club.get("code") or not club.get("name"):
        raise EuroleaguePageError(f"a game of the calendar lacks its '{key}' club: {sorted(line)}")
    partials = side.get("partials") or {}
    periods = [partials[f"partials{n}"] for n in range(1, 5) if f"partials{n}" in partials]
    periods += [points for _, points in sorted((partials.get("extraPeriods") or {}).items(), key=lambda kv: int(kv[0]))]
    return {"code": str(club["code"]).strip(), "name": str(club["name"]), "score": side.get("score"), "periods": periods}


def parse_games(data: Any) -> List[Dict[str, Any]]:
    """``[{season_code, game_code, played, utc_date, round, phase, home, away}]`` of the games of a season (``home`` is the ``local`` club). ``home`` and ``away`` carry the club code and name, the points and the
    points of each period (the extra ones after the fourth)."""
    out = []
    for line in _items(data):
        season, code = line.get("season"), line.get("gameCode")
        if not isinstance(season, dict) or not season.get("code") or not isinstance(code, int) or "played" not in line:
            raise EuroleaguePageError(f"a game of the calendar lacks its season, its code or whether it was played: {sorted(line)}")
        out.append({"season_code": str(season["code"]), "game_code": code, "played": bool(line["played"]), "utc_date": line.get("utcDate"), "round": line.get("roundName"),
                    "phase": (line.get("phaseType") or {}).get("code"), "home": _side(line, "local"), "away": _side(line, "road")})
    return out


def parse_seasons(data: Any) -> List[Dict[str, Any]]:
    """``[{code, year, name}]`` of the seasons of a competition (``E2025``; every tournament of the U18 is one, ``JTA25``). ``year`` is the one the season starts in."""
    out = []
    for item in _items(data):
        if not item.get("code") or not isinstance(item.get("year"), int):
            raise EuroleaguePageError(f"a season lacks its code or its year: {sorted(item)}")
        out.append({"code": str(item["code"]), "year": item["year"], "name": item.get("name")})
    return out


def _date(text: Optional[str]) -> Optional[str]:
    return text[:10] if text else None


def _player(item: Dict[str, Any]) -> Dict[str, Any]:
    person, stats = item.get("player", {}).get("person"), item.get("stats")
    if not isinstance(person, dict) or not isinstance(stats, dict) or not person.get("code") or not person.get("name"):
        raise EuroleaguePageError("a player of the box lacks his person or his statistics")
    return {"id": str(person["code"]), "name": str(person["name"]), "number": str(item["player"].get("dorsal") or stats.get("dorsal") or ""), "started": bool(stats.get("startFive")),
            "seconds": int(stats.get("timePlayed") or 0), "birth": _date(person.get("birthDate")), "height_cm": person.get("height") or None,
            "nationality": (person.get("country") or {}).get("name"), "position": item["player"].get("positionName"), "stats": {k: v for k, v in stats.items() if isinstance(v, (int, float))}}


def _team_box(side: Any) -> Dict[str, Any]:
    if not isinstance(side, dict) or not isinstance(side.get("players"), list) or not side["players"] or not isinstance(side.get("total"), dict) or not isinstance(side.get("team"), dict):
        raise EuroleaguePageError("a side of the box lacks its players, its total or the team's own actions")
    players = [_player(p) for p in side["players"]]
    club = side["players"][0]["player"].get("club") or {}
    return {"code": str(club.get("code") or "").strip(), "name": club.get("name"), "players": players, "totals": side["total"], "own": side["team"]}


def parse_stats(data: Any) -> List[Dict[str, Any]]:
    """``[home, away]``, each ``{code, name, players, totals, own}``: the official box of ``games/<code>/stats``. ``totals`` is the official total of the team and ``own`` what the team itself did (its
    rebounds and turnovers, which no player has): the players and ``own`` add up to ``totals``."""
    if not isinstance(data, dict):
        raise EuroleaguePageError("the box is not an object")
    return [_team_box(data.get("local")), _team_box(data.get("road"))]


def _clean(value: Any) -> Optional[str]:
    text = str(value).strip() if value is not None else ""
    return text or None


def _play(raw: Dict[str, Any], period: int) -> Dict[str, Any]:
    if not isinstance(raw.get("NUMBEROFPLAY"), int) or not raw.get("PLAYTYPE"):
        raise EuroleaguePageError(f"a play lacks its number or its type: {sorted(raw)}")
    player = _clean(raw.get("PLAYER_ID"))
    return {"number": raw["NUMBEROFPLAY"], "period": period, "type": str(raw["PLAYTYPE"]).strip(), "team": _clean(raw.get("CODETEAM")),
            "player": player[1:] if player and player.startswith("P") else player, "name": raw.get("PLAYER"), "dorsal": _clean(raw.get("DORSAL")), "clock": raw.get("MARKERTIME") or "",
            "score_home": raw.get("POINTS_A"), "score_away": raw.get("POINTS_B"), "info": raw.get("PLAYINFO") or ""}


def parse_play_by_play(data: Any) -> Dict[str, Any]:
    """``{home_code, away_code, plays}`` of ``PlayByPlay``: one dict per play in the order of the game (the four quarters and then the extra periods)."""
    if not isinstance(data, dict) or not all(isinstance(data.get(q), list) for q in (*QUARTERS, "ExtraTime")) or not data.get("CodeTeamA") or not data.get("CodeTeamB"):
        raise EuroleaguePageError("the answer is not a play by play (the quarters or the teams are missing)")
    plays = [_play(raw, block + 1) for block, key in enumerate(QUARTERS) for raw in data[key] if isinstance(raw, dict)]
    begun = 0
    for raw in (r for r in data["ExtraTime"] if isinstance(r, dict)):                  # the extra periods share one list: each one's «begin period» comes AFTER the substitutions that open it
        begun += 1 if raw.get("PLAYTYPE") == "BP" else 0
        plays.append(_play(raw, len(QUARTERS) + max(begun, 1)))
    if not plays:
        raise EuroleaguePageError("the play by play has no plays")
    return {"home_code": data["CodeTeamA"].strip(), "away_code": data["CodeTeamB"].strip(), "plays": sorted(plays, key=lambda p: p["number"])}


def parse_points(data: Any) -> List[Dict[str, Any]]:
    """``[{number, type, team, player, made, points, x, y, zone}]`` of ``Points``: the field goals with their coordinates (centimetres from the hoop, ``x`` across the court and ``y`` along it). ``number`` is
    the number of the play of the play by play. The free throws have no position (``-1``) and are left out."""
    rows = data.get("Rows") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise EuroleaguePageError("the answer is not a list of shots")
    shots = []
    for row in rows:
        kind = _clean(row.get("ID_ACTION")) if isinstance(row, dict) else None
        if kind not in FIELD_GOALS:
            continue
        if not isinstance(row.get("NUM_ANOT"), int) or not isinstance(row.get("COORD_X"), int) or not isinstance(row.get("COORD_Y"), int):
            raise EuroleaguePageError(f"a shot lacks its number or its coordinates: {row}")
        player = _clean(row.get("ID_PLAYER"))
        shots.append({"number": row["NUM_ANOT"], "type": kind, "team": _clean(row.get("TEAM")), "player": player[1:] if player and player.startswith("P") else player, "made": kind.endswith("M"),
                      "points": int(kind[0]), "x": row["COORD_X"], "y": row["COORD_Y"], "zone": _clean(row.get("ZONE"))})
    return sorted(shots, key=lambda s: s["number"])


def parse_game(line: Dict[str, Any], stats: Any, play_by_play: Any, points: Any) -> Dict[str, Any]:
    """A game whole: the line of the calendar (``parse_games``) and the three answers of the game. ``{season_code, game_code, utc_date, round, phase, teams: [home, away], plays, shots}``. The answers
    must be of the same game: the teams of the box and of the play by play are the ones of the calendar, in the same order."""
    teams, played = parse_stats(stats), parse_play_by_play(play_by_play)
    expected = (line["home"]["code"], line["away"]["code"])
    if (teams[0]["code"], teams[1]["code"]) != expected or (played["home_code"], played["away_code"]) != expected:
        raise EuroleaguePageError(f"the answers are not of the game {line['season_code']} {line['game_code']}: its teams are {expected}, the box has {(teams[0]['code'], teams[1]['code'])} "
                                  f"and the play by play {(played['home_code'], played['away_code'])}")
    for team, side in zip(teams, ("home", "away")):
        team["name"], team["periods"], team["score"] = line[side]["name"], line[side]["periods"], line[side]["score"]
    return {"season_code": line["season_code"], "game_code": line["game_code"], "utc_date": line["utc_date"], "round": line["round"], "phase": line["phase"], "teams": teams, "plays": played["plays"],
            "shots": parse_points(points)}
