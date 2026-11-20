"""The estimator of the equivalence graph (#891, E1b of epic #872): what a player would be expected to do in another competition, with a range.

Model, per axis of the radar (the ``z`` of the percentile of a player in his competition, ``market.equivalence``)::

    z_B = rho * z_A + (theta_B - theta_A) + noise

* ``rho`` is how much of a player's z a second season keeps (his RELIABILITY: measured on the stayers, the players who play two seasons in a row in the same competition, per sex) or, with ``slope="free"``,
  the slope the movers themselves show (a skill that is kept more than its reliability says);
* ``theta`` is the LEVEL of each competition, one per node and axis, fitted by least squares on ALL the movements at once (the equation of each movement is ``theta_B - theta_A = z_B - rho * z_A``). Two
  competitions that nobody crossed are translated anyway if they are connected by others, and the uncertainty of that comes from the covariance of the fit, not from adding steps by hand. A level is known
  up to a constant per connected component: only differences are used;
* the **standard errors are clustered by person** (a player who moves three times is one source of noise, not three), CR1 sandwich;
* an **edge** (a pair of competitions) needs ``MIN_PERSONS`` different persons who moved between them (in either direction); with fewer it does not exist. Men and women are separate graphs.

The answer is always a RANGE: the expected z with an 80 % interval (the noise of a player that the model does not explain plus the uncertainty of the shift of level), and its percentiles. A competition that is
not connected to the other has no translation (``None``). Pure functions (numpy), no I/O. Design and decisions of 20/11/2026: ``docs/evaluaciones/2026-11-20_grafo-equivalencias-891.md``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import NormalDist
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from src.market.equivalence import AXES, Movement, edge_counts

MIN_PERSONS = 40
_NORMAL = NormalDist()
Z80 = _NORMAL.inv_cdf(0.9)                                        # the half width of an 80 % interval in standard deviations
MIN_STAYERS = 30                                                  # stayers a sex needs for a reliability
_SEX = lambda node: node.split("|")[0]                            # noqa: E731


@dataclass
class Fit:
    """One sex: its nodes, its connected components and, per axis, the levels, the covariance of the parameters (levels first, then the slope if it is free) and the noise."""
    nodes: List[str]
    component: Dict[str, int]
    theta: np.ndarray                  # (axes, nodes)
    cov: np.ndarray                    # (axes, parameters, parameters)
    sigma: np.ndarray                  # (axes,)
    slope: np.ndarray                  # (axes,): rho, or the fitted slope
    free: bool


@dataclass
class Model:
    fits: Dict[str, Fit] = field(default_factory=dict)
    rho: Dict[str, List[float]] = field(default_factory=dict)          # per sex: the reliability per axis (or the fitted slope)
    edges: Dict[Tuple[str, str], Dict[str, int]] = field(default_factory=dict)
    slope_mode: str = "reliability"


def _correlation(pairs: Sequence[Tuple[float, float]]) -> Optional[float]:
    a = np.asarray(pairs, dtype=float)
    if len(a) < MIN_STAYERS or a[:, 0].std() == 0 or a[:, 1].std() == 0:
        return None
    return float(np.corrcoef(a[:, 0], a[:, 1])[0, 1])


def reliability(stayers: Iterable[Movement]) -> Dict[str, List[float]]:
    """``{sex: [rho per axis]}`` from the stayers: the correlation of the z of a player between two seasons in a row in the same competition. A sex whose stayers are too few or have no variation in an axis has none."""
    by_sex: Dict[str, List[Movement]] = {}
    for s in stayers:
        by_sex.setdefault(_SEX(s.from_node), []).append(s)
    out: Dict[str, List[float]] = {}
    for sex, rows in by_sex.items():
        values = [_correlation([(s.z_from[i], s.z_to[i]) for s in rows]) for i in range(len(AXES))]
        if all(v is not None for v in values):
            out[sex] = [float(v) for v in values]
    return out


def _components(nodes: List[str], edges: Iterable[Tuple[str, str]]) -> Dict[str, int]:
    parent = {n: n for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        parent[find(a)] = find(b)
    roots = sorted({find(n) for n in nodes})
    return {n: roots.index(find(n)) for n in nodes}


def _solve(rows: List[Movement], nodes: List[str], axis: int, rho: Optional[float], cluster: bool) -> Tuple[np.ndarray, np.ndarray, float, float]:
    """The levels (and the slope when ``rho`` is None) of one axis by least squares, their covariance, the noise and the slope used."""
    index = {n: i for i, n in enumerate(nodes)}
    free = rho is None
    x = np.zeros((len(rows), len(nodes) + (1 if free else 0)))
    y = np.zeros(len(rows))
    for r, m in enumerate(rows):
        x[r, index[m.to_node]], x[r, index[m.from_node]] = 1.0, -1.0
        if free:
            x[r, -1] = m.z_from[axis]
            y[r] = m.z_to[axis]
        else:
            y[r] = m.z_to[axis] - rho * m.z_from[axis]
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    rank = np.linalg.matrix_rank(x)
    dof = max(len(rows) - rank, 1)
    sigma2 = float(resid @ resid) / dof
    bread = np.linalg.pinv(x.T @ x)
    if not cluster:
        return beta, sigma2 * bread, sigma2 ** 0.5, float(beta[-1]) if free else float(rho)
    groups: Dict[str, np.ndarray] = {}
    for r, m in enumerate(rows):
        groups.setdefault(m.person, np.zeros(x.shape[1]))
        groups[m.person] += x[r] * resid[r]
    meat = sum(np.outer(g, g) for g in groups.values())
    clusters = len(groups)
    scale = (clusters / max(clusters - 1, 1)) * ((len(rows) - 1) / max(len(rows) - rank, 1))
    return beta, scale * bread @ meat @ bread, sigma2 ** 0.5, float(beta[-1]) if free else float(rho)


def _fit_sex(rows: List[Movement], rho: Optional[List[float]], cluster: bool) -> Optional[Fit]:
    counts = edge_counts(rows)
    kept = {key for key, edge in counts.items() if edge["persons"] >= MIN_PERSONS}
    rows = [m for m in rows if tuple(sorted((m.from_node, m.to_node))) in kept]
    if not rows:
        return None
    nodes = sorted({n for key in kept for n in key})
    component = _components(nodes, kept)
    free = rho is None
    theta, cov, sigma, slope = [], [], [], []
    for axis in range(len(AXES)):
        beta, covariance, noise, used = _solve(rows, nodes, axis, None if free else rho[axis], cluster)
        levels = beta[: len(nodes)].copy()
        for c in set(component.values()):                              # a level is known up to a constant per component: centre it
            members = [i for i, n in enumerate(nodes) if component[n] == c]
            levels[members] -= levels[members].mean()
        theta.append(levels)
        cov.append(covariance)
        sigma.append(noise)
        slope.append(used)
    return Fit(nodes, component, np.array(theta), np.array(cov), np.array(sigma), np.array(slope), free)


def fit(moves: Iterable[Movement], stay: Iterable[Movement], slope: str = "reliability", cluster: bool = True) -> Model:
    """The model of every sex that has movements. ``slope`` is ``"reliability"`` (rho from the stayers) or ``"free"`` (the slope of the movers); ``cluster`` clusters the standard errors by person."""
    if slope not in ("reliability", "free"):
        raise ValueError("slope must be 'reliability' or 'free'")
    moves, stay = list(moves), list(stay)
    rho = reliability(stay)
    model = Model(slope_mode=slope, edges=edge_counts(moves))
    by_sex: Dict[str, List[Movement]] = {}
    for m in moves:
        by_sex.setdefault(_SEX(m.from_node), []).append(m)
    for sex, rows in sorted(by_sex.items()):
        if slope == "reliability" and sex not in rho:
            continue
        found = _fit_sex(rows, None if slope == "free" else rho[sex], cluster)
        if found:
            model.fits[sex] = found
            model.rho[sex] = [float(v) for v in found.slope]
    return model


def translate(model: Model, from_node: str, to_node: str, z_from: Sequence[float]) -> Optional[List[Dict[str, Any]]]:
    """For a player with ``z_from`` (one per axis) in ``from_node``: per axis the expected z in ``to_node`` with its 80 % interval (``lo`` and ``hi``), the percentiles of the three, the noise of a player
    (``sd``) and the uncertainty of the shift of level alone (``se_level``). ``None`` if either competition is not in the graph, they are of different sexes or they are not connected."""
    sex = _SEX(from_node)
    found = model.fits.get(sex)
    if not found or _SEX(to_node) != sex or from_node not in found.nodes or to_node not in found.nodes or found.component[from_node] != found.component[to_node]:
        return None
    a, b = found.nodes.index(from_node), found.nodes.index(to_node)
    out = []
    for i in range(len(AXES)):
        shift = float(found.theta[i][b] - found.theta[i][a])
        d = np.zeros(found.cov.shape[1])
        d[b], d[a] = 1.0, -1.0
        level_var = float(d @ found.cov[i] @ d)
        if found.free:
            d[-1] = float(z_from[i])
        param_var = float(d @ found.cov[i] @ d)
        mean = float(found.slope[i]) * float(z_from[i]) + shift
        sd = (float(found.sigma[i]) ** 2 + param_var) ** 0.5
        lo, hi = mean - Z80 * sd, mean + Z80 * sd
        out.append({"mean": mean, "lo": lo, "hi": hi, "sd": sd, "se_level": max(level_var, 0.0) ** 0.5,
                    "pct_lo": 100 * _NORMAL.cdf(lo), "pct_mean": 100 * _NORMAL.cdf(mean), "pct_hi": 100 * _NORMAL.cdf(hi)})
    return out
