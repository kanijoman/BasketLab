"""The A/B of the rotation lever (issue #587): «the five on court is X per 40 min worse than the best available five».

Held-out games only (the oldest 60 % of every folder, plus the earlier seasons of the competition, give the ratings). For every moment of a team (a stint of the lineup rows) the gap
is the rating of the best five among the players who played that game minus the rating of the five on court. Three questions, answered against what the coaches did:
saturation (how many alerts per game the lever would give), agreement (do the coaches change the five within two minutes when it is high, and towards better fives)
and value (what happened in the next five minutes when the gap was high and nobody changed it, against when somebody did).
"""
from __future__ import annotations

import pickle
from typing import Any, Dict, List, Sequence, Tuple

from .players import ratings

RIDGE = {"women": 2000.0, "men": 30000.0}
THRESHOLDS = (2.0, 4.0, 6.0, 8.0)       # points per 40 minutes, summed over the five
WINDOW_S = 120                          # «the coach reacted» = the five changed within this time
HORIZON_S = 300
QUIET_S = 300                           # after an alert the lever stays silent this long
MIN_S = 120                             # nothing in the first minutes of the game


def _strength(rate: Dict[str, float], five: Sequence[str]) -> float:
    return sum(rate.get(p, 0.0) for p in five)


def _gap(rate: Dict[str, float], five: Sequence[str], pool: Sequence[str]) -> float:
    return sum(sorted((rate.get(p, 0.0) for p in pool), reverse=True)[:5]) - _strength(rate, five)


def _best(rate: Dict[str, float], pool: Sequence[str]) -> List[str]:
    return sorted(pool, key=lambda p: -rate.get(p, 0.0))[:5]


def side_moments(game: Dict[str, Any], home: bool, rate: Dict[str, float], check: Dict[str, float] = None) -> List[Dict[str, Any]]:
    """One moment per stint of one side: time, gap, the first change of five within ``WINDOW_S`` (its effect on the rating) and the margin of the next ``HORIZON_S``."""
    sign = 1 if home else -1
    t, stints = 0, []
    for h, a, delta, seconds in game["rows"]:
        stints.append({"t": t, "five": tuple(h if home else a), "delta": sign * delta})
        t += seconds
    pool = sorted({p for s in stints for p in s["five"]})            # who played that game for the team (nobody is injured or fouled out in the pool: an optimistic «available»)
    out = []
    for i, s in enumerate(stints):
        if len(pool) < 7 or s["t"] < MIN_S or s["t"] > 2400 - HORIZON_S:
            continue
        change = next((x for x in stints[i + 1:] if x["t"] - s["t"] <= WINDOW_S and x["five"] != s["five"]), None)
        later = [x for x in stints[i + 1:] if x["t"] - s["t"] <= HORIZON_S]
        best = _best(rate, pool)
        real = _strength(check, best) - _strength(check, s["five"]) if check is not None else 0.0        # the same five and best five, measured with ratings from OTHER games
        out.append({"t": s["t"], "gap": _gap(rate, s["five"], pool), "real": real, "changed": change is not None,
                    "better": _strength(rate, change["five"]) - _strength(rate, s["five"]) if change else 0.0,
                    "next": sum(x["delta"] for x in later)})
    return out


def alerts(moments: Sequence[Dict[str, Any]], threshold: float) -> List[Dict[str, Any]]:
    """The rule: the gap holds above the threshold in two consecutive stints, then silence for ``QUIET_S``."""
    fired, last, prev = [], -10 ** 9, False
    for m in moments:
        high = m["gap"] >= threshold
        if high and prev and m["t"] - last >= QUIET_S:
            fired.append(m)
            last = m["t"]
        prev = high
    return fired


def rotation_ab(lineups_path: str, women: bool, split: bool = False) -> Tuple[List[Dict[str, Any]], int]:
    """Moments of the held-out games of every folder plus the number of team-games."""
    lineups = pickle.load(open(lineups_path, "rb"))
    moments: List[Dict[str, Any]] = []
    sides = 0
    for folder, games in lineups.items():
        codes = sorted(games, key=lambda c: games[c]["order"])
        cut = int(len(codes) * 0.6)
        train, test = codes[:cut], codes[cut:]
        parent, season = folder.rsplit("/", 1)
        earlier = sorted(f for f in lineups if f.rsplit("/", 1)[0] == parent and f.rsplit("/", 1)[1] < season)
        pool = {f"{k}:{c}": g for k, f in enumerate(earlier) for c, g in lineups[f].items()} | games
        used = [f"{k}:{c}" for k, f in enumerate(earlier) for c in lineups[f]] + train
        ridge = RIDGE["women" if women else "men"]
        rate = ratings(pool, used, ridge)
        halves = (ratings(pool, used[::2], ridge), ratings(pool, used[1::2], ridge)) if split else (rate, None)
        for code in test:
            for home in (True, False):
                got = side_moments(games[code], home, halves[0], halves[1])
                for m in got:
                    m["game"] = f"{folder}:{code}:{home}"
                moments += got
                sides += 1
    return moments, sides


