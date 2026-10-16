"""Possession tracker: who has the ball and when a possession ends, from normalised play-by-play events.

Standard library only (it also runs in the app). One state machine for every consumer: batch (``track``) and
incremental (``PossessionTracker.feed``). Rules:

* A possession ends with a made basket (an and-one ends with its free throw), the last free throw of a trip, a
  turnover, or a missed shot / last free throw whose rebound goes to the rival. An offensive rebound keeps it.
* The rebound is offensive when the rebounding team is the one that missed ("same team as the last miss"), team
  rebounds included. This is the real-game meaning; the 2026-27 official PDF labels some of them the other way.
* Free throws of a technical foul are not a possession and never change who has the ball. An unsportsmanlike trip
  is a possession and the shooter's team keeps the ball afterwards (a consecutive possession of the same team).
* The feed has errors. A team acting without the ball closes the rival's possession as ``inferred`` (not counted)
  and flags the gap. A rebound credited to the rival, followed by an action of the team that missed with nothing
  from the rival in between, is reinterpreted as an offensive rebound for the possession only (``repaired``).

Some decisions need the next event (and-one, last free throw, repaired rebound): the possession is closed when
that event arrives (or at ``finish``), so closed possessions are returned a few events late.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .clock import period_length, period_start
from .events import Event
from .possession_types import Possession, PossessionQuality, level_for_breaks

__all__ = ["Possession", "PossessionQuality", "PossessionTracker", "level_for_breaks", "track"]

MAX_AND1_GAP_S = 15
_ACTIONS = frozenset(("fg2", "fg3", "ft", "turnover", "rebound"))
_NEXT_ORIGIN = {"made_fg": "made_basket", "ft_made": "made_basket", "turnover": "turnover", "missed_shot": "def_rebound",
                "trip": "trip"}


@dataclass
class _Hold:
    """A decision waiting for the next event: kind is "fg" (and-one?), "ft" (last of the trip?) or "dr" (repair?)."""
    kind: str
    team: str
    ev: Event
    trip: Optional[str] = None
    team_reb: bool = False


class PossessionTracker:
    def __init__(self, team_ids: Sequence[str]) -> None:
        ids = [str(t) for t in team_ids]
        if len(ids) != 2:
            raise ValueError("a game has exactly two teams")
        self._opp = {ids[0]: ids[1], ids[1]: ids[0]}
        self.technical_points: Counter = Counter()
        self._counted: Counter = Counter()
        self._breaks = self._breaks_raw = 0
        self._last_end: Optional[Tuple[str, int, str]] = None       # (team, period, outcome) of the last counted end
        self._last_end_raw: Optional[Tuple[str, int, str]] = None   # same, before repairing rebounds
        self._repaired = self._inferred = self._implicit_off = self._implicit_def = self._technical_ft = 0
        self._cur: Optional[Possession] = None
        self._period: Optional[int] = None
        self._reset_period()

    def _reset_period(self) -> None:
        self._cur = None
        self._pending: Optional[str] = None             # team whose miss waits for its rebound
        self._hold: Optional[_Hold] = None
        self._foul_type: Optional[str] = None
        self._fouls_since: Set[Optional[str]] = set()
        self._timeouts: List[Tuple[str, int]] = []
        self._after_oreb = False
        self._steal_seen: Optional[Tuple[str, int]] = None
        self._last_turnover: Optional[Possession] = None
        self._last_elapsed = self._last_num = 0

    # -- public --------------------------------------------------------------------------------------------------

    def feed(self, ev: Event) -> List[Possession]:
        """Process one event (in clock order); returns the possessions it closed."""
        out: List[Possession] = []
        if ev.deleted:
            return out
        kind = ev.kind
        if kind in ("period_start", "period_end"):
            self._boundary(out)
            self._period = ev.period if kind == "period_start" else None
            return out
        if kind == "timeout":
            self._timeout(ev)
        elif kind == "foul":
            self._foul_type = ev.foul_type
            self._fouls_since.add(ev.foul_type)
        elif kind == "steal":
            self._steal(ev)
        elif kind in _ACTIONS and ev.team_id in self._opp:
            if self._period is not None and ev.period != self._period:
                self._boundary(out)       # a new period with no marker for the previous one
            self._period = ev.period
            self._act(out, ev)
        return out

    def finish(self) -> List[Possession]:
        out: List[Possession] = []
        self._boundary(out, to_period_end=False)
        return out

    def quality(self) -> PossessionQuality:
        counted = dict(self._counted)
        teams = list(self._opp)
        return PossessionQuality(
            counted=counted, breaks_raw=self._breaks_raw, breaks=self._breaks, repaired_rebounds=self._repaired,
            inferred=self._inferred, implicit_offensive=self._implicit_off, implicit_defensive=self._implicit_def,
            technical_ft=self._technical_ft, level=level_for_breaks(self._breaks_raw),
            difference=abs(counted.get(teams[0], 0) - counted.get(teams[1], 0)), technical_points=dict(self.technical_points))

    # -- events --------------------------------------------------------------------------------------------------

    def _act(self, out: List[Possession], ev: Event) -> None:
        self._last_elapsed, self._last_num = ev.elapsed, ev.num
        self._settle(out, ev)
        if ev.kind != "turnover":
            self._steal_seen = None
        if self._resolve_pending(out, ev):
            return
        if ev.kind == "rebound":
            self._orphan_rebound(out, ev)
        elif ev.kind == "turnover":
            self._turnover(out, ev)
        elif ev.kind == "ft":
            self._free_throw(out, ev)
        else:
            self._shot(out, ev)

    def _shot(self, out: List[Possession], ev: Event) -> None:
        self._own(out, ev)
        self._foul_type = None
        if ev.made:
            self._score(ev)
            self._hold, self._fouls_since = _Hold("fg", ev.team_id, ev), set()
        else:
            self._pending = ev.team_id

    def _free_throw(self, out: List[Possession], ev: Event) -> None:
        if self._foul_type == "technical":     # no possession, the ball goes back to whoever had it
            self._technical_ft += 1
            if ev.made:
                self.technical_points[ev.team_id] += ev.points
            return
        self._own(out, ev)
        if ev.made:
            self._score(ev)
        self._hold = _Hold("ft", ev.team_id, ev, trip=self._foul_type)

    def _turnover(self, out: List[Possession], ev: Event) -> None:
        self._own(out, ev)
        self._foul_type = None
        steal = self._steal_seen is not None and self._steal_seen[1] == ev.elapsed and self._steal_seen[0] != ev.team_id
        closed = self._end(out, "turnover", ev)
        if steal:
            closed.steal, self._cur.origin = True, "steal"
        self._steal_seen, self._last_turnover = None, closed

    def _steal(self, ev: Event) -> None:
        """The steal line comes before or after the turnover line of the rival, at the same clock."""
        last, cur = self._last_turnover, self._cur
        if (last is not None and cur is not None and last.end_elapsed == ev.elapsed and last.team_id != ev.team_id
                and cur.team_id == ev.team_id and cur.start_elapsed == ev.elapsed):
            last.steal, cur.origin = True, "steal"
        else:
            self._steal_seen = (ev.team_id, ev.elapsed)

    def _timeout(self, ev: Event) -> None:
        item = (ev.team_id, ev.elapsed)
        if self._hold is None and self._cur is not None:
            self._cur.timeouts += (item,)
        else:
            self._timeouts.append(item)       # it belongs to the possession that follows

    def _orphan_rebound(self, out: List[Possession], ev: Event) -> None:
        """A rebound with no recorded miss to attach to."""
        if self._cur is not None and self._cur.team_id == ev.team_id:
            self._cur.orebs += 1
            self._after_oreb = True
            return
        origin = "team_def_rebound" if ev.player_id is None else "def_rebound"
        self._close_inferred(out, ev)
        self._cur = self._new(ev.team_id, ev, origin, repaired=True)

    # -- rebounds and pending decisions ---------------------------------------------------------------------------

    def _resolve_pending(self, out: List[Possession], ev: Event) -> bool:
        """Use ``ev`` to settle a missed shot waiting for its rebound; True when the event was consumed."""
        pending, kind, team = self._pending, ev.kind, ev.team_id
        if pending is None or (kind == "ft" and self._foul_type == "technical"):
            return False
        if kind == "rebound":
            self._pending = None
            if team == pending:
                self._cur.orebs += 1
                self._after_oreb = True
            else:    # the possession is closed with the next event, in case the rebound was misattributed
                self._note_end(self._cur, outcome="missed_shot", actual=False)
                self._hold = _Hold("dr", pending, ev, team_reb=ev.player_id is None)
            return True
        if kind == "ft" and team == pending:     # shooting foul on the miss: the trip follows
            self._pending = None
        elif team == pending:                     # it acts again: it kept the ball
            self._pending, self._after_oreb = None, True
            self._implicit_off += 1
        else:                                     # the rival acts: it got the ball
            self._pending = None
            self._implicit_def += 1
            self._end(out, "missed_shot", ev)
        return False

    def _settle(self, out: List[Possession], ev: Optional[Event]) -> None:
        """Take the decision that was waiting for the next event (``None`` = no more events)."""
        hold, self._hold = self._hold, None
        if hold is None:
            return
        if hold.kind == "fg":
            if (ev is not None and ev.kind == "ft" and ev.team_id == hold.team and ev.period == hold.ev.period
                    and ev.elapsed - hold.ev.elapsed <= MAX_AND1_GAP_S
                    and not self._fouls_since & {"technical", "unsportsmanlike"}):
                return                                          # and-one: the free throw ends the possession
            self._end(out, "made_fg", hold.ev)
        elif hold.kind == "ft":
            if ev is not None and ev.kind == "ft" and ev.team_id == hold.team and ev.period == hold.ev.period:
                return                                          # the trip goes on
            self._foul_type = None
            if hold.trip == "unsportsmanlike":
                self._end(out, "trip", hold.ev, same_team=True)
            elif hold.ev.made:
                self._end(out, "ft_made", hold.ev)
            else:
                self._pending = hold.team                       # live ball after the last free throw
        elif (ev is not None and ev.team_id == hold.team and (ev.kind in ("fg2", "fg3", "turnover")
                                                              or (ev.kind == "ft" and self._foul_type != "technical"))):
            self._cur.repaired_orebs += 1                       # the rebound was credited to the wrong team
            self._cur.repaired = True
            self._after_oreb = True
            self._repaired += 1
        else:
            origin = "team_def_rebound" if hold.team_reb else "def_rebound"
            self._end(out, "missed_shot", hold.ev, origin=origin, raw=False)

    # -- possession bookkeeping -----------------------------------------------------------------------------------

    def _new(self, team: str, ev: Event, origin: str, start: Optional[int] = None, gap: bool = False,
             repaired: bool = False) -> Possession:
        elapsed = ev.elapsed if start is None else start
        poss = Possession(team_id=team, period=ev.period, start_elapsed=elapsed, end_elapsed=elapsed, start_num=ev.num,
                          end_num=ev.num, origin=origin, timeouts=tuple(self._timeouts), gap_before=gap, repaired=repaired)
        self._timeouts, self._after_oreb = [], False
        return poss

    def _own(self, out: List[Possession], ev: Event) -> None:
        """Make sure the team of ``ev`` has the ball; if the rival had it, its possession ended without an event."""
        cur = self._cur
        if cur is not None and cur.team_id == ev.team_id:
            return
        if cur is None:
            self._cur = self._new(ev.team_id, ev, "period_start", start=period_start(ev.period))
            return
        self._close_inferred(out, ev)
        self._inferred += 1
        self._cur = self._new(ev.team_id, ev, "unknown", gap=True)

    def _score(self, ev: Event) -> None:
        cur = self._cur
        cur.points += ev.points
        if ev.player_id:
            cur.points_by_player[ev.player_id] = cur.points_by_player.get(ev.player_id, 0) + ev.points
        if self._after_oreb:
            cur.second_chance_points += ev.points

    def _end(self, out: List[Possession], outcome: str, ev: Event, same_team: bool = False,
             origin: Optional[str] = None, raw: bool = True) -> Possession:
        """Close the current possession with an event of the feed and hand the ball over."""
        cur = self._cur
        cur.end_elapsed, cur.end_num, cur.outcome, cur.counted = ev.elapsed, ev.num, outcome, True
        out.append(cur)
        self._note_end(cur, actual=True, raw=raw)
        team = cur.team_id if same_team else self._opp[cur.team_id]
        self._cur = self._new(team, ev, origin or _NEXT_ORIGIN.get(outcome, "unknown"))
        return cur

    def _close_inferred(self, out: List[Possession], ev: Event) -> None:
        cur = self._cur
        if cur is None:
            return
        cur.end_elapsed, cur.end_num, cur.outcome, cur.counted, cur.repaired = ev.elapsed, ev.num, "inferred", False, True
        if cur.duration > 0 or cur.points:
            out.append(cur)
        self._cur = None

    def _boundary(self, out: List[Possession], to_period_end: bool = True) -> None:
        """End of a period: settle what is waiting, count a miss at the buzzer, close the partial possession.

        ``to_period_end``: the clock ran to the end of the period (a marker or a later period); False at ``finish``."""
        self._settle(out, None)
        cur = self._cur
        if cur is not None and self._pending is not None:
            cur.end_elapsed, cur.end_num, cur.outcome, cur.counted = self._last_elapsed, self._last_num, "missed_shot", True
            out.append(cur)
            self._note_end(cur, actual=True, raw=True)
        elif cur is not None:
            if to_period_end:
                cur.end_elapsed = period_start(cur.period) + period_length(cur.period)
            cur.outcome, cur.counted = "period_end", False
            if cur.duration > 0 or cur.points:
                out.append(cur)
        self._reset_period()

    def _note_end(self, poss: Possession, outcome: Optional[str] = None, actual: bool = True, raw: bool = True) -> None:
        """Count a possession end and any alternation break (same team twice in a row inside a period)."""
        outcome = outcome or poss.outcome
        end = (poss.team_id, poss.period, outcome)
        if raw:
            prev = self._last_end_raw
            if prev and prev[0] == end[0] and prev[1] == end[1] and prev[2] != "trip":
                self._breaks_raw += 1
            self._last_end_raw = end
        if actual:
            self._counted[poss.team_id] += 1
            prev = self._last_end
            if prev and prev[0] == end[0] and prev[1] == end[1] and prev[2] != "trip":
                self._breaks += 1
            self._last_end = end


def track(events: Sequence[Event], team_ids: Sequence[str]) -> Tuple[List[Possession], PossessionQuality]:
    """Possessions of a whole game (events in any order: they are sorted by clock, then by line number)."""
    tracker = PossessionTracker(team_ids)
    out: List[Possession] = []
    for ev in sorted(events, key=lambda e: (e.elapsed, e.num)):
        out += tracker.feed(ev)
    out += tracker.finish()
    return out, tracker.quality()
