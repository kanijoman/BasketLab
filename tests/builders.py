"""Shared builders of the live-engine tests (issue #543).

* ``Match``: plays events through the REAL state machine (``LiveGame``) and hands back the snapshot, so a test can only be in a state the engine can reach. A hand-written
  snapshot dict (``snap``) can describe impossible states (a timeout between two periods, a rebound with nothing missed); the builder refuses them. Use it for new tests and when
  a test is touched; ``snap`` stays for tests that need to set exactly one field of a snapshot.
* The helpers that more than 40 test modules used to import from ``test_live_core_advice`` (``OWN``, ``RIVAL``, ``snap``, ``_player``, ``engine``…): tests do not import from
  other tests any more.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from src.live_core.advice import AdviceEngine
from src.live_core.clock import clock_text, period_and_remaining, period_length, period_start
from src.live_core.events import Event
from src.live_core.state import LiveGame

OWN, RIVAL = "T1", "T2"

BASE = {"p1": {"avg_stint": 360, "avg_min": 1500, "p90_min": 2000}}


# --- snapshots written by hand (kept for the tests that set one field) ------------------------------------------------------------------

def _player(name, team, pf=0, on_court=True, minutes=0, stint=0, pf_by_period=None):
    return {"name": name, "team_id": team, "on_court": on_court, "minutes": minutes,
            "stint": stint, "pf": pf, "pts": 0, "pf_by_period": pf_by_period or {}}


def _with_a_valid_five(players):
    """A snapshot that names some own players on court describes a game whose own five is valid (the engine does not say who is tired of a team with 4 or 6 on court, #1124): the
    missing ones are fresh players of the own team. One that names none, or already has five or more, is left as it is."""
    players = dict(players or {})
    own = [p for p in players.values() if p["team_id"] == OWN and p["on_court"]]
    if own and len(own) < 5:
        for i in range(5 - len(own)):
            players[f"_fresh{i}"] = _player(f"Fresh{i}", OWN, minutes=0, stint=0)
    return players


def snap(elapsed=600, period=1, players=None, fouls_by_period=None, log=None):
    fouls_by_period = fouls_by_period or {}
    players = _with_a_valid_five(players)
    return {
        "period": period, "remaining": 300, "elapsed": elapsed, "last_num": 1,
        "score": {OWN: 0, RIVAL: 0},
        "teams": {tid: {"name": tid, "fouls_game": sum(fouls_by_period.get(tid, {}).values()),
                        "timeouts": [], "fouls_by_period": fouls_by_period.get(tid, {}),
                        "stats": {}} for tid in (OWN, RIVAL)},
        "players": players, "log": log or [],
    }


def pad_to_score(log, score):
    """The log of a snapshot whose header says ``score`` (team -> points): a log that holds fewer points than the header is a play-by-play that is behind it, a state the engine
    waits in (score_settle). A fixture that only wants a header score gets the missing points as one early basket per team, so it describes a state of a settled game."""
    padding = []
    for team, header in (score or {}).items():
        have = sum(e[3] for e in log if e[1] == team and e[2] == "pts")
        if header > have:
            padding.append([0, team, "pts", header - have, None])
    return padding + list(log)


def engine(**kw):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, **kw)


def ids(advices):
    return [a.id for a in advices]


def _pts(t, team, v):
    return [t, team, "pts", v]


def _stats(**kw):
    base = dict(fg2m=20, fg2a=40, fg3m=6, fg3a=20, ftm=10, fta=14, orb=8, drb=25,
                tov=10, tov_team=0, stl=5, ast=12, blk=2, pts=0)
    base.update(kw)
    return base


def ff_snap(own, rival, elapsed=1200):
    s = snap(elapsed=elapsed)
    s["teams"][OWN]["stats"], s["teams"][RIVAL]["stats"] = own, rival
    s["score"] = {OWN: 40, RIVAL: 40}
    return s


# --- the match builder ----------------------------------------------------------------------------------------------------------------

class Match:
    """A match played event by event. Every method takes ``at`` (game second) and returns the match, so a scenario reads as it happened::

        Match().score(RIVAL, 3, at=100).turnover(OWN, at=130).timeout(OWN, at=140).evaluate()
    """

    def __init__(self, own: str = OWN, rival: str = RIVAL) -> None:
        self.own, self.rival = own, rival
        self.game = LiveGame([(own, own), (rival, rival)], {})
        self._num = 0
        self._now = 0
        self._miss_pending = False
        self._fouls: Dict[str, int] = {}
        self._late = False
        self.events: List[Event] = []      # in the order they were logged: what ``document()`` writes

    # -- events ----------------------------------------------------------------------------------------------------------------------

    def _event(self, kind: str, team: Optional[str], at: int, **kw: Any) -> "Match":
        if team is not None and team not in (self.own, self.rival):
            raise ValueError(f"equipo desconocido: {team!r} (los de este partido son {self.own} y {self.rival})")
        if at < self._now and not self._late:
            raise ValueError(f"el tiempo no puede ir hacia atrás: {at} s después de {self._now} s (usa ``late()`` para una línea registrada tarde)")
        period, remaining = period_and_remaining(at)
        self._num += 1
        self._now = max(self._now, at)
        name = kw.pop("name", kw.get("player_id"))
        if kw.get("player_id"):
            kw.setdefault("license", f"L-{kw['player_id']}")        # what FEB writes in ``idLicense``: how the engine knows who was fouled
        event = Event(num=self._num, period=period, remaining=remaining, elapsed=at, kind=kind, team_id=team, name=name, **kw)
        self.events.append(event)
        self.game.apply(event)
        return self

    def late(self, call: str, *args: Any, **kw: Any) -> "Match":
        """An action logged LATE, as FEB does: it gets the next line number but a clock earlier than the lines before it. ``late("turnover", RIVAL, at=300)``."""
        self._late = True
        try:
            return getattr(self, call)(*args, **kw)
        finally:
            self._late = False

    def score(self, team: str, points: int, at: int, player: Optional[str] = None) -> "Match":
        """A made basket (2 or 3 points) or a free throw (1)."""
        if points not in (1, 2, 3):
            raise ValueError(f"una canasta vale 1, 2 o 3 puntos, no {points}")
        kind = {1: "ft", 2: "fg2", 3: "fg3"}[points]
        return self._event(kind, team, at, made=True, points=points, player_id=player or ("p1" if team == self.own else "r1"))

    def miss(self, team: str, at: int, kind: str = "fg2", player: Optional[str] = None) -> "Match":
        if kind not in ("fg2", "fg3", "ft"):
            raise ValueError(f"un tiro es fg2, fg3 o ft, no {kind!r}")
        self._event(kind, team, at, made=False, player_id=player or ("p1" if team == self.own else "r1"))
        self._miss_pending = True
        return self

    def rebound(self, team: str, at: int, player: Optional[str] = None) -> "Match":
        if not self._miss_pending:
            raise ValueError("un rebote necesita un tiro fallado antes")
        self._miss_pending = False
        return self._event("rebound", team, at, player_id=player or ("p1" if team == self.own else "r1"))

    def turnover(self, team: str, at: int, player: Optional[str] = None) -> "Match":
        return self._event("turnover", team, at, player_id=player or ("p1" if team == self.own else "r1"))

    def steal(self, team: str, at: int, player: Optional[str] = None) -> "Match":
        return self._event("steal", team, at, player_id=player or ("p1" if team == self.own else "r1"))

    def foul(self, team: str, player: str, at: int, drawn_by: Optional[str] = None, kind: str = "personal") -> "Match":
        """A foul of ``player`` (``kind``: personal, technical, unsportsmanlike); ``drawn_by`` is who suffers it (the receiver FEB writes in the line)."""
        if kind not in ("personal", "technical", "unsportsmanlike"):
            raise ValueError(f"una falta es personal, technical o unsportsmanlike, no {kind!r}")
        self._fouls[player] = self._fouls.get(player, 0) + 1
        return self._event("foul", team, at, player_id=player, foul_type=kind, pf_count=self._fouls[player], fouled=f"L-{drawn_by}" if drawn_by else None)

    def assist(self, team: str, at: int, player: Optional[str] = None) -> "Match":
        return self._event("assist", team, at, player_id=player or ("p1" if team == self.own else "r1"))

    def block(self, team: str, at: int, player: Optional[str] = None) -> "Match":
        return self._event("block", team, at, player_id=player or ("p1" if team == self.own else "r1"))

    def timeout(self, team: str, at: int) -> "Match":
        return self._event("timeout", team, at)

    def period_end(self, period: int) -> "Match":
        """The end of a period (clock at 0:00), as the feed writes it; the summary of the quarter is said then."""
        end = period_start(period) + period_length(period)
        if end < self._now:
            raise ValueError(f"el periodo {period} ya había terminado: el reloj está en {self._now} s")
        self._num += 1
        self._now = end
        self.game.apply(Event(num=self._num, period=period, remaining=0, elapsed=end, kind="period_end"))
        return self

    def lineup(self, team: str, players: Iterable[str], at: int = 0) -> "Match":
        """The five players of a team enter the court."""
        for pid in players:
            self._event("sub_in", team, at, player_id=pid)
        return self

    def substitution(self, team: str, out: str, into: str, at: int) -> "Match":
        self._event("sub_out", team, at, player_id=out)
        return self._event("sub_in", team, at, player_id=into)

    # -- reading the state -----------------------------------------------------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        return self.game.snapshot()

    def engine(self, **kw: Any) -> AdviceEngine:
        return AdviceEngine(own_team_id=self.own, rival_team_id=self.rival, **kw)

    def evaluate(self, **kw: Any) -> List[Any]:
        """The alerts of the real engine for the state now (a fresh engine: use ``engine()`` to keep its memory between evaluations)."""
        return self.engine(**kw).evaluate(self.snapshot())

    # -- the FEB document of the match ------------------------------------------------------------------------------------------------

    def document(self) -> Dict[str, Any]:
        """The match as FEB serves it: a document with the play-by-play lines (newest first, as the feed lists them) that ``LiveEngine`` and the sessions read."""
        players: Dict[str, str] = {}
        for ev in self.events:
            if ev.player_id and ev.team_id:
                players.setdefault(ev.player_id, ev.team_id)
        last = self.events[-1] if self.events else None
        return {
            "HEADER": {"TEAM": [{"id": self.own, "name": self.own}, {"id": self.rival, "name": self.rival}],
                       "quarter": last.period if last else 1, "time": clock_text(last.remaining) if last else "10:00"},
            "BOXSCORE": {"TEAM": [{"id": team, "PLAYER": [{"id": pid, "name": pid} for pid, owner in players.items() if owner == team]} for team in (self.own, self.rival)]},
            "PLAYBYPLAY": {"LINES": [_line(ev) for ev in reversed(self.events)]},
        }


_ACTIONS = {"fg2": "shoot", "fg3": "shoot", "ft": "fthrow", "rebound": "rebound", "turnover": "lose", "steal": "recovery", "assist": "assist", "block": "blockshot",
            "timeout": "timeout", "foul": "foul", "sub_in": "subst", "sub_out": "subst", "period_end": "period"}
_BODIES = {"rebound": "REBOTE (Rebotes: 1)", "turnover": "PÉRDIDA (Pérdidas: 1)", "steal": "ROBO (Robos: 1)", "assist": "ASISTENCIA (Asistencias: 1)",
           "block": "TAPÓN (Tapones: 1)", "timeout": "Tiempo muerto", "sub_in": "Entra a pista", "sub_out": "Sale de pista"}


def _line(ev: Event) -> Dict[str, Any]:
    """One play-by-play line (the text is what ``events.parse_line`` reads) of an event."""
    who = f"({ev.team_id}) {ev.name}: " if ev.name else ""
    if ev.kind in ("fg2", "fg3", "ft"):
        body = f"TIRO DE {ev.kind[-1] if ev.kind != 'ft' else 1} {'ANOTADO' if ev.made else 'FALLADO'}"
    elif ev.kind == "foul":
        body = f"FALTA {'Técnica' if ev.foul_type == 'technical' else ev.foul_type.capitalize()} (Faltas: {ev.pf_count or 1}. Faltas de equipo: 1)"
    elif ev.kind == "period_end":
        who, body = "", f"Fin del Cuarto {ev.period}"
    else:
        body = _BODIES[ev.kind]
    return {"num": str(ev.num), "quarter": str(ev.period), "time": clock_text(ev.remaining), "idTeam": ev.team_id, "idPlayer": ev.player_id, "idLicense": ev.license,
            "action": _ACTIONS[ev.kind], "text": who + body, "deleted": None, "logParam4": ev.fouled}