def reliability(lineups_path: str, women: bool) -> str:
    """The gap computed with the ratings of half of the games and measured with the other half: how much of it is real (the slope), by size of the gap."""
    import numpy as np

    moments, _ = rotation_ab(lineups_path, women, split=True)
    gap, real = np.array([m["gap"] for m in moments]), np.array([m["real"] for m in moments])
    slope = float(np.polyfit(gap, real, 1)[0])
    lines = [f"Fiabilidad del hueco (calculado con los partidos pares y medido con los impares): pendiente {slope:+.2f} (1 = todo el hueco es real, 0 = todo ruido). Hueco esperado frente al real:", "",
             "| Hueco calculado | Momentos | Hueco medio calculado | Hueco real (otros partidos) |", "|---|---|---|---|"]
    edges = np.percentile(gap, [0, 50, 75, 90, 97, 100])
    for lo, hi in zip(edges, edges[1:]):
        pick = (gap >= lo) & (gap <= hi)
        lines.append(f"| {lo:.1f} a {hi:.1f} | {int(pick.sum())} | {gap[pick].mean():.1f} | {real[pick].mean():+.1f} |")
    return "\n".join(lines)


def report(lineups_path: str, women: bool) -> str:
    import numpy as np

    moments, sides = rotation_ab(lineups_path, women)
    gaps = np.array([m["gap"] for m in moments])
    base_change = np.mean([m["changed"] for m in moments])
    lines = [f"{sides} equipos-partido de la parte posterior de cada temporada, {len(moments)} momentos (un tramo de ≈ 30 s). Hueco mediano entre el quinteto en pista y el mejor disponible: "
             f"{np.median(gaps):.1f} puntos por 40 min (percentil 90: {np.percentile(gaps, 90):.1f}). En el {base_change:.0%} de los momentos el entrenador cambia el quinteto en los 2 minutos siguientes.", "",
             "| Umbral | Alertas por equipo-partido | Cambia en 2 min | Cambia a mejor | Margen en los 5 min siguientes: no cambia | cambia | Diferencia (IC 95 % por partidos) |", "|---|---|---|---|---|---|---|"]
    rng = np.random.default_rng(0)
    keys = sorted({m["game"] for m in moments})
    per_game = {k: [m for m in moments if m["game"] == k] for k in keys}
    for threshold in THRESHOLDS:
        by_game = {k: alerts(per_game[k], threshold) for k in keys}
        fired = [m for got in by_game.values() for m in got]
        if len(fired) < 20:
            lines.append(f"| {threshold:g} | {len(fired) / sides:.2f} | (pocas alertas) | | | | |")
            continue
        keep = [m["next"] for m in fired if not m["changed"]]
        moved = [m for m in fired if m["changed"]]
        diffs = []
        for _ in range(500):
            pick = [by_game[keys[k]] for k in rng.integers(0, len(keys), len(keys))]
            a = [m["next"] for g in pick for m in g if not m["changed"]]
            b = [m["next"] for g in pick for m in g if m["changed"]]
            if a and b:
                diffs.append(np.mean(b) - np.mean(a))
        mean_moved = np.mean([m["next"] for m in moved])
        lines.append(f"| {threshold:g} | {len(fired) / sides:.2f} | {len(moved) / len(fired):.0%} (base {base_change:.0%}) | {np.mean([m['better'] > 0 for m in moved]):.0%} | {np.mean(keep):+.2f} | "
                     f"{mean_moved:+.2f} | {mean_moved - np.mean(keep):+.2f} ({np.percentile(diffs, 2.5):+.2f} a {np.percentile(diffs, 97.5):+.2f}) |")
    changed = np.array([m["changed"] for m in moments])
    better = np.array([m["better"] for m in moments])
    lines += ["", f"Correlación del hueco con «el entrenador cambia en 2 min»: {np.corrcoef(gaps, changed)[0, 1]:+.3f}; con la mejora de rating del cambio (cuando lo hay): "
              f"{np.corrcoef(gaps[changed], better[changed])[0, 1]:+.3f} (un hueco grande debería llevar a cambios que lo cierran: negativa)."]
    return "\n".join(lines)
