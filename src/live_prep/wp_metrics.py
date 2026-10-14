"""Scores of a probability forecast (issue #255): Brier, log loss, reliability by deciles and the MAE of the margin."""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Sequence

LOG_LOSS_EPS = 1e-4   # a forecast of exactly 0 or 1 that fails is penalised heavily, not infinitely


def brier(ps: Sequence[float], ys: Sequence[int]) -> Optional[float]:
    return sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(ps) if ps else None


def log_loss(ps: Sequence[float], ys: Sequence[int]) -> Optional[float]:
    if not ps:
        return None
    clipped = [min(max(p, LOG_LOSS_EPS), 1 - LOG_LOSS_EPS) for p in ps]
    return -sum(math.log(p if y else 1 - p) for p, y in zip(clipped, ys)) / len(ps)


def mae(predicted: Sequence[float], actual: Sequence[float]) -> Optional[float]:
    return sum(abs(a - p) for p, a in zip(predicted, actual)) / len(predicted) if predicted else None


def reliability(ps: Sequence[float], ys: Sequence[int], bins: int = 10) -> List[Dict[str, Any]]:
    """Per occupied bin of the forecast: how many, the mean forecast and how often it happened (1.0 goes to the last bin)."""
    cells: Dict[int, List[Any]] = {}
    for p, y in zip(ps, ys):
        cell = cells.setdefault(min(int(p * bins), bins - 1), [0, 0.0, 0])
        cell[0] += 1
        cell[1] += p
        cell[2] += y
    return [{"bin": b, "n": n, "mean_p": total / n, "freq": hits / n} for b, (n, total, hits) in sorted(cells.items())]


def max_decile_gap(rows: Sequence[Dict[str, Any]], min_n: int = 10) -> Optional[float]:
    """Largest |frequency - forecast| in points among the bins with at least ``min_n`` forecasts (None: no such bin)."""
    gaps = [abs(r["freq"] - r["mean_p"]) * 100 for r in rows if r["n"] >= min_n]
    return max(gaps) if gaps else None


def bootstrap_reliability(ps: Sequence[float], ys: Sequence[int], games: Sequence[str], bins: int = 10,
                          resamples: int = 1000, seed: int = 0, level: float = 0.95) -> List[Dict[str, Any]]:
    """Reliability per bin with a bootstrap interval of the gap, resampling WHOLE GAMES (issue #261).

    The cuts of a game, and the two sides of it, share the outcome, so they are not independent: resampling games is what
    gives an honest interval. ``gap`` is ``freq - mean_p`` in points; ``lo``/``hi`` the percentiles of ``level`` over the
    resamples in which the bin was not empty. An interval that excludes 0 says the gap is not just noise.
    """
    per_game: Dict[str, Dict[int, List[float]]] = {}
    for p, y, game in zip(ps, ys, games):
        cell = per_game.setdefault(game, {}).setdefault(min(int(p * bins), bins - 1), [0, 0.0, 0])
        cell[0] += 1
        cell[1] += p
        cell[2] += y
    ids = list(per_game)
    if not ids:
        return []

    def gaps(chosen: Sequence[str]) -> Dict[int, List[float]]:
        total: Dict[int, List[float]] = {}
        for gid in chosen:
            for b, (n, sp, hits) in per_game[gid].items():
                t = total.setdefault(b, [0, 0.0, 0])
                t[0] += n
                t[1] += sp
                t[2] += hits
        return total

    base = gaps(ids)
    rng = random.Random(seed)
    draws: Dict[int, List[float]] = {b: [] for b in base}
    for _ in range(resamples):
        for b, (n, sp, hits) in gaps([rng.choice(ids) for _ in ids]).items():
            if b in draws and n:
                draws[b].append((hits / n - sp / n) * 100)
    tail = (1 - level) / 2
    rows = []
    for b in sorted(base):
        n, sp, hits = base[b]
        ordered = sorted(draws[b])
        lo = ordered[int(tail * (len(ordered) - 1))] if ordered else None
        hi = ordered[int((1 - tail) * (len(ordered) - 1))] if ordered else None
        rows.append({"bin": b, "n": n, "games": sum(1 for gid in ids if b in per_game[gid]), "mean_p": sp / n, "freq": hits / n,
                     "gap": (hits / n - sp / n) * 100, "lo": lo, "hi": hi})
    return rows
