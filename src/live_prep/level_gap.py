"""The strength gap between divisions, estimated from real games between them (issue #464): ``python -m src.live_prep.level_gap``.

A team's net rating is measured against the teams of its own division, so to put two divisions on the same scale the games between them are needed
(the Copa de España: Cultural Leonesa of 2ª FEB against Alimerka Oviedo of 1ª FEB). Each team gets a rating (the mean net rating per 100 possessions of its games
inside its own division); a game between divisions says how much the stronger division's team beat what the ratings alone predicted, and the mean of
that over the levels of difference is the gap ``category_strength.LEVEL_GAP_NET_RTG`` is calibrated with. With a handful of games the standard error is
as large as the estimate: it is printed so nobody sets the constant from noise.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import Counter
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from src.live_core.engine import LiveEngine
from src.live_core.four_factors import possessions

from .category_strength import team_level


def team_ratings(league_games: Iterable[Dict[str, Any]]) -> Dict[str, float]:
    """Mean net rating per 100 possessions of every team over its games inside its division (``a``, ``b``, ``margin100`` from ``a``'s side)."""
    ratings: Dict[str, List[float]] = {}
    for g in league_games:
        ratings.setdefault(g["a"], []).append(g["margin100"])
        ratings.setdefault(g["b"], []).append(-g["margin100"])
    return {team: sum(values) / len(values) for team, values in ratings.items()}


def estimate_gap(cross_games: Iterable[Dict[str, Any]], ratings: Dict[str, float]) -> Dict[str, Any]:
    """``{gap, n, se}``: net rating per 100 possessions that one division of difference is worth, from games between divisions.

    Each game gives ``(actual - (rating a - rating b)) / (level b - level a)``: positive when the team of the stronger division (lower level number) did better than
    its rating predicted. Games of the same division, or of a team with no rating, say nothing."""
    values: List[float] = []
    for g in cross_games:
        levels = g["level_b"] - g["level_a"]
        if not levels or g["a"] not in ratings or g["b"] not in ratings:
            continue
        values.append((g["margin100"] - (ratings[g["a"]] - ratings[g["b"]])) / levels)
    if not values:
        return {"gap": None, "n": 0, "se": None}
    mean = sum(values) / len(values)
    se = math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1) / len(values)) if len(values) > 1 else None
    return {"gap": round(mean, 2), "n": len(values), "se": round(se, 2) if se is not None else None}


def _game_record(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ids = [str(t["id"]) for t in doc["HEADER"]["TEAM"]]
    if len(ids) != 2:
        return None
    snap = LiveEngine().update(doc)
    stats = {tid: snap["teams"][tid]["stats"] for tid in ids}
    n = (possessions(stats[ids[0]]) + possessions(stats[ids[1]])) / 2
    if not n:
        return None
    return {"a": ids[0], "b": ids[1], "margin100": (snap["score"][ids[0]] - snap["score"][ids[1]]) / n * 100}


def collect(games_by_collection: Iterable[Any], level_of: Callable[[str], Optional[int]]) -> Dict[str, Any]:
    """``(collection, games)`` pairs → the estimate. Collections with a division define where each team plays; games between teams of different divisions,
    wherever they were played (a cup), are the sample."""
    records: List[Dict[str, Any]] = []
    team_levels: Dict[str, Counter] = {}
    for collection, games in games_by_collection:
        level = level_of(collection)
        for doc in games:
            record = _game_record(doc)
            if record is None:
                continue
            records.append(record)
            if level is not None:
                for team in (record["a"], record["b"]):
                    team_levels.setdefault(team, Counter())[level] += 1
    levels = {team: team_level(counts) for team, counts in team_levels.items()}
    league = [r for r in records if r["a"] in levels and levels[r["a"]] == levels.get(r["b"])]
    cross = [{**r, "level_a": levels[r["a"]], "level_b": levels[r["b"]]} for r in records
             if r["a"] in levels and r["b"] in levels and levels[r["a"]] != levels[r["b"]]]
    result = estimate_gap(cross, team_ratings(league))
    result["teams"] = len(levels)
    return result


def in_season(collection: str, season: str) -> bool:
    """The collection is of the season that starts in ``season`` (its name carries ``2026_2027``)."""
    return f"_{season}_{int(season) + 1}" in collection


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Estimate the net rating gap between divisions from the games between them.")
    parser.add_argument("--season", default="2026", help="year the season starts (collections of other seasons are not read)")
    args = parser.parse_args(argv)
    from src.database import MongoDBHandler
    from src.services.collection_service import CollectionService

    from .db_source import catalog_level_of
    from .eval_source import games_from_mongo

    handler = MongoDBHandler()
    service = CollectionService(handler)
    names = [n for n in sorted(handler.repository.connection.get_database().list_collection_names())
             if not service._SKIP_PREFIXES.match(n) and n not in service._SKIP_NAMES and not n.upper().startswith("FBCYL")
             and in_season(n, args.season)]
    result = collect(((name, games_from_mongo(handler, name)) for name in names), catalog_level_of(handler))
    print(f"{len(names)} colecciones, {result['teams']} equipos con división; partidos entre divisiones: {result['n']}")
    if result["gap"] is None:
        print("Sin partidos entre divisiones: LEVEL_GAP_NET_RTG sigue sin calibrar.")
    else:
        print(f"Diferencia por división: {result['gap']:+.2f} por 100 posesiones (error típico {result['se']}). "
              f"Ajusta category_strength.LEVEL_GAP_NET_RTG solo si el error es pequeño frente a la estimación.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
