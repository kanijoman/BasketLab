"""Live game state built incrementally from play-by-play events.

Everything (score, fouls, shooting, rebounds, minutes on court) is derived from the
events, so the engine does not depend on the live box score being updated. The first
five of each team are inferred: a player whose first event is not a substitution-in was
already on court (since tip-off in period 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional, Tuple

from .clock import period_start
from .events import Event

STAT_KEYS = ("fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta", "orb", "drb", "tov", "tov_team",
             "stl", "ast", "blk", "pts")

_PLAYER_KINDS = {"sub_in", "sub_out", "fg2", "fg3", "ft", "rebound", "turnover", "steal",
                 "assist", "block", "foul"}
_TEAM_FOUL_TYPES = {"personal", "unsportsmanlike", "technical"}

# Recovery credited to a player who stays on court through a break (game-seconds of the
# current stint; real minutes are never discounted). Halftime resets the stint completely.
QUARTER_BREAK_CREDIT_S = 60
HALFTIME_PERIOD = 3


@dataclass
class _Player:
    name: str
    team_id: Optional[str]
    on_court: bool = False
    stint_start: int = 0
    closed: int = 0
    pf: int = 0
    pf_by_period: Dict[int, int] = field(default_factory=dict)
    pts: int = 0
    credit: int = 0  # rest credited to the current stint (see QUARTER_BREAK_CREDIT_S)


@dataclass
class _Team:
    name: str
    fouls_by_period: Dict[int, int] = field(default_factory=dict)
    fouls_game: int = 0
    timeouts: list = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=lambda: {k: 0 for k in STAT_KEYS})


class LiveGame:
    def __init__(self, teams: Iterable[Tuple[str, str]], roster: Optional[Dict[str, Tuple[str, str]]] = None):
        """``teams``: (id, name) pairs. ``roster``: player id -> (name, team id)."""
        self.teams: Dict[str, _Team] = {tid: _Team(name) for tid, name in teams}
        self.score: Dict[str, int] = {tid: 0 for tid in self.teams}
        self.players: Dict[str, _Player] = {
            pid: _Player(name, team_id) for pid, (name, team_id) in (roster or {}).items()
        }
        self.period = 1
        self.remaining = 600
        self.elapsed = 0
        self.last_num = 0
        self._last_miss_team: Optional[str] = None
        self._rested_through = 1  # last period whose opening break has been credited
        # Chronological [elapsed, team_id, kind, value] for runs and streaks: pts, tov, orb.
        self.log: list = []

    # -- event application -------------------------------------------------------

    def apply(self, ev: Event) -> None:
        self._enter_period(ev.period)
        self.period, self.remaining, self.elapsed, self.last_num = ev.period, ev.remaining, ev.elapsed, ev.num
        player = self._player_for(ev)
        team = self.teams.get(ev.team_id) if ev.team_id else None

        handler = getattr(self, f"_on_{ev.kind}", None)
        if handler:
            handler(ev, player, team)

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
            player.on_court, player.stint_start, player.credit = True, ev.elapsed, 0

    def _on_sub_out(self, ev: Event, player: Optional[_Player], team) -> None:
        if player and player.on_court:
            player.closed += max(0, ev.elapsed - player.stint_start)
            player.on_court = False

    def _shot(self, ev: Event, player: Optional[_Player], team: Optional[_Team], made_key: str, att_key: str) -> None:
        if team is None:
            return
        team.stats[att_key] += 1
        if ev.made:
            team.stats[made_key] += 1
            team.stats["pts"] += ev.points
            self.score[ev.team_id] += ev.points
            self.log.append([ev.elapsed, ev.team_id, "pts", ev.points])
            if player:
                player.pts += ev.points
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
        team.stats["orb" if offensive else "drb"] += 1
        if offensive:
            self.log.append([ev.elapsed, ev.team_id, "orb", 1])
        self._last_miss_team = None

    def _count(self, key: str, team: Optional[_Team]) -> None:
        if team is not None:
            team.stats[key] += 1

    def _on_turnover(self, ev, player, team):
        # FEB logs team turnovers ("Equipo: PERDIDA") without a player; the official
        # box-score TO column excludes them, so keep them apart (possessions add both).
        self._count("tov" if ev.player_id else "tov_team", team)
        if team is not None:
            self.log.append([ev.elapsed, ev.team_id, "tov", 1])

    def _on_steal(self, ev, player, team):
        self._count("stl", team)

    def _on_assist(self, ev, player, team):
        self._count("ast", team)

    def _on_block(self, ev, player, team):
        self._count("blk", team)

    def _on_timeout(self, ev, player, team):
        if team is not None:
            team.timeouts.append(ev.elapsed)

    def _on_foul(self, ev: Event, player: Optional[_Player], team: Optional[_Team]) -> None:
        if player:
            player.pf = ev.pf_count if ev.pf_count is not None else player.pf + 1
            player.pf_by_period[ev.period] = player.pf_by_period.get(ev.period, 0) + 1
        if team is not None and ev.foul_type in _TEAM_FOUL_TYPES:
            team.fouls_by_period[ev.period] = team.fouls_by_period.get(ev.period, 0) + 1
            team.fouls_game += 1

    def set_clock(self, period: int, remaining: int) -> None:
        """Advance the clock from the live header (never moves backwards)."""
        from .clock import elapsed_seconds

        elapsed = elapsed_seconds(period, remaining)
        if elapsed >= self.elapsed:
            self._enter_period(period)
            self.period, self.remaining, self.elapsed = period, remaining, elapsed

    # -- output -----------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """Plain JSON-serialisable dict (the Pyodide <-> JS boundary)."""
        now = self.elapsed
        players = {}
        for pid, p in self.players.items():
            stint = max(0, now - p.stint_start - p.credit) if p.on_court else 0
            players[pid] = {
                "name": p.name, "team_id": p.team_id, "on_court": p.on_court,
                "minutes": p.closed + (max(0, now - p.stint_start) if p.on_court else 0), "stint": stint, "pf": p.pf, "pts": p.pts,
                "pf_by_period": {str(k): v for k, v in sorted(p.pf_by_period.items())},
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
            "last_num": self.last_num, "score": dict(self.score), "teams": teams, "players": players,
            "log": [list(e) for e in self.log],
        }
