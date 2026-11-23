"""The document of the formation index (#893, E3b): what ``talent-data`` publishes as ``formation`` and how the estimate of a player of the formation is rebuilt from it and from the ``equivalences``.

``build_document(rows, competitions)`` fits the graph of levels (``equivalence_model``) and the index (``formation``) on the published rows and writes per sex the coefficients and the noise, the groups it can
speak of (enough players who made it to the senior game), a validation a promotion out at a time and ``usable``: the range is shown only if the index beats the mean of those who made it and its 80 % range holds.
``estimate_from_documents`` is the reference of what the browser does (the same single estimate as ``formation.project``): the levels of the senior competitions come from the ``equivalences`` document.
**Conditional on getting there**: the estimate says what he would be in the senior game IF he gets there. Pure functions, no I/O.
"""
from __future__ import annotations

from collections import Counter
from statistics import NormalDist
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from src.market.equivalence import AXES, Observation, movements, observations, stayers
from src.market.equivalence_model import Z80, Model, fit as fit_graph, fit_observations
from src.market.formation import FormationObs, Levels, fit, formation_observations, leave_one_season_out, pairs

FORMAT = 1
DECIMALS = 5
MIN_GROUP_PAIRS = 100                                          # players of a group who made it a group needs for the index to speak of it
_NORMAL = NormalDist()


def levels_of(model: Model) -> Levels:
    """``node -> level per axis`` of a graph of levels, ``None`` for a competition it does not know."""
    def levels(node: str) -> Optional[Sequence[float]]:
        found = model.fits.get(node.split("|")[0])
        return None if not found or node not in found.nodes else tuple(float(v) for v in found.theta[:, found.nodes.index(node)])
    return levels


def levels_without(senior: Sequence[Observation]):
    """``season -> levels`` of the graph fitted without any movement or stayer that has that season on either side (what the validation needs)."""
    moves, stay = movements(senior), stayers(senior)
    return lambda season: levels_of(fit_graph([m for m in moves if season not in (m.from_season, m.to_season)], [s for s in stay if season not in (s.from_season, s.to_season)]))


def _round(values: Iterable[float]) -> List[float]:
    return [round(float(v), DECIMALS) for v in values]


def build_document(rows: Iterable[Mapping[str, Any]], competitions: Mapping[str, Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """The document, or ``None`` when there is no formation, no graph or nobody who made it (nothing to publish)."""
    rows = list(rows)
    senior, formation = observations(rows, competitions), formation_observations(rows, competitions)
    if not senior or not formation:
        return None
    graph = fit_observations(senior)
    found = pairs(formation, senior, levels_of(graph)) if graph.fits else []
    counts = Counter(p.group for p in found)
    groups = sorted(g for g, n in counts.items() if n >= MIN_GROUP_PAIRS)
    if not groups:
        return None
    model = fit([p for p in found if p.group in groups])
    study = leave_one_season_out(formation, senior, levels_without(senior))
    o = study["overall"]
    better = o["n"] > 0 and o["mae_model"] < o["mae_mean"]
    publish = bool(better and abs(o["coverage"] - 0.8) <= 0.05)
    validation = {"n": o["n"], **{k: (None if o[k] is None else round(float(o[k]), 4)) for k in ("mae_model", "mae_mean", "coverage", "mean_width")}, "publish": publish}
    sexes = {sex: {"coef": [_round(c) for c in model.coef[sex]], "sigma": _round(model.sigma[sex]), "n": sum(1 for p in found if p.sex == sex and p.group in groups)} for sex in sorted(model.coef)}
    return {"format": FORMAT, "axes": list(AXES), "groups": groups, "sexes": sexes, "validation": validation, "usable": publish}


def estimate_from_documents(document: Mapping[str, Any], equivalences: Mapping[str, Any], history: Sequence[FormationObs], to_node: str) -> Optional[List[Dict[str, Any]]]:
    """What a player of the formation would be in the senior competition ``to_node`` IF he gets there, from his latest formation season: per axis the expected z with the 80 % range and its percentiles. ``None`` without
    formation, for a group or sex the index does not speak of or a competition the graph does not know."""
    if not history:
        return None
    last = max(history, key=lambda o: (o.season, o.minutes, o.group))
    part, eq = document["sexes"].get(last.sex), equivalences["sexes"].get(last.sex)
    if last.group not in document["groups"] or not part or not eq or to_node.split("|")[0] != last.sex or to_node not in eq["nodes"]:
        return None
    at = eq["nodes"].index(to_node)
    out = []
    for i in range(len(document["axes"])):
        a, b, g = part["coef"][i]
        mean = a + b * float(last.z[i]) + g * float(last.group == "U18") + eq["theta"][i][at]
        sd = part["sigma"][i]
        lo, hi = mean - Z80 * sd, mean + Z80 * sd
        out.append({"mean": mean, "lo": lo, "hi": hi, "sd": sd, "pct_lo": 100 * _NORMAL.cdf(lo), "pct_mean": 100 * _NORMAL.cdf(mean), "pct_hi": 100 * _NORMAL.cdf(hi), "group": last.group, "season": last.season})
    return out
