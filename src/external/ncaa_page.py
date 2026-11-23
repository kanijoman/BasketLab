"""What the NCAA reader takes from the answers of ESPN (#888, D4 of epic #872; #966).

ESPN is read as JSON. Two families of answers:

* the ones that tell WHICH competitions exist and WHO plays in each: the conferences of a season and the standings of that season, which give every team the conference it played in THAT season (a team
  that changes conference between two seasons has the old one in the old season: realignments do not rewrite the past);
* the ones that tell what HAPPENED: the scoreboard of a day (which games are over and who plays them) and the ``summary`` of a game (the official box, the teams with the conference they played in that
  day and the play by play).

An answer whose shape is not the one expected is a ``NcaaPageError`` and is never read as an empty season or game: a quiet empty list would hide that ESPN changed.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

DIVISION_GROUP = "50"                    # «Division I», the group of all the conferences: the id ESPN asks for, not a conference


class NcaaPageError(Exception):
    """The answer is not in a format the reader knows (asking again would not change it, so it is not retried)."""


def _list(data: Any, key: str) -> List[Dict[str, Any]]:
    items = data.get(key) if isinstance(data, dict) else None
    if not isinstance(items, list) or not items or not all(isinstance(i, dict) for i in items):
        raise NcaaPageError(f"the answer has no '{key}' list")
    return items


def parse_conferences(data: Any) -> List[Dict[str, str]]:
    """``[{id, name, short}]`` of the conferences a season has (the division itself is not one). ``short`` is the name the fans use («ACC», «Big 12»), the one the catalogue and the collections carry."""
    out = []
    for item in _list(data, "conferences"):
        group, name = item.get("groupId"), item.get("name")
        if not group or not name:
            raise NcaaPageError(f"a conference lacks its id or its name: {item}")
        if str(group) != DIVISION_GROUP:
            out.append({"id": str(group), "name": str(name), "short": str(item.get("shortName") or name)})
    if not out:
        raise NcaaPageError("the answer lists no conference")
    return out


def parse_standings(data: Any) -> Dict[str, Dict[str, str]]:
    """``{team id: {name, conference_id, conference}}``: the conference each team played in, from the standings of the season."""
    teams: Dict[str, Dict[str, str]] = {}
    for conference in _list(data, "children"):
        if not conference.get("id") or not conference.get("name") or not isinstance(conference.get("standings", {}).get("entries"), list):
            raise NcaaPageError(f"a conference of the standings lacks its id, its name or its teams: {sorted(conference)}")
        for entry in conference["standings"]["entries"]:
            team = entry.get("team") or {}
            if not team.get("id"):
                raise NcaaPageError(f"a team of the standings lacks its id: {entry}")
            teams[str(team["id"])] = {"name": str(team.get("displayName") or ""), "conference_id": str(conference["id"]), "conference": str(conference["name"])}
    if not teams:
        raise NcaaPageError("the standings list no team")
    return teams


def _conference_of(groups: Any) -> Optional[str]:
    """The id of the Division I conference a team plays in, or ``None`` when it is not a Division I team (ESPN says ``isConference: false`` and a group of «non-ncaa-division-i»)."""
    if isinstance(groups, dict) and groups.get("isConference") is True and str((groups.get("parent") or {}).get("id")) == DIVISION_GROUP and groups.get("id"):
        return str(groups["id"])
    return None


def parse_scoreboard(data: Any) -> List[Dict[str, Any]]:
    """The games of a day: ``{game_id, date, finished, neutral, teams: [{id, name, home, score, conference_id}]}`` (``conference_id`` is ``None`` for a team that is not Division I)."""
    events = data.get("events") if isinstance(data, dict) else None
    if not isinstance(events, list):
        raise NcaaPageError("the answer has no 'events' list")
    games = []
    for event in events:
        try:
            competition = event["competitions"][0]
            teams = [{"id": str(c["team"]["id"]), "name": str(c["team"].get("displayName") or ""), "home": c["homeAway"] == "home", "score": int(c["score"]) if c.get("score") not in (None, "") else None,
                      "conference_id": str(c["team"]["conferenceId"]) if c["team"].get("conferenceId") else None} for c in competition["competitors"]]
            games.append({"game_id": str(event["id"]), "date": str(event["date"]), "finished": event["status"]["type"]["name"] == "STATUS_FINAL", "neutral": bool(competition.get("neutralSite")), "teams": teams})
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise NcaaPageError(f"an event of the scoreboard is not in the expected format ({type(error).__name__}: {error})") from error
    return games


_BOX_KEYS = ["minutes", "points", "fieldGoalsMade-fieldGoalsAttempted", "threePointFieldGoalsMade-threePointFieldGoalsAttempted", "freeThrowsMade-freeThrowsAttempted", "rebounds", "assists", "turnovers",
             "steals", "blocks", "offensiveRebounds", "defensiveRebounds", "fouls"]


def _made_attempted(text: str) -> Tuple[int, int]:
    made, _, attempted = text.partition("-")
    return int(made), int(attempted)


def _player_stats(keys: List[str], values: List[str]) -> Dict[str, int]:
    """The official numbers of a player; the columns must be the known ones (a box that changed its columns is an error, never a column read as another)."""
    if list(keys) != _BOX_KEYS:
        raise NcaaPageError(f"the columns of the box are not the known ones: {keys}")
    row = dict(zip(keys, values))
    fgm, fga = _made_attempted(row["fieldGoalsMade-fieldGoalsAttempted"])
    tpm, tpa = _made_attempted(row["threePointFieldGoalsMade-threePointFieldGoalsAttempted"])
    ftm, fta = _made_attempted(row["freeThrowsMade-freeThrowsAttempted"])
    return {"minutes": int(row["minutes"]), "pts": int(row["points"]), "fgm": fgm, "fga": fga, "tpm": tpm, "tpa": tpa, "ftm": ftm, "fta": fta, "reb": int(row["rebounds"]), "ast": int(row["assists"]),
            "tov": int(row["turnovers"]), "stl": int(row["steals"]), "blk": int(row["blocks"]), "orb": int(row["offensiveRebounds"]), "drb": int(row["defensiveRebounds"]), "pf": int(row["fouls"])}


def _player(athlete: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    info = athlete["athlete"]
    values = athlete.get("stats") or []
    dnp = bool(athlete.get("didNotPlay")) or not values
    return {"id": str(info["id"]), "name": str(info.get("displayName") or ""), "jersey": info.get("jersey"), "position": (info.get("position") or {}).get("abbreviation"),
            "starter": bool(athlete.get("starter")), "dnp": dnp, "stats": None if dnp else _player_stats(keys, values)}


def _play(raw: Dict[str, Any]) -> Dict[str, Any]:
    participants = [(p.get("athlete") or {}).get("id") for p in raw.get("participants") or []]
    athlete = participants[0] if participants else None
    assist = participants[1] if len(participants) > 1 and raw.get("scoringPlay") else None            # a made shot names the player who assisted it second
    coordinate = raw.get("coordinate") or {}
    return {"seq": str(raw["sequenceNumber"]), "period": int(raw["period"]["number"]), "clock": str((raw.get("clock") or {}).get("displayValue") or "0:00"),
            "team_id": str(raw["team"]["id"]) if raw.get("team") else None, "type": str(raw["type"]["text"]), "text": str(raw.get("text") or ""), "scoring": bool(raw.get("scoringPlay")),
            "points": int(raw.get("scoreValue") or 0) if raw.get("scoringPlay") else 0, "shooting": bool(raw.get("shootingPlay")), "points_attempted": int(raw.get("pointsAttempted") or 0),
            "athlete_id": str(athlete) if athlete else None, "assist_id": str(assist) if assist else None, "x": coordinate.get("x"), "y": coordinate.get("y"), "home_score": raw.get("homeScore"), "away_score": raw.get("awayScore"),
            "wallclock": raw.get("wallclock")}


def parse_summary(data: Any) -> Dict[str, Any]:
    """A game as ESPN's ``summary`` gives it: ``{game_id, date, finished, neutral, teams, players, totals, plays}``.

    ``teams``: ``{id, name, home, score, periods, conference_id, division1}`` (the conference is the one the team played in THAT day, as the game says it; a team that is not Division I has ``None`` and
    ``division1: False``); ``players``: ``{team id: [{id, name, jersey, position, starter, dnp, stats}]}`` with the official numbers of the box (``stats`` is ``None`` for who did not play); ``totals``:
    ``{team id: {name: value}}`` of the team box, which includes what the team itself did (team rebounds and turnovers); ``plays``: every event of the play by play (it can come empty)."""
    try:
        header = data["header"]
        competition = header["competitions"][0]
        teams = [{"id": str(c["team"]["id"]), "name": str(c["team"].get("displayName") or ""), "home": c["homeAway"] == "home", "score": int(c["score"]),
                  "periods": [int(p["displayValue"]) for p in c.get("linescores") or []], "conference_id": _conference_of(c["team"].get("groups")),
                  "division1": _conference_of(c["team"].get("groups")) is not None} for c in competition["competitors"]]
        players: Dict[str, List[Dict[str, Any]]] = {}
        for entry in data["boxscore"]["players"]:
            groups = entry["statistics"]
            keys = groups[0]["keys"] if groups else []
            players[str(entry["team"]["id"])] = [_player(a, keys) for g in groups for a in g["athletes"]]
        totals = {str(t["team"]["id"]): {s["name"]: s.get("displayValue") for s in t.get("statistics") or []} for t in data["boxscore"]["teams"]}
        plays = [_play(p) for p in data.get("plays") or []]
        status = (competition.get("status") or {}).get("type", {}).get("name")
        if len(teams) != 2 or set(players) != {t["id"] for t in teams}:
            raise NcaaPageError("the game does not have two teams with their box")
        return {"game_id": str(header["id"]), "date": str(competition["date"]), "finished": status == "STATUS_FINAL", "neutral": bool(competition.get("neutralSite")), "teams": teams,
                "players": players, "totals": totals, "plays": plays}
    except NcaaPageError:
        raise
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as error:
        raise NcaaPageError(f"the game is not in the expected format ({type(error).__name__}: {error})") from error
