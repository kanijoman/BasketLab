"""A NCAA game of ESPN as the canonical document of an external source (#888, D4 of epic #872): the result of ``ncaa_page.parse_summary`` as the FEB document, with ``_league: ncaa`` and every id
prefixed (``ncaa:265``), written the way ``fiba_canonical`` writes FIBA's so that nothing forks:

* ``HEADER``: the game, the kick-off (``dd-mm-yyyy - HH:MM``, the UTC time ESPN gives), the two teams HOME FIRST with their score and the conference each one played in THAT day (``conference_id``,
  ``conference``) and whether it is Division I (``division1``, #966), and the points of each period (men play two halves of 20 minutes, women four quarters, an overtime is one more period);
* ``BOXSCORE.TEAM[]``: the OFFICIAL box of both teams (the minutes in seconds, ``None`` for who did not play), the total of the players and, apart, what the team itself did (team rebounds and turnovers:
  what the box of the team has over the sum of its players);
* ``PLAYBYPLAY.LINES``: one line per play of ESPN, with the keywords the engine matches (``TIRO DE 2 ANOTADO``, ``MATE``, ``Faltas: n.``). An event that is not known is kept as a line of ``other``.

The game is kept COMPLETE: both teams, the box of both and every play, also when a team is not Division I (which players are kept is decided by who reads the document). Not in this version: the shot
chart (ESPN gives the court coordinates of each shot; their mapping to the zones of the engine is a block of its own). Pure functions, no I/O, nothing of the game is changed.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from src.market.canonical import period_scheme, source_id

SOURCE = "ncaa"
_STATS = ("pts", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "reb", "ast", "tov", "stl", "blk", "orb", "drb", "pf")


def _seconds(minutes: int) -> str:
    return str(int(minutes) * 60)


def _starttime(date: str) -> str:
    day, _, hour = date.rstrip("Z").partition("T")
    year, month, number = day.split("-")
    return f"{number}-{month}-{year} - {hour[:5]}"


def _clock(text: str) -> str:
    minutes, _, seconds = (text or "0:00").partition(":")
    return f"{int(minutes):02d}:{int(float(seconds or 0)):02d}"


def _player_box(player: Dict[str, Any]) -> Dict[str, Any]:
    stats = player["stats"]
    base = {"id": source_id(SOURCE, player["id"]), "name": player["name"], "no": player["jersey"], "sta": "*" if player["starter"] else None}
    if stats is None:
        return {**base, "min": None, **{k: None for k in ("pts", "p1m", "p1a", "p2m", "p2a", "p3m", "p3a", "fgm", "fga", "assist", "bs", "st", "to", "ro", "rd", "rt", "pf", "rf", "val")}}
    return {**base, "min": _seconds(stats["minutes"]), "pts": str(stats["pts"]), "p1m": str(stats["ftm"]), "p1a": str(stats["fta"]), "p2m": str(stats["fgm"] - stats["tpm"]),
            "p2a": str(stats["fga"] - stats["tpa"]), "p3m": str(stats["tpm"]), "p3a": str(stats["tpa"]), "fgm": str(stats["fgm"]), "fga": str(stats["fga"]), "assist": str(stats["ast"]),
            "bs": str(stats["blk"]), "st": str(stats["stl"]), "to": str(stats["tov"]), "ro": str(stats["orb"]), "rd": str(stats["drb"]), "rt": str(stats["reb"]), "pf": str(stats["pf"]),
            "rf": None, "val": None}


def _team_box(team: Dict[str, Any], players: List[Dict[str, Any]], totals: Dict[str, Any], won: bool, names: Dict[str, str]) -> Dict[str, Any]:
    played = [p["stats"] for p in players if p["stats"]]
    add = Counter()
    for stats in played:
        add.update({k: v for k, v in stats.items() if k != "minutes"})
    total = {"pts": str(add["pts"]), "p1m": str(add["ftm"]), "p1a": str(add["fta"]), "p2m": str(add["fgm"] - add["tpm"]), "p2a": str(add["fga"] - add["tpa"]), "p3m": str(add["tpm"]), "p3a": str(add["tpa"]),
             "fgm": str(add["fgm"]), "fga": str(add["fga"]), "assist": str(add["ast"]), "bs": str(add["blk"]), "st": str(add["stl"]), "to": str(add["tov"]), "ro": str(add["orb"]), "rd": str(add["drb"]),
             "rt": str(add["reb"]), "pf": str(add["pf"])}
    own = lambda name, summed: str(max(0, int(totals.get(name) or 0) - summed))                  # what the box of the team has over the sum of its players
    actions = {"ro": own("offensiveRebounds", add["orb"]), "rd": own("defensiveRebounds", add["drb"]), "rt": own("totalRebounds", add["reb"]), "to": str(int(totals.get("teamTurnovers") or 0)),
               "pf": own("fouls", add["pf"])}
    return {"id": source_id(SOURCE, team["id"]), "name": team["name"], "teamCode": None, "win_lose": "W" if won else "L", "conference_id": team["conference_id"], "conference": names.get(team["conference_id"] or ""),
            "division1": team["division1"], "TOTAL": total, "TEAMACTIONS": actions, "PLAYER": [_player_box(p) for p in players]}


class _Lines:
    """The play by play of a game as the lines of a FEB document, one per play."""

    def __init__(self, game: Dict[str, Any], regulation: int) -> None:
        self.regulation = regulation
        self.teams = {t["id"]: t["name"] for t in game["teams"]}
        self.players = {p["id"]: p["name"] for players in game["players"].values() for p in players}
        self.fouls: Counter = Counter()

    def _who(self, play: Dict[str, Any]) -> str:
        team, player = self.teams.get(play["team_id"] or "", ""), self.players.get(play["athlete_id"] or "", "")
        return f"({team}) {player}" if player else f"({team})" if team else ""

    def _period_end(self, play: Dict[str, Any]) -> str:
        if play["type"] == "End Game":
            return "Fin del partido"
        number = play["period"]
        if number > self.regulation:
            return f"Fin de la Prórroga {number - self.regulation}"
        return f"Fin de la Parte {number}" if self.regulation == 2 else f"Fin del Cuarto {number}"

    def line(self, play: Dict[str, Any]) -> Dict[str, Any]:
        kind, who, text = play["type"], self._who(play), play["text"]
        action = "other"
        if play["shooting"]:
            made = "ANOTADO" if play["scoring"] else "FALLADO"
            value = play["points_attempted"] or play["points"] or 2
            if value == 1 or kind.endswith("FreeThrow"):
                action, text = "fthrow", f"{who}: TIRO DE 1 {made}"
            else:
                action, text = "shoot", f"{who}: " + (f"MATE {made}" if kind == "DunkShot" else f"TIRO DE {value} {made}")
        elif kind in ("Offensive Rebound", "Defensive Rebound", "Dead Ball Rebound"):
            side = " OFENSIVO" if kind == "Offensive Rebound" else " DEFENSIVO" if kind == "Defensive Rebound" else ""
            action = "rebound"
            text = f"{who}: REBOTE{side}" if play["athlete_id"] else f"{who} REBOTE DE EQUIPO{side}"
        elif kind == "Steal":
            action, text = "recovery", f"{who}: RECUPERACIÓN"
        elif "Turnover" in kind:
            action, text = "lose", f"{who}: PÉRDIDA" if play["athlete_id"] else f"{who} PÉRDIDA DE EQUIPO"
        elif kind == "Block Shot":
            action, text = "blockshot", f"{who}: TAPÓN"
        elif kind == "PersonalFoul":
            self.fouls[play["athlete_id"]] += 1
            action, text = "foul", f"{who}: FALTA PERSONAL. Faltas: {self.fouls[play['athlete_id']]}."
        elif kind == "Technical Foul":
            action, text = "foul", f"{who}: FALTA TÉCNICA"
        elif kind == "Substitution":
            action, text = "subst", f"{who}: " + ("ENTRA A PISTA" if "subbing in" in text else "SALE DE PISTA")
        elif "TimeOut" in kind:
            action, text = "timeout", f"{who} TIEMPO MUERTO" if play["team_id"] else "TIEMPO MUERTO DE TELEVISIÓN"
        elif kind in ("End Period", "End Game"):
            action, text = "period", self._period_end(play)
        return {"num": "", "quarter": str(play["period"]), "time": _clock(play["clock"]), "idTeam": source_id(SOURCE, play["team_id"]) if play["team_id"] else None,
                "idPlayer": source_id(SOURCE, play["athlete_id"]) if play["athlete_id"] else None, "idLicense": source_id(SOURCE, play["athlete_id"]) if play["athlete_id"] else None,
                "action": action, "text": text, "deleted": None, "scoreA": str(play["home_score"]) if play["home_score"] is not None else None,
                "scoreB": str(play["away_score"]) if play["away_score"] is not None else None}

    def build(self, plays: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        lines = [self.line(p) for p in plays]
        for number, line in enumerate(lines, start=1):
            line["num"] = str(number)
        return lines


def to_canonical(game: Dict[str, Any], entry: Dict[str, Any], conference_names: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """The canonical document of a game as ``ncaa_page.parse_summary`` read it, for the competition ``entry`` of the catalogue (its sex, season and name). ``conference_names`` maps the id of a conference to its
    name (the list of its season). The game read is not changed."""
    names = conference_names or {}
    scheme = period_scheme(SOURCE, entry["gender"])
    home = next(t for t in game["teams"] if t["home"])
    away = next(t for t in game["teams"] if not t["home"])
    quarters = [{"n": str(i), "scoreA": str(a), "scoreB": str(b)} for i, (a, b) in enumerate(zip(home["periods"], away["periods"]), start=1)]
    header_team = lambda t: {"pts": str(t["score"]), "fouls": None, "id": source_id(SOURCE, t["id"]), "name": t["name"], "logo": None, "teamCode": None, "clubCode": None,
                             "conference_id": t["conference_id"], "conference": names.get(t["conference_id"] or ""), "division1": t["division1"]}
    header = {"CompID": f"{entry['competition']} {entry['season_value']}", "competition": entry["competition"], "round": None, "quarter": len(quarters), "time": "FINAL", "logo": None, "duration": None,
              "starttime": _starttime(game["date"]), "place": None, "field": None, "status": "3", "statusText": "FINISHED", "TEAM": [header_team(home), header_team(away)],
              "QUARTERS": {"QUARTER": quarters}, "game_code": str(game["game_id"])}
    box = [_team_box(t, game["players"][t["id"]], game["totals"].get(t["id"], {}), t["score"] > other["score"], names) for t, other in ((home, away), (away, home))]
    return {"_id": source_id(SOURCE, game["game_id"]), "_league": SOURCE, "_season": str(entry["season_value"]), "HEADER": header,
            "PLAYBYPLAY": {"duration": None, "hasExtension": len(quarters) > scheme.periods, "LINES": _Lines(game, scheme.periods).build(game["plays"])},
            "BOXSCORE": {"duration": None, "TEAM": box}, "SHOTCHART": {"SHOTS": [], "TEAM": []}}
