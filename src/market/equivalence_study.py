"""The validation of the equivalence estimator (#891, E1b of epic #872): is the translation better than not translating, and can the range be shown?

**A season out at a time**: for each season ``S``, the model is fitted WITHOUT any movement or stayer that has ``S`` on either side, and the movements that arrive in ``S`` are predicted with it. Nothing of the
season it predicts is in the fit (ScoutingFEB split rows at random and its 0.88 was a leak). ``walk_forward`` is the stricter version for the last seasons: it fits only with the seasons BEFORE ``S``.

What is measured, per movement and axis, in z:
* the error of the model (``translate``), of **not translating** (``z_B = z_A``) and of **only shrinking** by the reliability (``rho * z_A``);
* whether the 80 % interval holds the real value (the coverage: 80 % is what an honest range gives) and its width.

Pure functions, no I/O: ``scripts/equivalence_study.py`` reads the published rows and prints the report. The estimator is ``equivalence_model``.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from src.market.equivalence import AXES, Movement
from src.market.equivalence_model import Model, fit as default_fit, reliability, translate


def _empty() -> Dict[str, List[float]]:
    return {"model": [], "identity": [], "rho_only": [], "hit": [], "width": []}


def _summary(acc: Dict[str, List[float]]) -> Dict[str, Any]:
    n = len(acc["hit"])
    mean = lambda values: (sum(values) / len(values)) if values else None          # noqa: E731
    return {"n": n, "mae_model": mean(acc["model"]), "mae_identity": mean(acc["identity"]), "mae_rho_only": mean(acc["rho_only"]), "coverage": mean(acc["hit"]), "mean_width": mean(acc["width"])}


def _score(model: Model, rho: Dict[str, List[float]], tests: Sequence[Movement], overall: Dict[str, List[float]], per_axis: List[Dict[str, List[float]]], per_edge: Dict[str, Dict[str, List[float]]],
           per_season: Dict[int, Dict[str, List[float]]], season: int) -> None:
    for m in tests:
        out = translate(model, m.from_node, m.to_node, m.z_from)
        sex = m.from_node.split("|")[0]
        if out is None or sex not in rho:
            continue
        edge = per_edge.setdefault(" <-> ".join(sorted(n.split("|")[2] for n in (m.from_node, m.to_node))) + f" ({sex})", _empty())
        bucket = per_season.setdefault(season, _empty())
        for i in range(len(AXES)):
            values = {"model": abs(m.z_to[i] - out[i]["mean"]), "identity": abs(m.z_to[i] - m.z_from[i]), "rho_only": abs(m.z_to[i] - rho[sex][i] * m.z_from[i]),
                      "hit": float(out[i]["lo"] <= m.z_to[i] <= out[i]["hi"]), "width": out[i]["hi"] - out[i]["lo"]}
            for acc in (overall, per_axis[i], edge, bucket):
                for key, value in values.items():
                    acc[key].append(value)


def _study(moves: Sequence[Movement], stay: Sequence[Movement], seasons: Sequence[int], train: Callable[[int, Movement], bool], fit_fn: Callable[..., Model], **options: Any) -> Dict[str, Any]:
    overall, per_axis, per_edge, per_season = _empty(), [_empty() for _ in AXES], {}, {}
    for season in seasons:
        training = [m for m in moves if train(season, m)]
        training_stay = [s for s in stay if train(season, s)]
        tests = [m for m in moves if m.to_season == season]
        if not tests or not training:
            continue
        model, rho = fit_fn(training, training_stay, **options), reliability(training_stay)
        _score(model, rho, tests, overall, per_axis, per_edge, per_season, season)
    return {"overall": _summary(overall), "per_axis": {AXES[i]: _summary(a) for i, a in enumerate(per_axis)}, "per_edge": {k: _summary(v) for k, v in sorted(per_edge.items())},
            "per_season": {k: _summary(v) for k, v in sorted(per_season.items())}}


def leave_one_season_out(moves: Iterable[Movement], stay: Iterable[Movement], fit_fn: Callable[..., Model] = default_fit, **options: Any) -> Dict[str, Any]:
    """Each season predicted by a model fitted without it (no movement or stayer with that season on either side). ``options`` go to ``fit`` (``slope``, ``cluster``)."""
    moves, stay = list(moves), list(stay)
    seasons = sorted({m.to_season for m in moves})
    return _study(moves, stay, seasons, lambda s, m: m.from_season != s and m.to_season != s, fit_fn, **options)


def walk_forward(moves: Iterable[Movement], stay: Iterable[Movement], first: Optional[int] = None, fit_fn: Callable[..., Model] = default_fit, **options: Any) -> Dict[str, Any]:
    """Each season from ``first`` on predicted with only the seasons before it (the strict version: the future never helps the past)."""
    moves, stay = list(moves), list(stay)
    seasons = [s for s in sorted({m.to_season for m in moves}) if first is None or s >= first]
    return _study(moves, stay, seasons, lambda s, m: m.to_season < s, fit_fn, **options)


def verdict(study: Dict[str, Any], tolerance: float = 0.05, nominal: float = 0.8) -> Dict[str, Any]:
    """Can the range be shown? It can if the model beats not translating AND the 80 % interval holds within ``tolerance`` of its nominal share (the rule of the design: if not, E4 keeps «orientativo»)."""
    overall = study["overall"]
    if not overall["n"]:
        return {"publish": False, "reason": "no movements to judge"}
    better = overall["mae_model"] < overall["mae_identity"] and overall["mae_model"] <= overall["mae_rho_only"]
    calibrated = abs(overall["coverage"] - nominal) <= tolerance
    return {"publish": bool(better and calibrated), "better_than_baselines": bool(better), "calibrated": bool(calibrated), "coverage": overall["coverage"]}

