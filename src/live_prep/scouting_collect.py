"""What the live engine sees of ONE team over its games: the data of the rival scouting report (issue #299).

``scout_team(games, team_id)`` replays every game of the team "as live" from ITS side, with the package it would have had
before that game (``SeasonAccumulator``: only earlier games), through the very engine of the app, and gathers: results,
Four Factors and pace, players with their production and clutch, the most used quintets with their net rating, zones (own
shots and shots conceded against the league), scoring by quarter and at the starts and closes of quarters, timeouts and
what follows them, and the alerts the engine raises for that team, how often and when. The team is a parameter: nothing
here is specific to any team. Games arrive in date order, one at a time (memory), and only plain Python types come out.
"""

from __future__ import annotations

import heapq
from collections import Counter
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from src.live_core.advice import AdviceEngine
from src.live_core.engine import LiveEngine
from src.live_core.four_factors import GAME_SECONDS, factors, possessions

from src.pbp.game_derived import DERIVED_VERSION, derive_game_fields

from .eval_feed import finished_game_polls
from .eval_source import game_code, parse_starttime, same_start_groups
from .package_builder import SeasonAccumulator

FIXED_DATE = "1970-01-01T00:00:00Z"
QUARTER_S = 600
EDGE_S = 180            # the "start" and the "close" of a quarter: its first and last three minutes
TIMEOUT_WINDOW_S = 120  # what happens after a timeout
TOP_PLAYERS, TOP_LINEUPS, TOP_ALERTS = 10, 8, 12
FACTOR_KEYS = ("efg", "tov", "orb", "ftr")
ORIGIN_KEYS = ("pts_off_tov", "pts_second_chance", "pts_paint")    # points of the team and conceded; the bench is only the team's


def _reliable_teams(game: Dict[str, Any]) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """The ``DERIVED`` figures of both teams of a game, or None when it cannot be read or is not reliable for the possession figures (#390)."""
    derived = game.get("DERIVED")
    if not derived or derived.get("v") != DERIVED_VERSION:      # not stored (or an older version): compute it from the full document
        derived = derive_game_fields(game)
    teams = (derived or {}).get("TEAM") or []
    return (teams[0], teams[1]) if len(teams) == 2 and all(t.get("reliable") for t in teams) else None


class _League:
    """Per team-game averages of the origin figures over every reliable game of the competition."""

    def __init__(self) -> None:
        self.sums: Counter = Counter()
        self.team_games = 0

    def add(self, teams: Tuple[Dict[str, Any], Dict[str, Any]]) -> None:
        for t in teams:
            self.team_games += 1
            self.sums.update({k: t.get(k) or 0 for k in (*ORIGIN_KEYS, "pts_bench", "pts")})

    def result(self) -> Dict[str, float]:
        n = self.team_games or 1
        out = {k: self.sums[k] / n for k in (*ORIGIN_KEYS, "pts_bench")}
        out["bench_pct"] = self.sums["pts_bench"] / self.sums["pts"] * 100 if self.sums["pts"] else 0.0
        return out


def _about_the_team(rule_id: str) -> bool:
    """The engine also warns about the RIVAL of the perspective (hot shooters, fouls...): that says nothing of the scouted team.
    ``rival_run`` stays (a run AGAINST the team) and the quarter summary is not a pattern."""
    return rule_id != "period_summary" and (not rule_id.startswith("rival_") or rule_id == "rival_run")


