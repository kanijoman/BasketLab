"""The movements between competitions of the equivalence graph (#891, E1a of epic #872): the table the estimator (E1b) reads, and nothing else: no model.

From the rows of ``talent-data`` (one per person, season, competition and team) it builds:

* **observations**: the percentiles of the eight axes of the radar of a person who played enough (``eligible``), as z (the inverse of the normal: a percentile is not additive, a z is), ONE per person, node and
  season (a player who changed team inside a competition keeps the row with more minutes);
* **movements**: the same person in two DIFFERENT competitions of the same sex in CONSECUTIVE seasons, with the z of each: they tie the levels (a cup, the formation and the same season in two competitions are not
  this kind of evidence: the cup is not a level, the formation is E3's question and two at once are a different one);
* **stayers**: the same person in the same competition in consecutive seasons: they measure how reliable each axis is (E1b);
* **edge counts**: how many persons moved between each pair of competitions and in which direction (by the ``level`` of the catalogue, 1 the highest), which decides which edges have the evidence to exist.

A **node** is a competition (``sex|league|name``, the same in every season); the person is the one an external player is linked to (``linked_to``), never matched by name. Pure functions, no I/O: the rows
are those the web reads, so the same table is what the browser sees. Decisions of 20/11/2026 in ``docs/evaluaciones/2026-11-20_grafo-equivalencias-891.md``.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

AXES = ("pts", "ast", "orb", "drb", "stl", "blk", "efg", "tov")           # the eight axes of the radar (``frontend/src/market/player.ts``)
MIN_ELIGIBLE_AXES = len(AXES)                                              # a row with an axis missing is left out: a missing axis is never a zero
_CUT = 0.005                                                               # the percentiles 0 and 100 are cut at 0.5 and 99.5 so that their z is finite
_NORMAL = NormalDist()
_NOT_LEVELS = ("COPA", "CE SSAA")                                          # a cup shares its players with the league at the same time: it is not a level


@dataclass(frozen=True)
class Observation:
    person: str
    node: str
    season: int
    age: Optional[int]
    minutes: int
    z: Tuple[float, ...]


@dataclass(frozen=True)
class Movement:
    person: str
    from_node: str
    to_node: str
    from_season: int
    to_season: int
    age: Optional[int]                    # the age in the season he arrives
    z_from: Tuple[float, ...]
    z_to: Tuple[float, ...]


def node_of(entry: Mapping[str, Any]) -> Optional[str]:
    """``F|feb|LF CHALLENGE`` for a senior league of FEB: its sex, its league and its name, the same in every season. ``None`` for what is not a level of this graph: the formation (E3), a cup and a competition that does
    not say its sex."""
    name, gender = entry.get("competition"), entry.get("gender")
    if entry.get("category") != "senior" or entry.get("league") != "feb" or gender not in ("M", "F") or not name or str(name).upper().startswith(_NOT_LEVELS):
        return None
    return f"{gender}|{entry['league']}|{name}"


def person_of(row: Mapping[str, Any]) -> str:
    """The person: the one an external player is linked to, or the player himself."""
    return str(row.get("linked_to") or row["person_id"])


def z_of(percentile: float) -> float:
    """The z of a percentile (0 to 100), cut at the extremes."""
    return _NORMAL.inv_cdf(min(max(float(percentile) / 100.0, _CUT), 1.0 - _CUT))


def _z_row(row: Mapping[str, Any]) -> Optional[Tuple[float, ...]]:
    pct = row.get("pct") or {}
    values = [pct.get(axis) for axis in AXES]
    return tuple(z_of(v) for v in values) if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values) else None


def observations(rows: Iterable[Mapping[str, Any]], competitions: Mapping[str, Mapping[str, Any]]) -> List[Observation]:
    """One observation per person, node and season, sorted. ``competitions`` is ``{key of the competition: its entry}`` (``competition``, ``league``, ``gender``, ``category``, ``level``, ``season``); a row of a
    competition it does not know, that is not a node, that did not play enough or that lacks an axis is left out."""
    best: Dict[Tuple[str, str, int], Tuple[Tuple[int, str], Observation]] = {}
    for row in rows:
        entry = competitions.get(row.get("comp"))
        node = node_of(entry) if entry else None
        z = _z_row(row)
        if not node or not row.get("eligible") or z is None:
            continue
        season = int(entry["season"])
        obs = Observation(person_of(row), node, season, row.get("age"), int(row.get("minutes") or 0), z)
        key = (obs.person, node, season)
        rank = (obs.minutes, str(row.get("person_id")))                # a tie goes to the larger id: the answer does not depend on the order of the rows
        if key not in best or rank > best[key][0]:
            best[key] = (rank, obs)
    return [best[k][1] for k in sorted(best)]


def _pairs(obs: Iterable[Observation], same_node: bool) -> List[Movement]:
    by_person: Dict[str, List[Observation]] = {}
    for o in obs:
        by_person.setdefault(o.person, []).append(o)
    out: List[Movement] = []
    for person in sorted(by_person):
        rs = by_person[person]
        for a in rs:
            for b in rs:
                if b.season - a.season == 1 and (a.node == b.node) == same_node and a.node.split("|")[0] == b.node.split("|")[0]:
                    out.append(Movement(person, a.node, b.node, a.season, b.season, b.age, a.z, b.z))
    return sorted(out, key=lambda m: (m.person, m.from_season, m.from_node, m.to_node))


def movements(obs: Iterable[Observation]) -> List[Movement]:
    """The same person in two different competitions of the same sex in consecutive seasons, sorted by person and season."""
    return _pairs(list(obs), same_node=False)


def stayers(obs: Iterable[Observation]) -> List[Movement]:
    """The same person in the same competition in consecutive seasons (``from_node == to_node``)."""
    return _pairs(list(obs), same_node=True)


def node_levels(competitions: Mapping[str, Mapping[str, Any]]) -> Dict[str, Optional[int]]:
    """``{node: level}`` of the competitions of the catalogue (the level of a node is the one its competitions say; ``None`` if none of them says it)."""
    out: Dict[str, Optional[int]] = {}
    for entry in competitions.values():
        node = node_of(entry)
        if node:
            out[node] = entry.get("level") if entry.get("level") is not None else out.get(node)
    return out


def edge_counts(moves: Iterable[Movement], levels: Optional[Mapping[str, Optional[int]]] = None) -> Dict[Tuple[str, str], Dict[str, int]]:
    """``{(node a, node b): {up, down, unranked, persons}}`` with the two nodes in order: how many movements went to a higher level (``up``), to a lower one (``down``) or between two whose level is not known
    (``unranked``), and how many DIFFERENT persons made them (a person who moved twice is one person: the resampling of E1b is by person). ``levels`` is ``{node: level}`` (``node_levels``); without it every
    movement is ``unranked``."""
    levels = levels or {}
    counts: Dict[Tuple[str, str], Dict[str, int]] = {}
    people: Dict[Tuple[str, str], Set[str]] = {}
    for m in moves:
        key = tuple(sorted((m.from_node, m.to_node)))
        edge = counts.setdefault(key, {"up": 0, "down": 0, "unranked": 0, "persons": 0})
        a, b = levels.get(m.from_node), levels.get(m.to_node)
        edge["unranked" if a is None or b is None else "up" if b < a else "down"] += 1
        people.setdefault(key, set()).add(m.person)
    for key, edge in counts.items():
        edge["persons"] = len(people[key])
    return counts
