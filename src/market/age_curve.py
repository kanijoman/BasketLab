"""The age curve of the projection (#892, E2 of epic #872): how much a player's z changes from one season to the next beyond what the reliability says, as a function of his age.

Model, per sex and axis of the radar (``market.equivalence``)::

    z_next = rho * z + effect(age) + noise

fitted on the players who STAY in a competition (so the level of the competition is not in it), with a fixed effect per age: ``rho`` is the slope within each age and ``effect(age)`` the mean of what the
reliability does not explain, smoothed over the neighbouring ages and pulled to zero where few players have that age (``SHRINK``): an age with three players is not a trend. The age is the one of the season
the player leaves (``season - birth year``, the birth being the one his rows say most often). The answer is always a range (80 %). Validated a season out at a time against "only shrink by the reliability".
Pure functions, no I/O. Design and decisions: ``docs/evaluaciones/``.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from src.market.equivalence import AXES, Observation, person_of
from src.market.equivalence_model import Z80

AGE_MIN, AGE_MAX = 16, 36                                       # the ages outside use the edge of the curve
SHRINK = 30.0                                                   # players an age needs for its effect to count for half
_BIRTH = re.compile(r"^(\d{4})-\d{2}-\d{2}$")


@dataclass(frozen=True)
class Pair:
    person: str
    node: str
    season_from: int
    season_to: int
    age: int
    z_from: Tuple[float, ...]
    z_to: Tuple[float, ...]


@dataclass
class AgeModel:
    rho: Dict[str, List[float]] = field(default_factory=dict)
    effect: Dict[str, List[Dict[int, float]]] = field(default_factory=dict)       # sex -> axis -> age -> effect in z
    sigma: Dict[str, List[float]] = field(default_factory=dict)

    def effect_at(self, sex: str, axis: int, age: int) -> float:
        return self.effect[sex][axis][min(max(age, AGE_MIN), AGE_MAX)]


def births_of(rows: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
    """``{person: year of birth}``: the year his rows say most often (a tie goes to the earlier), and the FEB person an external player is linked to is the same person. No birth, no entry."""
    votes: Dict[str, Counter] = {}
    for row in rows:
        found = _BIRTH.match(str(row.get("birth") or ""))
        if found:
            votes.setdefault(person_of(row), Counter())[int(found.group(1))] += 1
    return {p: sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for p, c in sorted(votes.items())}


def pairs(obs: Iterable[Observation], births: Mapping[str, int], horizon: int = 1) -> List[Pair]:
    """The same person in the same competition ``horizon`` seasons later, with the age he had when he left. Someone who changed competition is a translation (E1), not a stay."""
    obs = list(obs)
    by_key = {(o.person, o.node, o.season): o for o in obs}
    out = []
    for o in sorted(obs, key=lambda o: (o.person, o.node, o.season)):
        later = by_key.get((o.person, o.node, o.season + horizon))
        if later is not None and o.person in births:
            out.append(Pair(o.person, o.node, o.season, later.season, o.season - births[o.person], o.z, later.z))
    return out


AGE_GROUPS = ("<=21", "22-29", "30+")


def age_group(age: int) -> str:
    return "<=21" if age <= 21 else "22-29" if age <= 29 else "30+"


def _sex(node: str) -> str:
    return node.split("|")[0]


def _fit_axis(rows: Sequence[Pair], axis: int, shrink: float) -> Tuple[float, Dict[int, float], float]:
    by_age: Dict[int, List[Pair]] = {}
    for p in rows:
        by_age.setdefault(min(max(p.age, AGE_MIN), AGE_MAX), []).append(p)
    mean = lambda values: sum(values) / len(values)                                    # noqa: E731
    num = den = 0.0
    for group in by_age.values():                                                      # the slope within each age
        mx, my = mean([p.z_from[axis] for p in group]), mean([p.z_to[axis] for p in group])
        num += sum((p.z_from[axis] - mx) * (p.z_to[axis] - my) for p in group)
        den += sum((p.z_from[axis] - mx) ** 2 for p in group)
    rho = num / den if den else 0.0
    sums = {a: (sum(p.z_to[axis] - rho * p.z_from[axis] for p in g), len(g)) for a, g in by_age.items()}
    effect = {}
    for age in range(AGE_MIN, AGE_MAX + 1):                                            # smoothed over the neighbours, then pulled to zero where it is thin
        total = count = 0.0
        for a in (age - 1, age, age + 1):
            if a in sums:
                total, count = total + sums[a][0], count + sums[a][1]
        effect[age] = (total / count) * (count / (count + shrink)) if count else 0.0
    resid = [p.z_to[axis] - rho * p.z_from[axis] - effect[min(max(p.age, AGE_MIN), AGE_MAX)] for p in rows]
    return rho, effect, (sum(r * r for r in resid) / max(len(resid), 1)) ** 0.5


def fit(found: Iterable[Pair], shrink: float = SHRINK) -> AgeModel:
    """The model of every sex that has pairs. The order of the pairs does not change the answer."""
    by_sex: Dict[str, List[Pair]] = {}
    for p in sorted(found, key=lambda p: (p.person, p.node, p.season_from, p.season_to)):
        by_sex.setdefault(_sex(p.node), []).append(p)
    model = AgeModel()
    for sex, rows in sorted(by_sex.items()):
        parts = [_fit_axis(rows, i, shrink) for i in range(len(AXES))]
        model.rho[sex], model.effect[sex], model.sigma[sex] = [r for r, _, _ in parts], [e for _, e, _ in parts], [s for _, _, s in parts]
    return model


def project(model: AgeModel, sex: str, z: Sequence[float], age: int) -> Optional[List[Dict[str, float]]]:
    """The expected z next season, per axis, with the 80 % range, for a player of ``sex`` with ``z`` and ``age``; ``None`` when the model does not know the sex."""
    if sex not in model.rho:
        return None
    out = []
    for i in range(len(AXES)):
        mean = model.rho[sex][i] * float(z[i]) + model.effect_at(sex, i, age)
        out.append({"mean": mean, "lo": mean - Z80 * model.sigma[sex][i], "hi": mean + Z80 * model.sigma[sex][i], "sd": model.sigma[sex][i]})
    return out


def leave_one_season_out(found: Iterable[Pair], shrink: float = SHRINK) -> Dict[str, Any]:
    """Each season predicted by a model fitted WITHOUT it (no pair with it on either side): the error of the model against only shrinking by the reliability, and the coverage and width of its range."""
    found = list(found)
    acc: Dict[str, List[float]] = {"model": [], "rho_only": [], "hit": [], "width": []}
    groups: Dict[str, Dict[str, List[float]]] = {g: {"model": [], "rho_only": []} for g in AGE_GROUPS}
    for season in sorted({p.season_to for p in found}):
        model = fit([p for p in found if p.season_from != season and p.season_to != season], shrink)
        for p in (p for p in found if p.season_to == season):
            out = project(model, _sex(p.node), p.z_from, p.age)
            if out is None:
                continue
            for i, r in enumerate(out):
                acc["model"].append(abs(p.z_to[i] - r["mean"]))
                acc["rho_only"].append(abs(p.z_to[i] - model.rho[_sex(p.node)][i] * p.z_from[i]))
                acc["hit"].append(float(r["lo"] <= p.z_to[i] <= r["hi"]))
                acc["width"].append(r["hi"] - r["lo"])
                group = groups[age_group(p.age)]
                group["model"].append(acc["model"][-1])
                group["rho_only"].append(acc["rho_only"][-1])
    mean = lambda values: (sum(values) / len(values)) if values else None            # noqa: E731
    return {"overall": {"n": len(acc["hit"]), "mae_model": mean(acc["model"]), "mae_rho_only": mean(acc["rho_only"]), "coverage": mean(acc["hit"]), "mean_width": mean(acc["width"])},
            "per_age_group": {g: {"n": len(v["model"]), "mae_model": mean(v["model"]), "mae_rho_only": mean(v["rho_only"])} for g, v in groups.items()}}
