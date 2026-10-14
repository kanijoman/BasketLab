"""Calibrate the live win probability on finished games (issue #255): ``python -m src.live_prep.wp_cli``.

Every game is replayed from both sides with the package each team would have had before it (``SeasonAccumulator``);
at cuts every ``cut_s`` seconds the snapshot is kept together with the package baselines and the final result. The
forecast is then recomputed as many times as needed (variants, parameter grids) without replaying anything again.
Variants: ``full`` (the model), ``prior_only`` (pre-game expectation and nothing from the game) and ``score_time``
(only score and clock: the forecast the model has to beat).
"""

from __future__ import annotations

import dataclasses
import itertools
from typing import Any, Dict, Iterable, List, Optional, Sequence

from src.live_core.config import RuleConfig
from src.live_core.engine import LiveEngine
from src.live_core.four_factors import FourFactorsModel
from src.live_core.win_prob import GAME_SECONDS, WinProbabilityModel

from .eval_feed import finished_game_polls
from .eval_source import same_start_groups
from .package_builder import SeasonAccumulator
from .wp_metrics import bootstrap_reliability, brier, log_loss, mae, max_decile_gap, reliability

VARIANTS = ("full", "prior_only", "score_time")
_FIXED_DATE = "1970-01-01T00:00:00Z"


def _trimmed(snap: Dict[str, Any]) -> Dict[str, Any]:
    return {"score": dict(snap["score"]), "elapsed": snap["elapsed"], "home_id": snap.get("home_id"),
            "teams": {tid: {"stats": dict(t["stats"])} for tid, t in snap["teams"].items()}}


def _cuts(game: Dict[str, Any], cut_s: int) -> tuple:
    """(snapshots at the cuts, last snapshot) of the game replayed from the start."""
    engine, kept, last = LiveEngine(), {}, None
    for poll in finished_game_polls(game, latency_s=0.0, poll_s=10.0):
        last = engine.update(poll.doc)
        cut = (last["elapsed"] // cut_s) * cut_s
        if 0 < cut < GAME_SECONDS and cut not in kept:
            kept[cut] = _trimmed(last)
    return kept, last


def _game_samples(game: Dict[str, Any], index: int, acc: SeasonAccumulator, ids: List[str], cut_s: int,
                  min_prior: int, collection: str) -> List[Dict[str, Any]]:
    sides = [(own, rival) for own, rival in ((ids[0], ids[1]), (ids[1], ids[0])) if acc.played(own) >= min_prior]
    if not sides:
        return []
    kept, last = _cuts(game, cut_s)
    if last is None or not any(last["score"].values()):
        return []     # nothing replayed, or no points read (an old text format): any forecast would be meaningless
    out = []
    for own, rival in sides:
        baselines = acc.to_package(collection, "", own, rival, None, _FIXED_DATE).baselines
        margin = last["score"][own] - last["score"][rival]
        out += [{"game": str(game.get("_id") or index), "index": index, "team": own, "rival": rival, "cut": cut, "snap": snap,
                 "baselines": baselines, "final_margin": margin, "won": margin > 0}
                for cut, snap in sorted(kept.items())]
    return out


def collect_samples(games: Iterable[Dict[str, Any]], cut_s: int = 300, min_prior_games: int = 3,
                    collection: str = "FEB") -> List[Dict[str, Any]]:
    """Samples of every side of every game, in date order; a side needs ``min_prior_games`` earlier games of its team."""
    acc, samples, index = SeasonAccumulator(), [], 0
    for group in same_start_groups(games):
        for game in group:
            ids = [str(t["id"]) for t in game["HEADER"]["TEAM"]]
            if len(ids) == 2:
                samples += _game_samples(game, index, acc, ids, cut_s, min_prior_games, collection)
            index += 1
        for game in group:
            acc.add_game(game)
    return samples


def forecast(sample: Dict[str, Any], cfg: RuleConfig, variant: str) -> Dict[str, Any]:
    snap, own, rival = sample["snap"], sample["team"], sample["rival"]
    if variant == "score_time":
        return WinProbabilityModel(own, rival, {}, cfg).evaluate({**snap, "home_id": None}, None)
    ff = FourFactorsModel(own, rival, sample["baselines"], cfg).evaluate(snap) if variant == "full" else None
    return WinProbabilityModel(own, rival, sample["baselines"], cfg).evaluate(snap, ff)


def score_samples(samples: Sequence[Dict[str, Any]], cfg: RuleConfig, variant: str = "full") -> Dict[str, Any]:
    results = [forecast(s, cfg, variant) for s in samples]
    ps, ys = [r["p"] for r in results], [int(s["won"]) for s in samples]
    rel = reliability(ps, ys)
    return {"n": len(samples), "brier": brier(ps, ys), "log_loss": log_loss(ps, ys),
            "mae": mae([r["projected_margin"] for r in results], [s["final_margin"] for s in samples]),
            "reliability": rel, "max_gap": max_decile_gap(rel)}


def bootstrap_forecast(samples: Sequence[Dict[str, Any]], cfg: RuleConfig, resamples: int = 1000, seed: int = 0,
                       variant: str = "full") -> List[Dict[str, Any]]:
    """Per-decil gap of the forecast with a bootstrap interval resampling whole games (issue #261)."""
    results = [forecast(s, cfg, variant) for s in samples]
    return bootstrap_reliability([r["p"] for r in results], [int(s["won"]) for s in samples], [str(s["game"]) for s in samples],
                                 resamples=resamples, seed=seed)


def compare(samples: Sequence[Dict[str, Any]], cfg: Optional[RuleConfig] = None) -> Dict[str, Dict[str, Any]]:
    cfg = cfg or RuleConfig()
    return {variant: score_samples(samples, cfg, variant) for variant in VARIANTS}


def grid_search(samples: Sequence[Dict[str, Any]], grid: Dict[str, Sequence[float]],
                base: Optional[RuleConfig] = None) -> List[Dict[str, Any]]:
    """Every combination of the parameters of ``grid`` scored with the full model, best log loss first."""
    base, names, rows = base or RuleConfig(), list(grid), []
    for values in itertools.product(*(grid[n] for n in names)):
        params = dict(zip(names, values))
        scored = score_samples(samples, dataclasses.replace(base, **params), "full")
        rows.append({"params": params, "log_loss": scored["log_loss"], "brier": scored["brier"], "mae": scored["mae"],
                     "max_gap": scored["max_gap"]})
    return sorted(rows, key=lambda r: r["log_loss"])


# Criterion to show the probability in the app (agreed on 2026-10-14, issue #255): better than score and clock alone,
# not worse than the pre-game prior beyond the noise, and deciles with enough cuts (the two sides of a game mirror each
# other, so fewer cuts say little) within 5 points.
LOG_LOSS_TOLERANCE = 0.005
GAP_MIN_CUTS = 400
GAP_LIMIT_POINTS = 5.0


def app_criterion(compared: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """``met`` plus what it rests on: the two log-loss comparisons and the largest decile gap among trustworthy deciles."""
    full = compared["full"]
    vs_score_time = full["log_loss"] < compared["score_time"]["log_loss"]
    vs_prior = full["log_loss"] <= compared["prior_only"]["log_loss"] + LOG_LOSS_TOLERANCE + 1e-9
    gap = max_decile_gap(full["reliability"], min_n=GAP_MIN_CUTS)
    return {"met": bool(vs_score_time and vs_prior and gap is not None and gap <= GAP_LIMIT_POINTS),
            "vs_score_time": vs_score_time, "vs_prior": vs_prior, "gap": gap}
