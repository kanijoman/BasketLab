"""Scores of a probability forecast (issue #255): Brier, log loss, reliability by deciles and the MAE of the margin."""

from __future__ import annotations

import math
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
