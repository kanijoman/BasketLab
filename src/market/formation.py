"""The formation index (#893, E3 of epic #872): what a player of the formation (U12 to U18) is expected to be in the senior game IF he gets there, with a range.

Model, per sex and axis of the radar (``market.equivalence``)::

    z_senior = a + b * z_formation + g * [U18] + noise

where ``z_senior`` is the z of his first senior season (the next one) put on the COMMON scale of the equivalence graph: minus the level ``theta`` of his competition (``equivalence_model``), so the projection
is translated to any senior competition by adding that level back. Only players who reach the senior game with enough minutes are seen: **the index is conditional on getting there** and says so. A ridge keeps
the coefficients from chasing noise. Validated a PROMOTION (season) out at a time: the levels and the fit are made without the season that is predicted, against «the mean of those who made it».
Age adds nothing measurable once the group is known (E2, ``docs/evaluaciones/2026-11-20_curva-de-edad-892.md``), so it is not in the model. FEB only: the formation of FBCYL has its own scale (not linked to this one).
Pure functions, no I/O. Results: ``docs/evaluaciones/``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from src.market.equivalence import AXES, Observation, _z_row, person_of
from src.market.equivalence_model import Z80

RIDGE = 1.0
Levels = Callable[[str], Optional[Sequence[float]]]               # node -> level (theta) per axis, or None when the graph does not know it
_SENIOR_GROUP = {"U18"}                                            # the group that gets the coefficient ``g``


@dataclass(frozen=True)
class FormationObs:
    person: str
    season: int
    group: str                                                     # U12, U14, U16 or U18
    sex: str
    minutes: int
    z: Tuple[float, ...]


@dataclass(frozen=True)
class Pair:
    person: str
    season_from: int
    season_to: int
    group: str
    sex: str
    z_formation: Tuple[float, ...]
    z_senior: Tuple[float, ...]                                    # on the common scale: his z minus the level of his competition


@dataclass
class FormationModel:
    coef: Dict[str, List[Tuple[float, float, float]]] = field(default_factory=dict)       # sex -> axis -> (a, b, g)
    sigma: Dict[str, List[float]] = field(default_factory=dict)
    mean: Dict[str, List[float]] = field(default_factory=dict)                               # the baseline: the mean of those who made it

    @property
    def slope(self) -> Dict[str, List[float]]:
        return {sex: [c[1] for c in axes] for sex, axes in self.coef.items()}


def formation_observations(rows: Iterable[Mapping[str, Any]], competitions: Mapping[str, Mapping[str, Any]]) -> List[FormationObs]:
    """One observation per person, season, age group and sex from the rows of the formation of FEB: the row with more minutes, only those that played enough and have the eight percentiles."""
    best: Dict[Tuple[str, int, str, str], FormationObs] = {}
    for row in rows:
        entry = competitions.get(row.get("comp")) or {}
        z = _z_row(row)
        if entry.get("category") != "formacion" or entry.get("league") != "feb" or entry.get("gender") not in ("M", "F") or not entry.get("age_group") or not row.get("eligible") or z is None:
            continue
        o = FormationObs(person_of(row), int(entry["season"]), entry["age_group"], entry["gender"], int(row.get("minutes") or 0), z)
        key = (o.person, o.season, o.group, o.sex)
        if key not in best or (o.minutes, str(row.get("person_id"))) > (best[key].minutes, ""):
            best[key] = o
    return [best[k] for k in sorted(best)]


def pairs(formation: Iterable[FormationObs], senior: Iterable[Observation], levels: Levels) -> List[Pair]:
    """Each formation observation with the first senior season right after it (the one with more minutes if there are two) of the same sex, on the common scale. Without a senior season or a level, no pair."""
    by_person: Dict[Tuple[str, int], List[Observation]] = {}
    for o in senior:
        by_person.setdefault((o.person, o.season), []).append(o)
    out = []
    for f in sorted(formation, key=lambda f: (f.person, f.season, f.group, f.sex)):
        for o in sorted(by_person.get((f.person, f.season + 1), []), key=lambda o: (-o.minutes, o.node)):
            theta = levels(o.node)
            if o.node.split("|")[0] == f.sex and theta is not None:
                out.append(Pair(f.person, f.season, o.season, f.group, f.sex, f.z, tuple(v - t for v, t in zip(o.z, theta))))
                break
    return out


def fit(found: Iterable[Pair], ridge: float = RIDGE) -> FormationModel:
    """The model of every sex that has pairs; the order of the pairs does not change the answer."""
    by_sex: Dict[str, List[Pair]] = {}
    for p in sorted(found, key=lambda p: (p.person, p.season_from, p.group)):
        by_sex.setdefault(p.sex, []).append(p)
    model = FormationModel()
    for sex, rows in sorted(by_sex.items()):
        y = np.array([p.z_senior for p in rows])
        coefs, sigmas = [], []
        for axis in range(len(AXES)):
            x = np.column_stack([np.ones(len(rows)), [p.z_formation[axis] for p in rows], [float(p.group in _SENIOR_GROUP) for p in rows]])
            penalty = ridge * np.diag([0.0, 1.0, 1.0])                      # the intercept is not shrunk
            w = np.linalg.solve(x.T @ x + penalty, x.T @ y[:, axis])
            coefs.append((float(w[0]), float(w[1]), float(w[2])))
            sigmas.append(float(np.sqrt(np.mean((y[:, axis] - x @ w) ** 2))))
        model.coef[sex], model.sigma[sex], model.mean[sex] = coefs, sigmas, [float(v) for v in y.mean(axis=0)]
    return model


def project(model: FormationModel, sex: str, z: Sequence[float], group: str, theta: Sequence[float]) -> Optional[List[Dict[str, float]]]:
    """What he would be in a senior competition of level ``theta`` (the level per axis, ``equivalence_model``) if he gets there: per axis the expected z with the 80 % range; ``None`` for a sex the model does not know."""
    if sex not in model.coef:
        return None
    out = []
    for i, (a, b, g) in enumerate(model.coef[sex]):
        mean = a + b * float(z[i]) + g * float(group in _SENIOR_GROUP) + float(theta[i])
        sd = model.sigma[sex][i]
        out.append({"mean": mean, "lo": mean - Z80 * sd, "hi": mean + Z80 * sd, "sd": sd})
    return out


def leave_one_season_out(formation: Iterable[FormationObs], senior: Iterable[Observation], levels_without: Callable[[int], Levels], ridge: float = RIDGE) -> Dict[str, Any]:
    """Each promotion (the season they reach the senior game) predicted by a model made WITHOUT it: ``levels_without(season)`` gives the levels of the graph fitted without that season and the pairs and the fit
    use no pair that has it on either side. The error is on the common scale, against the mean of those who made it; the coverage and width are those of the 80 % range."""
    formation, senior = list(formation), list(senior)
    acc: Dict[str, List[float]] = {"model": [], "mean": [], "hit": [], "width": []}
    groups: Dict[str, Dict[str, List[float]]] = {}
    zero = (0.0,) * len(AXES)
    for season in sorted({o.season for o in senior}):
        levels = levels_without(season)
        found = pairs(formation, senior, levels)
        model = fit([p for p in found if p.season_from != season and p.season_to != season], ridge)
        for p in (p for p in found if p.season_to == season):
            out = project(model, p.sex, p.z_formation, p.group, zero)
            if out is None:
                continue
            for i, r in enumerate(out):
                acc["model"].append(abs(p.z_senior[i] - r["mean"]))
                acc["mean"].append(abs(p.z_senior[i] - model.mean[p.sex][i]))
                acc["hit"].append(float(r["lo"] <= p.z_senior[i] <= r["hi"]))
                acc["width"].append(r["hi"] - r["lo"])
                g = groups.setdefault(p.group, {"model": [], "mean": []})
                g["model"].append(acc["model"][-1])
                g["mean"].append(acc["mean"][-1])
    mean = lambda values: (sum(values) / len(values)) if values else None            # noqa: E731
    return {"overall": {"n": len(acc["hit"]), "mae_model": mean(acc["model"]), "mae_mean": mean(acc["mean"]), "coverage": mean(acc["hit"]), "mean_width": mean(acc["width"])},
            "per_group": {g: {"n": len(v["model"]), "mae_model": mean(v["model"]), "mae_mean": mean(v["mean"])} for g, v in sorted(groups.items())}}
