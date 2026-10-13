"""Statistics over a window of the event log, and the diagnosis of a run or a drought.

Reads the log entries ``[elapsed, team_id, kind, value, player_id]`` of ``state.LiveGame`` (kinds: pts, fg2, fg3,
ft, tov, orb, stl, timeout). Entries written by an older engine have no player (4 elements) and still count.
Standard library only. Rules (runs, droughts, shooting streaks, hot players) build on these helpers.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from .config import RuleConfig

_SHOT_KINDS = ("fg2", "fg3", "ft")
_FIELD_GOALS = ("fg2", "fg3")


def player_of(entry: Sequence[Any]) -> Optional[str]:
    return entry[4] if len(entry) > 4 else None


def window_stats(log: Iterable[Sequence[Any]], team_id: str, start: int, end: int) -> Dict[str, Any]:
    """What ``team_id`` did in the game-seconds ``[start, end]`` (both ends included)."""
    s: Dict[str, Any] = {"pts": 0, "fg2": [0, 0], "fg3": [0, 0], "ft": [0, 0], "tov": 0, "tov_by_player": {},
                         "orb": 0, "stl": 0, "timeouts": 0}
    for e in log:
        if e[1] != team_id or not start <= e[0] <= end:
            continue
        kind = e[2]
        if kind == "pts":
            s["pts"] += e[3]
        elif kind in _SHOT_KINDS:
            s[kind][1] += 1
            s[kind][0] += 1 if e[3] else 0
        elif kind == "tov":
            s["tov"] += 1
            if player_of(e):
                s["tov_by_player"][player_of(e)] = s["tov_by_player"].get(player_of(e), 0) + 1
        elif kind == "orb":
            s["orb"] += 1
        elif kind == "stl":
            s["stl"] += 1
        elif kind == "timeout":
            s["timeouts"] += 1
    return s


def _gap(log: Iterable[Sequence[Any]], team_id: str, now: int, since: int, kinds: Sequence[str], made_only: bool) -> int:
    last = since
    for e in log:
        if e[1] == team_id and e[0] <= now and e[2] in kinds and (e[3] if made_only else True):
            last = max(last, e[0])
    return max(0, now - last)


def scoring_gap(log: Iterable[Sequence[Any]], team_id: str, now: int, since: int = 0) -> int:
    """Game-seconds since ``team_id`` last scored (free throws count); since ``since`` if it has not scored yet."""
    return _gap(log, team_id, now, since, ("pts",), made_only=False)


def field_goal_gap(log: Iterable[Sequence[Any]], team_id: str, now: int, since: int = 0) -> int:
    """Game-seconds since the last MADE field goal (free throws do not count)."""
    return _gap(log, team_id, now, since, _FIELD_GOALS, made_only=True)


def last_shots(log: Iterable[Sequence[Any]], team_id: str, n: int, kinds: Sequence[str] = _FIELD_GOALS,
               player_id: Optional[str] = None) -> List[int]:
    """Results (1 made, 0 missed) of the last ``n`` attempts of ``kinds``, oldest first; of one player if given."""
    shots = [int(bool(e[3])) for e in log
             if e[1] == team_id and e[2] in kinds and (player_id is None or player_of(e) == player_id)]
    return shots[-n:] if n > 0 else []


def trailing_makes(results: Sequence[int]) -> int:
    """Consecutive makes at the end of a list of shot results."""
    count = 0
    for r in reversed(results):
        if not r:
            break
        count += 1
    return count


def player_points(log: Iterable[Sequence[Any]], player_id: str, start: int, end: int) -> int:
    return sum(e[3] for e in log if e[2] == "pts" and player_of(e) == player_id and start <= e[0] <= end)


# -- diagnosis ---------------------------------------------------------------------

# Heuristic points each event explains. Not calibrated: they only rank the causes of a window.
_WEIGHT = {"turnovers": 1.0, "rival_orb": 1.0, "own_free_throws": 1.0, "rival_threes": 1.0,
           "rival_free_throws": 0.5, "own_cold": 0.5}
_COLD_FG_PCT = 0.30


def _n(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def _turnover_text(own: Dict[str, Any], names: Dict[str, str]) -> str:
    text = _n(own["tov"], "pérdida", "pérdidas")
    if own["tov_by_player"]:
        pid, k = max(sorted(own["tov_by_player"].items()), key=lambda kv: kv[1])
        if k >= 2:
            text += f" ({k} de {names.get(pid, pid)})"
    return text


def run_causes(own: Dict[str, Any], rival: Dict[str, Any], names: Dict[str, str], config: RuleConfig) -> List[Dict[str, Any]]:
    """Why a window went badly: ranked causes in Spanish, each ``{kind, count, points, text}``.

    ``own`` and ``rival`` are ``window_stats`` of the same window. A cause needs ``config.cause_min_count`` events;
    at most ``config.cause_max`` are returned, the ones that explain the most points first.
    """
    need = config.cause_min_count
    fga = own["fg2"][1] + own["fg3"][1]
    fgm = own["fg2"][0] + own["fg3"][0]
    ft_miss = own["ft"][1] - own["ft"][0]
    found = [
        ("turnovers", own["tov"], _turnover_text(own, names)),
        ("rival_orb", rival["orb"], _n(rival["orb"], "rebote ofensivo del rival", "rebotes ofensivos del rival")),
        ("own_free_throws", ft_miss, _n(ft_miss, "tiro libre fallado", "tiros libres fallados")),
        ("rival_threes", rival["fg3"][0], _n(rival["fg3"][0], "triple del rival", "triples del rival")),
        ("rival_free_throws", rival["ft"][1], _n(rival["ft"][1], "tiro libre del rival", "tiros libres del rival")),
    ]
    causes = [{"kind": k, "count": c, "points": round(c * _WEIGHT[k], 2), "text": t} for k, c, t in found if c >= need]
    if fga >= 2 * need and fgm / fga < _COLD_FG_PCT:
        causes.append({"kind": "own_cold", "count": fga - fgm, "points": round((fga - fgm) * _WEIGHT["own_cold"], 2),
                       "text": f"tiro propio {fgm}/{fga}"})
    causes.sort(key=lambda c: -c["points"])  # stable: ties keep the order above
    return causes[:config.cause_max]
