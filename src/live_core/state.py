"""Live game state built incrementally from play-by-play events.

Everything (score, fouls, shooting, rebounds, minutes on court) is derived from the
events, so the engine does not depend on the live box score being updated. The first
five of each team are inferred: a player whose first event is not a substitution-in was
already on court (since tip-off in period 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional, Tuple

from . import clutch as clutch_mod
from .clock import period_length, period_start
from .events import Event
from .lineups import LineupTracker
from .live_possessions import PossessionCounters

STAT_KEYS = ("fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta", "orb", "drb", "tov", "tov_team",
             "stl", "ast", "blk", "pts")

PLAYER_STAT_KEYS = ("fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta", "orb", "drb", "tov", "stl", "ast", "blk")

_PLAYER_KINDS = {"sub_in", "sub_out", "fg2", "fg3", "ft", "rebound", "turnover", "steal",
                 "assist", "block", "foul"}
_TEAM_FOUL_TYPES = {"personal", "unsportsmanlike", "technical"}
# What a box score shows of a player and can change with one action (``last_stat``, #593), in the order the keys are reported.
_LAST_KEYS = ("pts",) + PLAYER_STAT_KEYS + ("pf", "on_court")

# Recovery credited to a player who stays on court through a break (game-seconds of the
# current stint; real minutes are never discounted). Halftime resets the stint completely.
QUARTER_BREAK_CREDIT_S = 60
# A timeout is a minute of rest for the players on court of BOTH teams (the clock stops for everybody): credited like the break, partly
# (issue #316; provisional, to be tuned with the evaluator).
TIMEOUT_CREDIT_S = 30
HALFTIME_PERIOD = 3


@dataclass
class _Player:
    name: str
    team_id: Optional[str]
    no: Optional[str] = None     # jersey number as text, when the box score of the document has it (#597)
    on_court: bool = False
    stint_start: int = 0
    closed: int = 0
    pf: int = 0
    pf_by_period: Dict[int, int] = field(default_factory=dict)
    unsports: int = 0   # unsportsmanlike fouls (FIBA: disqualified with two, or with one and a technical)
    techs: int = 0      # technical fouls of the player
    pts: int = 0
    credit: int = 0  # rest credited to the current stint (see QUARTER_BREAK_CREDIT_S)
    stints_done: int = 0  # finished stints and their rest-adjusted total length (for baselines)
    stint_sum: int = 0
    stats: Dict[str, int] = field(default_factory=lambda: {k: 0 for k in PLAYER_STAT_KEYS})
    pm: int = 0         # plus/minus: his team's points minus the rival's while he is on court (see lineups.py)
    stint_pm: int = 0   # the same since he came in
    clutch: Dict[str, int] = field(default_factory=clutch_mod.empty)   # what he does in a close finish (see clutch.py)
    q4: Dict[str, int] = field(default_factory=clutch_mod.empty)       # and in the whole 4th period (the fallback)


@dataclass
class _Team:
    name: str
    fouls_by_period: Dict[int, int] = field(default_factory=dict)
    fouls_game: int = 0
    timeouts: list = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=lambda: {k: 0 for k in STAT_KEYS})


class LiveGame:
    def __init__(self, teams: Iterable[Tuple[str, str]], roster: Optional[Dict[str, Tuple[str, str]]] = None, numbers: Optional[Dict[str, str]] = None):
        """``teams``: (id, name) pairs. ``roster``: player id -> (name, team id). ``numbers``: player id -> jersey number (text), when the box score has them."""
        self.teams: Dict[str, _Team] = {tid: _Team(name) for tid, name in teams}
        self.score: Dict[str, int] = {tid: 0 for tid in self.teams}
        self.players: Dict[str, _Player] = {
            pid: _Player(name, team_id, no=(numbers or {}).get(pid)) for pid, (name, team_id) in (roster or {}).items()
        }
        self.period = 1
        self.remaining = 600
        self.elapsed = 0
        self.last_num = 0
        self._licenses: Dict[str, str] = {}      # idLicense -> player id, from every line that names both (a foul only says the licence of who suffers it)
        self._drawn: Dict[str, int] = {}         # licence -> fouls suffered
        self._seq = 0
        self.last_stat: Optional[Dict[str, Any]] = None     # the last action that changed a player's box score (the tab highlights it, #593)
        self.last_event: Optional[Dict[str, Any]] = None   # {kind, elapsed, text, period, remaining, team_id} of the last line applied (lineup_settle.py, #413; the app shows the text, #490)
        self._last_miss_team: Optional[str] = None
        self.ball: Optional[Dict[str, Any]] = None        # who has the ball now: {team_id, since, why}; an indicator for the scoreboard (#497)
        self._in_clutch = False   # is the event being applied inside the clutch window (margin before it)?
        self.lineups = LineupTracker(list(self.teams))
        self.possessions = PossessionCounters(list(self.teams))   # exact possessions and points by origin (#357)
        self._rested_through = 1  # last period whose opening break has been credited
        # Chronological [elapsed, team_id, kind, value, player_id] (player None when the event has none):
        # pts (points of a made shot), fg2/fg3/ft (an attempt: 1 made, 0 missed), tov, orb, stl, timeout.
        self.log: list = []

    # -- event application -------------------------------------------------------

    def _margin(self) -> int:
        """Score margin between the two teams right now (a huge one if the game does not have two teams)."""
        scores = list(self.score.values())
        return abs(scores[0] - scores[1]) if len(scores) == 2 else 10 ** 6

    def _tick(self, now: int) -> None:
        """Credit the game-seconds since the last clock to the players on court: in the 4th period, and in the clutch window
        while the margin (as it was) is close. The window can open inside the interval, so only its overlap counts."""
        before = self.elapsed
        if now <= before:
            return
        self.lineups.tick(now - before)
        q4_start = period_start(clutch_mod.LAST_REGULATION_PERIOD)
        q4_end = q4_start + period_length(clutch_mod.LAST_REGULATION_PERIOD)
        q4 = max(0, min(now, q4_end) - max(before, q4_start))
        window = max(0, now - max(before, clutch_mod.window_start(self.period))) if self._margin() <= clutch_mod.in_window_margin() else 0
        if not (q4 or window):
            return
        for player in self.players.values():
            if player.on_court:
                player.q4["sec"] += q4
                player.clutch["sec"] += window

    def _clutch_bump(self, ev: Event, player: Optional[_Player], **amounts: int) -> None:
        """Add to the player's 4th-period totals and, if the event is inside the window, to his clutch totals."""
        if player is None or ev.period != clutch_mod.LAST_REGULATION_PERIOD and not self._in_clutch:
            return
        for bucket, applies in ((player.q4, ev.period == clutch_mod.LAST_REGULATION_PERIOD), (player.clutch, self._in_clutch)):
            if applies:
                for key, value in amounts.items():
                    bucket[key] += value

    def apply(self, ev: Event) -> None:
        self._enter_period(ev.period)
        self._tick(ev.elapsed)
        self._in_clutch = clutch_mod.in_window(ev.period, ev.elapsed, self._margin())   # the margin BEFORE the event
        self.period, self.remaining, self.elapsed, self.last_num = ev.period, ev.remaining, ev.elapsed, ev.num
        self.last_event = {"kind": ev.kind, "elapsed": ev.elapsed, "text": ev.text, "period": ev.period, "remaining": ev.remaining, "team_id": ev.team_id}
        self._move_ball(ev)
        player = self._player_for(ev)
        team = self.teams.get(ev.team_id) if ev.team_id else None
        if ev.player_id and ev.license:
            self._licenses[ev.license] = ev.player_id
        before = self._box(player)

        handler = getattr(self, f"_on_{ev.kind}", None)
        if handler:
            handler(ev, player, team)
        self._note_last_stat(ev, player, before)
        self.lineups.refresh(self.players, ev.elapsed)
        self.possessions.feed(ev)

    @staticmethod
    def _box(player: Optional[_Player]) -> Optional[Dict[str, Any]]:
        """What a box score shows of a player right now (to see afterwards what one action changed)."""
        return None if player is None else {**player.stats, "pts": player.pts, "pf": player.pf, "on_court": player.on_court}

    def _note_last_stat(self, ev: Event, player: Optional[_Player], before: Optional[Dict[str, Any]]) -> None:
        """Remember the action if it changed a box score: who, which columns and, for a foul, who drew it."""
        keys = [k for k in _LAST_KEYS if before is not None and self._box(player)[k] != before[k]]
        also = []
        if ev.kind == "foul" and ev.fouled and self._licenses.get(ev.fouled) in self.players:
            drawn = self.players[self._licenses[ev.fouled]]
            also.append({"player_id": self._licenses[ev.fouled], "team_id": drawn.team_id, "keys": ["fd"]})
        if keys:
            self._seq += 1
            self.last_stat = {"seq": self._seq, "player_id": ev.player_id, "team_id": ev.team_id, "keys": keys, "also": also}

    def _other(self, team_id: Optional[str]) -> Optional[str]:
        others = [t for t in self.teams if t != team_id]
        return others[0] if len(self.teams) == 2 and team_id in self.teams and len(others) == 1 else None

    def _move_ball(self, ev: Event) -> None:
        """Who has the ball after ``ev`` (an indicator read from the last events, not the exact possessions of ``possessions.py``): the rival after a made
        basket or a turnover, nobody after a miss until the rebound, the rebounder or the stealer, the shooter during free throws; nothing at a period boundary."""
        team, kind = ev.team_id, ev.kind
        if len(self.teams) != 2:
            return
        owner = why = None
        if kind in ("period_start", "period_end"):
            self.ball = None
            return
        if kind in ("fg2", "fg3") and ev.made:
            owner, why = self._other(team), "made_basket"
        elif kind in ("fg2", "fg3"):
            owner, why = None, "miss"
        elif kind == "ft":
            owner, why = team, "free_throw"
        elif kind == "turnover":
            owner, why = self._other(team), "turnover"
        elif kind in ("rebound", "steal"):
            owner, why = team, kind
        else:
            return          # fouls, substitutions, timeouts, assists...: the ball does not change hands
        if kind != "ft" or team is not None:
            self.ball = {"team_id": owner, "since": ev.elapsed, "why": why}

    def _player_for(self, ev: Event) -> Optional[_Player]:
        if not ev.player_id or ev.kind not in _PLAYER_KINDS:
            return None
        player = self.players.get(ev.player_id)
        if player is None:
            player = self.players[ev.player_id] = _Player(ev.name or ev.player_id, ev.team_id)
        elif ev.name and player.name == ev.player_id:
            player.name = ev.name
        if player.team_id is None:
            player.team_id = ev.team_id
        if not player.on_court and ev.kind != "sub_in" and player.closed == 0 and player.stint_start == 0:
            # First sighting through something other than "enters": already on court.
            player.on_court = True
            player.stint_start = 0 if ev.period == 1 else ev.elapsed
            if ev.period == 1:
                # on court since the tip-off, so the margin of his team so far is his plus/minus (the five of the start are not in the feed, #593)
                other = self._other(ev.team_id)
                player.pm = player.stint_pm = self.score.get(ev.team_id, 0) - (self.score.get(other, 0) if other else 0)
        return player

    def _enter_period(self, period: int) -> None:
        """Credit the break before ``period`` to players who stay on court through it."""
        while self._rested_through < period:
            self._rested_through += 1
            opening = self._rested_through
            for player in self.players.values():
                if not player.on_court:
                    continue
                if opening == HALFTIME_PERIOD:
                    player.credit = max(0, period_start(HALFTIME_PERIOD) - player.stint_start)
                else:
                    player.credit += QUARTER_BREAK_CREDIT_S

    def _on_sub_in(self, ev: Event, player: Optional[_Player], team) -> None:
        if player and not player.on_court:
            player.on_court, player.stint_start, player.credit, player.stint_pm = True, ev.elapsed, 0, 0

    def _on_sub_out(self, ev: Event, player: Optional[_Player], team) -> None:
        if player and player.on_court:
            player.closed += max(0, ev.elapsed - player.stint_start)
            player.stints_done += 1
            player.stint_sum += max(0, ev.elapsed - player.stint_start - player.credit)
            player.on_court, player.credit = False, 0

    def _shot(self, ev: Event, player: Optional[_Player], team: Optional[_Team], made_key: str, att_key: str) -> None:
        if team is None:
            return
        team.stats[att_key] += 1
        if player:
            player.stats[att_key] += 1
        if ev.kind == "ft":
            self._clutch_bump(ev, player, fta=1, ftm=1 if ev.made else 0, pts=ev.points if ev.made else 0)
        else:
            self._clutch_bump(ev, player, fga=1, pts=ev.points if ev.made else 0)
        self._log(ev, ev.kind, 1 if ev.made else 0)
        if ev.made:
            team.stats[made_key] += 1
            team.stats["pts"] += ev.points
            self.score[ev.team_id] += ev.points
            self.lineups.points(self.players, ev.team_id, ev.points)
            self._log(ev, "pts", ev.points)
            if player:
                player.pts += ev.points
                player.stats[made_key] += 1
            if ev.kind != "ft":
                self._last_miss_team = None
        else:
            self._last_miss_team = ev.team_id

    def _on_fg2(self, ev, player, team):
        self._shot(ev, player, team, "fg2m", "fg2a")

    def _on_fg3(self, ev, player, team):
        self._shot(ev, player, team, "fg3m", "fg3a")

    def _on_ft(self, ev, player, team):
        self._shot(ev, player, team, "ftm", "fta")

    def _on_rebound(self, ev, player, team):
        if team is None:
            return
        offensive = self._last_miss_team == ev.team_id
        key = "orb" if offensive else "drb"
        team.stats[key] += 1
        if player:
            player.stats[key] += 1
        if offensive:
            self._log(ev, "orb", 1)
        self._last_miss_team = None

    def _log(self, ev: Event, kind: str, value: int) -> None:
        self.log.append([ev.elapsed, ev.team_id, kind, value, ev.player_id or None])

    def _count(self, key: str, team: Optional[_Team], player: Optional[_Player] = None) -> None:
        if team is not None:
            team.stats[key] += 1
        if player is not None and key in player.stats:
            player.stats[key] += 1

    def _on_turnover(self, ev, player, team):
        # FEB logs team turnovers ("Equipo: PERDIDA") without a player; the official
        # box-score TO column excludes them, so keep them apart (possessions add both).
        self._count("tov" if ev.player_id else "tov_team", team, player)
        if ev.player_id:
            self._clutch_bump(ev, player, tov=1)
        if team is not None:
            self._log(ev, "tov", 1)

    def _on_steal(self, ev, player, team):
        self._count("stl", team, player)
        if team is not None:
            self._log(ev, "stl", 1)

    def _on_assist(self, ev, player, team):
        self._count("ast", team, player)

    def _on_block(self, ev, player, team):
        self._count("blk", team, player)

    def _on_timeout(self, ev, player, team):
        if team is not None:
            team.timeouts.append(ev.elapsed)
            self.log.append([ev.elapsed, ev.team_id, "timeout", 1, None])  # a timeout never has a player
            for on_court in self.players.values():
                if on_court.on_court:
                    on_court.credit += TIMEOUT_CREDIT_S

    def _on_foul(self, ev: Event, player: Optional[_Player], team: Optional[_Team]) -> None:
        if ev.fouled:
            self._drawn[ev.fouled] = self._drawn.get(ev.fouled, 0) + 1
        if player:
            player.pf = ev.pf_count if ev.pf_count is not None else player.pf + 1
            player.pf_by_period[ev.period] = player.pf_by_period.get(ev.period, 0) + 1
            if ev.foul_type == "unsportsmanlike":
                player.unsports += 1
            elif ev.foul_type == "technical":
                player.techs += 1
        if team is not None and ev.foul_type in _TEAM_FOUL_TYPES:
            team.fouls_by_period[ev.period] = team.fouls_by_period.get(ev.period, 0) + 1
            team.fouls_game += 1

    def set_clock(self, period: int, remaining: int) -> None:
        """Advance the clock from the live header (never moves backwards)."""
        from .clock import elapsed_seconds

        elapsed = elapsed_seconds(period, remaining)
        if elapsed >= self.elapsed:
            self._enter_period(period)
            self._tick(elapsed)
            self.period, self.remaining, self.elapsed = period, remaining, elapsed

    # -- output -----------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """Plain JSON-serialisable dict (the Pyodide <-> JS boundary)."""
        now = self.elapsed
        players = {}
        drawn: Dict[str, int] = {}
        for licence, count in self._drawn.items():       # resolved here, not when the foul is read: the fouled player may show up in a later line
            if licence in self._licenses:
                drawn[self._licenses[licence]] = drawn.get(self._licenses[licence], 0) + count
        for pid, p in self.players.items():
            stint = max(0, now - p.stint_start - p.credit) if p.on_court else 0
            players[pid] = {
                "name": p.name, "team_id": p.team_id, "no": p.no, "on_court": p.on_court,
                "minutes": p.closed + (max(0, now - p.stint_start) if p.on_court else 0),
                "stint": stint, "pf": p.pf, "pts": p.pts, "unsportsmanlike": p.unsports, "technical": p.techs,
                "stints_done": p.stints_done, "stint_sum": p.stint_sum, "stats": dict(p.stats),
                "pf_by_period": {str(k): v for k, v in sorted(p.pf_by_period.items())},
                "clutch": dict(p.clutch), "q4": dict(p.q4), "pm": p.pm, "stint_pm": p.stint_pm, "fd": drawn.get(pid, 0),
            }
        teams = {
            tid: {
                "name": t.name, "fouls_game": t.fouls_game, "timeouts": list(t.timeouts),
                "fouls_by_period": {str(k): v for k, v in sorted(t.fouls_by_period.items())},
                "stats": dict(t.stats),
            }
            for tid, t in self.teams.items()
        }
        return {
            "period": self.period, "remaining": self.remaining, "elapsed": self.elapsed,
            "last_num": self.last_num, "last_event": dict(self.last_event) if self.last_event else None, "last_stat": dict(self.last_stat) if self.last_stat else None, "score": dict(self.score), "teams": teams, "players": players,
            "log": [list(e) for e in self.log],
            "possessions": self.possessions.snapshot(),
            "ball": dict(self.ball) if self.ball else None,
            # the first team of FEB's header is the local one; the session JSON sorts keys, so say it explicitly
            "home_id": next(iter(self.teams), None),
            **self.lineups.snapshot(),
        }