def _period(elapsed: float) -> int:
    """Period of a game-second (the second a quarter ends still belongs to it)."""
    e = max(0.0, elapsed - 1e-9)
    return int(e // QUARTER_S) + 1 if e < GAME_SECONDS else 5 + int((e - GAME_SECONDS) // 300)


def _points(log: Sequence[Sequence[Any]], team: str, start: float, end: float) -> int:
    """Points of ``team`` scored in the game-seconds ``(start, end]``."""
    return sum(e[3] for e in log if e[1] == team and e[2] == "pts" and start < e[0] <= end)


class _Agg:
    """Sums over the games of the team; ``result`` turns them into averages."""

    def __init__(self, team: str) -> None:
        self.team, self.games = team, []
        self.name = team
        self.factors = {"own": Counter(), "rival": Counter()}
        self.pace = 0.0
        self.players: Dict[str, Dict[str, Any]] = {}
        self.lineups: Dict[Tuple[str, ...], Dict[str, Any]] = {}
        self.zones = {"own": {}, "conceded": {}}
        self.quarters: Dict[int, List[float]] = {}                     # period -> [for, against]
        self.edges = {"start": {p: [0, 0] for p in range(1, 5)}, "close": {p: [0, 0] for p in range(1, 5)}}
        self.timeouts = Counter()
        self.origin = {"games": 0, "own": Counter(), "conceded": Counter()}
        self.alerts: Dict[str, Dict[str, Any]] = {}

    def add(self, game: Dict[str, Any], opp: str, snap: Dict[str, Any], alerts: List[Dict[str, Any]],
            derived: Optional[Tuple[Dict[str, Any], Dict[str, Any]]] = None, note: Optional[Dict[str, Any]] = None) -> None:
        mine, theirs = snap["teams"][self.team], snap["teams"][opp]
        self.name = mine.get("name") or self.team
        score_for, score_against = snap["score"][self.team], snap["score"][opp]
        start = parse_starttime(game)
        self.games.append({
            "code": game_code(game), "date": start.isoformat() if start else "", "opponent_id": opp,
            "opponent": theirs.get("name") or opp, "home": snap.get("home_id") == self.team,
            "score_for": score_for, "score_against": score_against, "margin": score_for - score_against, **(note or {})})
        self._factors_and_pace(mine["stats"], theirs["stats"], snap["elapsed"])
        self._players(snap)
        self._lineups(snap)
        for key, tid in (("own", self.team), ("conceded", opp)):
            _sum_cells(self.zones[key], snap["zones"].get(tid, {}))
        self._quarters_and_timeouts(snap["log"], opp)
        self._origin(derived)
        self._alerts(alerts)

    def _factors_and_pace(self, own: Dict[str, int], rival: Dict[str, int], elapsed: float) -> None:
        for key, (a, b) in (("own", (own, rival)), ("rival", (rival, own))):
            self.factors[key].update(factors(a, b))
        if elapsed:
            self.pace += (possessions(own) + possessions(rival)) / 2 / elapsed * GAME_SECONDS

    def _players(self, snap: Dict[str, Any]) -> None:
        for pid, p in snap["players"].items():
            if p["team_id"] != self.team or p["minutes"] <= 0:
                continue
            row = self.players.setdefault(pid, {"id": pid, "name": p["name"], "games": 0, "minutes": 0, "pts": 0, "fga": 0,
                                                "clutch": {k: 0 for k in ("fga", "fta", "ftm", "tov", "pts", "sec")}})
            row["games"] += 1
            row["minutes"] += p["minutes"]
            row["pts"] += p["pts"]
            row["fga"] += p["stats"].get("fg2a", 0) + p["stats"].get("fg3a", 0)
            for k in row["clutch"]:
                row["clutch"][k] += p["clutch"].get(k, 0)

    def _lineups(self, snap: Dict[str, Any]) -> None:
        names = {pid: p["name"] for pid, p in snap["players"].items()}
        for row in snap.get("lineups", {}).get(self.team, []):
            key = tuple(sorted(row["players"]))
            total = self.lineups.setdefault(key, {"seconds": 0, "pts_for": 0, "pts_against": 0, "games": 0,
                                                  "names": [names.get(pid, pid) for pid in key]})
            for k in ("seconds", "pts_for", "pts_against"):
                total[k] += row[k]
            total["games"] += 1

    def _quarters_and_timeouts(self, log: Sequence[Sequence[Any]], opp: str) -> None:
        for p in range(1, 5):
            lo, hi = (p - 1) * QUARTER_S, p * QUARTER_S
            self.quarters.setdefault(p, [0, 0])
            self.quarters[p][0] += _points(log, self.team, lo, hi)
            self.quarters[p][1] += _points(log, opp, lo, hi)
            for edge, (a, b) in (("start", (lo, lo + EDGE_S)), ("close", (hi - EDGE_S, hi))):
                self.edges[edge][p][0] += _points(log, self.team, a, b)
                self.edges[edge][p][1] += _points(log, opp, a, b)
        for e in log:
            if e[1] == self.team and e[2] == "timeout":
                self.timeouts["n"] += 1
                self.timeouts["first_half" if e[0] <= GAME_SECONDS / 2 else "second_half"] += 1
                self.timeouts["after_for"] += _points(log, self.team, e[0], e[0] + TIMEOUT_WINDOW_S)
                self.timeouts["after_against"] += _points(log, opp, e[0], e[0] + TIMEOUT_WINDOW_S)

    def _origin(self, derived: Optional[Tuple[Dict[str, Any], Dict[str, Any]]]) -> None:
        if not derived:
            return
        mine, theirs = (derived[0], derived[1]) if derived[0]["id"] == self.team else (derived[1], derived[0])
        self.origin["games"] += 1
        self.origin["own"].update({k: mine.get(k) or 0 for k in (*ORIGIN_KEYS, "pts_bench", "pts")})
        self.origin["conceded"].update({k: theirs.get(k) or 0 for k in ORIGIN_KEYS})

    def _alerts(self, alerts: List[Dict[str, Any]]) -> None:
        game = len(self.games)
        for a in (a for a in alerts if _about_the_team(a["id"])):
            row = self.alerts.setdefault(a["id"], {"id": a["id"], "category": a["category"], "count": 0, "games": set(),
                                                   "minutes": 0.0, "severity": Counter(), "message": a["message"]})
            row["count"] += 1
            row["games"].add(game)
            row["minutes"] += a["elapsed"] / 60
            row["severity"][a["severity"]] += 1

    def result(self, league_zones: Dict[str, Dict[str, int]], league_origin: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        n = len(self.games)
        total = sum(p["pts"] for p in self.players.values()) or 1
        players = sorted(({**p, "minutes": round(p["minutes"] / 60, 1), "pts_per_game": p["pts"] / n, "share": p["pts"] / total}
                          for p in self.players.values()), key=lambda p: (-p["pts"], p["name"]))[:TOP_PLAYERS]
        lineups = sorted(({"players": v["names"], "seconds": v["seconds"], "pts_for": v["pts_for"], "pts_against": v["pts_against"],
                           "games": v["games"], "net40": round((v["pts_for"] - v["pts_against"]) / v["seconds"] * GAME_SECONDS, 1)}
                          for v in self.lineups.values() if v["seconds"] > 0), key=lambda r: (-r["seconds"], r["players"]))[:TOP_LINEUPS]
        alerts = sorted(({"id": a["id"], "category": a["category"], "count": a["count"], "games": len(a["games"]),
                          "per_game": a["count"] / n, "avg_minute": a["minutes"] / a["count"],
                          "severity": a["severity"].most_common(1)[0][0], "message": a["message"]} for a in self.alerts.values()),
                        key=lambda a: (-a["count"], a["id"]))[:TOP_ALERTS]
        t = self.timeouts
        return {
            "team": {"id": self.team, "name": self.name}, "sample_games": n, "games": self.games,
            "factors": {side: {k: self.factors[side][k] / n for k in FACTOR_KEYS} for side in ("own", "rival")},
            "pace": self.pace / n, "players": players, "lineups": lineups,
            "zones": {"own": self.zones["own"], "conceded": self.zones["conceded"], "league": league_zones},
            "quarters": {str(p): {"for": f / n, "against": a / n, "margin": (f - a) / n} for p, (f, a) in self.quarters.items()},
            "edges": {e: {str(p): (f - a) / n for p, (f, a) in v.items()} for e, v in self.edges.items()},
            "timeouts": {"per_game": t["n"] / n, "first_half": t["first_half"] / n, "second_half": t["second_half"] / n,
                         "after_n": t["n"], "after_for": t["after_for"] / t["n"] if t["n"] else 0.0,
                         "after_against": t["after_against"] / t["n"] if t["n"] else 0.0},
            "origin": self._origin_result(league_origin),
            "alerts": alerts,
        }

    def _origin_result(self, league: Optional[Dict[str, float]]) -> Optional[Dict[str, Any]]:
        g, own, conceded = self.origin["games"], self.origin["own"], self.origin["conceded"]
        if not g or not league:
            return None
        own_row = {k: own[k] / g for k in (*ORIGIN_KEYS, "pts_bench")}
        own_row["bench_pct"] = own["pts_bench"] / own["pts"] * 100 if own["pts"] else 0.0
        return {"games": g, "own": own_row, "conceded": {k: conceded[k] / g for k in ORIGIN_KEYS}, "league": league}


def _sum_cells(target: Dict[str, Dict[str, int]], cells: Dict[str, Dict[str, int]]) -> None:
    for zone, cell in cells.items():
        total = target.setdefault(zone, {"a": 0, "m": 0, "pts": 0})
        for k in total:
            total[k] += cell[k]


def _replay(game: Dict[str, Any], acc: SeasonAccumulator, team: str, opp: str, collection: str,
            poll_s: float) -> Optional[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
    """The game as the tablet would have seen it, from ``team``'s side: its final snapshot and every alert raised."""
    package = acc.to_package(collection, "", team, opp, {"match": {"code": game_code(game)}}, FIXED_DATE)
    advice, engine, snap, alerts = AdviceEngine.from_package(package), LiveEngine(), None, []
    for poll in finished_game_polls(game, latency_s=0.0, poll_s=poll_s):
        snap = engine.update(poll.doc)
        alerts += [{"id": a.id, "category": a.category, "severity": a.severity, "message": a.message, "elapsed": snap["elapsed"]}
                   for a in advice.evaluate(snap)]
    return (snap, alerts) if snap is not None else None


LEAGUE, ALL = "liga", "todo"        # the scope of the league's games and the one that groups every competition; a cup (or any other) scope has its own name


def _start_key(game: Dict[str, Any]) -> datetime:
    return parse_starttime(game) or datetime.min


def scout_team_scopes(games: Iterable[Dict[str, Any]], team_id: str, collection: str = "FEB", poll_s: float = 30.0,
                      progress: Optional[Callable[[int], None]] = None, extra: Optional[Dict[str, Iterable[Dict[str, Any]]]] = None,
                      levels: Optional[Dict[str, int]] = None) -> Dict[str, Dict[str, Any]]:
    """The scouting data of ``team_id`` over its league and its other competitions, by scope (issue #638): ``liga``, one per key of ``extra`` and ``todo``.

    ``games`` is the league (every game of the competition, in date order): it feeds the season (the priors of the engine and the league's zones and
    origin figures) exactly as ``scout_team`` always did. ``extra`` maps a scope name (``copa``) to the games of the team in another competition: they are
    replayed from its side with what the league had taught the engine up to their date but they never feed the season, so a cup game against a team
    of another division does not move the league context. Each game is replayed once and counted in its own scope and in ``todo`` (which is only there
    when at least two scopes have games). ``levels`` (team id -> category) marks the games against a team of another category (``other_level``,
    ``level_gap``: the rival's category minus the team's). Raises ``ValueError`` when the team has no game at all.
    """
    team_id, extra = str(team_id), extra or {}
    if any(name in (LEAGUE, ALL) for name in extra):
        raise ValueError(f"Los nombres de alcance {LEAGUE!r} y {ALL!r} están reservados")
    scope_of: Dict[str, str] = {}
    others: List[Dict[str, Any]] = []
    for name, items in extra.items():
        for game in items:
            scope_of[game_code(game)] = name
            others.append(game)
    merged = heapq.merge(games, sorted(others, key=_start_key), key=_start_key) if others else games
    acc, league, aggs, done = SeasonAccumulator(), _League(), {}, 0
    for group in same_start_groups(merged):
        for game in group:       # all of them before any is learned: games that start together do not see each other
            scope = scope_of.get(game_code(game))                        # None: a game of the league
            ids = [str(t["id"]) for t in (game.get("HEADER") or {}).get("TEAM", [])]
            derived = _reliable_teams(game) if len(ids) == 2 else None
            if derived and scope is None:
                league.add(derived)
            if len(ids) == 2 and team_id in ids:
                opp = ids[1] if ids[0] == team_id else ids[0]
                replayed = _replay(game, acc, team_id, opp, collection, poll_s)
                if replayed:
                    note = _note(scope or LEAGUE, team_id, opp, levels) if (others or levels) else None
                    for name in {scope or LEAGUE, ALL}:
                        aggs.setdefault(name, _Agg(team_id)).add(game, opp, *replayed, derived=derived, note=note)
        for game in group:
            if game_code(game) not in scope_of:                          # only the league teaches the season
                acc.add_game(game)
        done += len(group)
        if progress:
            progress(done)
    if not aggs:
        raise ValueError(f"El equipo {team_id} no tiene partidos con jugada a jugada en la colección")
    if sum(1 for name in aggs if name != ALL) < 2:
        aggs.pop(ALL, None)                                              # the grouped scope would repeat the only one
    context = (acc.zone_league, league.result() if league.team_games else None)
    return {name: agg.result(*context) for name, agg in aggs.items()}


def _note(scope: str, team: str, opp: str, levels: Optional[Dict[str, int]]) -> Dict[str, Any]:
    """What a game says of its competition and, when both categories are known, whether the rival is of another one."""
    note: Dict[str, Any] = {"competition": scope}
    if levels and team in levels and opp in levels:
        note["level_gap"] = levels[opp] - levels[team]
        note["other_level"] = note["level_gap"] != 0
    return note


def scout_team(games: Iterable[Dict[str, Any]], team_id: str, collection: str = "FEB", poll_s: float = 30.0,
               progress: Optional[Callable[[int], None]] = None) -> Dict[str, Any]:
    """The scouting data of ``team_id`` over ``games`` (every game of the competition, in date order): the ``liga`` scope of ``scout_team_scopes``.

    Every game feeds the season (priors and league zones) but only those of the team are replayed. ``poll_s`` is the replay's
    step in seconds (30 is enough for the report and three times cheaper than the app's 10). ``progress(done)`` is called
    after each group of games that start together. Raises ``ValueError`` when the team has no game.
    """
    return scout_team_scopes(games, team_id, collection, poll_s, progress)[LEAGUE]
