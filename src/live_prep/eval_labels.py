"""What the coach did about an alert, read from the finished game (rule evaluator).

For an alert, ``E`` is the game-second of the snapshot that produced it and ``S`` the game-second on screen when it
was shown (S >= E). Each rule has an expected action (``ACTION_FOR``): the named player leaves the court, the team
calls a timeout, or one of the proposed players comes in. Rules without one are judged only by their outcome. A
matching action counts from ``E - lookback_s`` (the feed delays the lines the engine had seen) and is
``anticipada`` if it happened by S (the coach decided alone), ``seguida`` within ``follow_s`` after S, ``tarde``
within ``late_s``, and ``no`` otherwise. ``outcome_of`` compares the five minutes after S with the five before.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

from src.live_core.events import Event, parse_line

# Rule id -> the action that answers it. Rules not listed have none (outcome only).
ACTION_FOR: Dict[str, str] = {
    "foul_trouble": "sub_out",
    "fatigue_high": "sub_out",
    "rival_run": "timeout",
    "turnover_streak": "timeout",
    "own_drought": "timeout",
    "long_run": "timeout",
    "four_factors_lever": "proposed_sub",
    "rest_starters": "proposed_sub",
}

_FOUL_OUT = 5
_SHOTS = ("fg2", "fg3", "ft")


@dataclass(frozen=True)
class LabelConfig:
    follow_s: int = 120   # an action up to this long after the alert was shown is "seguida"
    late_s: int = 300     # up to this long, "tarde"
    lookback_s: int = 40  # actions this long before the engine saw the condition still answer it (feed latency)
    window_s: int = 300   # outcome windows before and after the alert


class Actions:
    """The events of a finished game, in game order, that the labels look at."""

    def __init__(self, events: Iterable[Event]) -> None:
        self.events: List[Event] = sorted((e for e in events if not e.deleted), key=lambda e: (e.elapsed, e.num))

    @classmethod
    def from_game(cls, game: Dict[str, Any]) -> "Actions":
        lines = ((game.get("PLAYBYPLAY") or {}).get("LINES")) or []
        return cls(e for e in (parse_line(line) for line in lines) if e is not None)

    def timeouts(self, team_id: str) -> List[int]:
        return [e.elapsed for e in self.events if e.kind == "timeout" and e.team_id == team_id]

    def voluntary_sub_outs(self, player_id: str) -> List[int]:
        """When the player left the court, except when his 5th foul sent him out."""
        forced = {e.elapsed for e in self.events
                  if e.kind == "foul" and e.player_id == player_id and (e.pf_count or 0) >= _FOUL_OUT}
        return [e.elapsed for e in self.events
                if e.kind == "sub_out" and e.player_id == player_id and e.elapsed not in forced]

    def sub_ins(self, team_id: str, player_ids: Iterable[str]) -> List[int]:
        wanted = set(player_ids)
        return [e.elapsed for e in self.events if e.kind == "sub_in" and e.team_id == team_id and e.player_id in wanted]


def _action_times(kind: str, row: Dict[str, Any], actions: Actions) -> List[int]:
    if kind == "sub_out":
        player = (row.get("evidence") or {}).get("player_id")
        return actions.voluntary_sub_outs(str(player)) if player is not None else []
    if kind == "timeout":
        return actions.timeouts(row["team"])
    if kind == "proposed_sub":
        proposed = [str(p["in_id"]) for p in row.get("proposal") or [] if p.get("in_id") is not None]
        return actions.sub_ins(row["team"], proposed)
    return []


def label_alert(row: Dict[str, Any], actions: Actions, cfg: LabelConfig) -> Dict[str, Any]:
    """``{label, action_at, delay}``: delay = action second minus the second the alert was shown (<= 0: anticipated)."""
    kind = ACTION_FOR.get(row["id"])
    if kind is None:
        return {"label": None, "action_at": None, "delay": None}
    shown = row["shown"]
    start = row["elapsed"] - cfg.lookback_s
    found = next((t for t in _action_times(kind, row, actions) if t >= start), None)
    if found is None or found - shown > cfg.late_s:
        return {"label": "no", "action_at": None, "delay": None}
    delay = found - shown
    name = "anticipada" if delay <= 0 else "seguida" if delay <= cfg.follow_s else "tarde"
    return {"label": name, "action_at": found, "delay": delay}


# --- outcome -----------------------------------------------------------------------------

def _count(kind: str, team: str) -> Callable[[List[Event]], int]:
    return lambda evs: sum(1 for e in evs if e.kind == kind and e.team_id == team)


def _efg(team: str) -> Callable[[List[Event]], Optional[float]]:
    def measure(evs: List[Event]) -> Optional[float]:
        shots = [e for e in evs if e.team_id == team and e.kind in ("fg2", "fg3")]
        if not shots:
            return None
        made = [e for e in shots if e.made]
        return round((len(made) + 0.5 * sum(1 for e in made if e.kind == "fg3")) / len(shots), 4)
    return measure


def _points(evs: List[Event], pick: Callable[[Event], bool]) -> int:
    return sum(e.points for e in evs if e.kind in _SHOTS and e.points and pick(e))


def _measure(rule_id: str, own: str) -> Optional[tuple]:
    """(name, function of a window's events) the rule wanted to move; None: net points only."""
    rival_pts = lambda evs: _points(evs, lambda e: e.team_id not in (None, own))  # noqa: E731
    return {
        "turnover_streak": ("own_tov", _count("turnover", own)),
        "rival_foul_trouble": ("own_fta", _count("ft", own)),
        "rival_near_bonus": ("own_fta", _count("ft", own)),
        "team_fouls_bonus": ("own_fouls", _count("foul", own)),
        "four_factors_lever": ("own_efg", _efg(own)),
        "rival_hot_player": ("rival_pts", rival_pts),
        "rival_zone": ("rival_pts", rival_pts),
    }.get(rule_id)


def outcome_of(row: Dict[str, Any], actions: Actions, cfg: Optional[LabelConfig] = None) -> Dict[str, Any]:
    """Net points (own minus rival) and the rule's own measure, five minutes before and after the alert was shown."""
    cfg, own, shown = cfg or LabelConfig(), row["team"], row["shown"]
    before = [e for e in actions.events if shown - cfg.window_s < e.elapsed <= shown]
    after = [e for e in actions.events if shown < e.elapsed <= shown + cfg.window_s]

    def net(evs: List[Event]) -> int:
        return _points(evs, lambda e: e.team_id == own) - _points(evs, lambda e: e.team_id not in (None, own))

    out: Dict[str, Any] = {"net_before": net(before), "net_after": net(after)}
    out["net_delta"] = out["net_after"] - out["net_before"]
    picked = _measure(row["id"], own)
    out["measure"] = {"name": picked[0], "before": picked[1](before), "after": picked[1](after)} if picked else None
    return out
