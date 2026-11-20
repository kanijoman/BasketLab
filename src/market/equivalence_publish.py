"""The document of the equivalence graph (#891, E1c of epic #872): what ``talent-data`` publishes as ``equivalences`` and how an estimate is rebuilt from it.

``build_document(rows, competitions)`` fits the model (``equivalence_model.fit_observations``) on the published rows and writes per sex the levels of the competitions (one per axis), their covariance, the
noise and the reliability of an origin of one season and of two, plus the edges that exist and a validation (a season out at a time, ``equivalence_study``) with the ``usable`` flag: the range is shown only
if the model beats not translating and its 80 % interval holds. ``estimate_from_document`` is the reference of what the browser does with it (E4): the SAME single estimate as ``equivalence_model.estimate``,
from the numbers of the document alone. Pure functions, no I/O.
"""
from __future__ import annotations

from statistics import NormalDist
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from src.market.equivalence import AXES, Observation, movements, observations, stayers
from src.market.equivalence_model import MIN_PERSONS, Z80, fit_observations, origin
from src.market.equivalence_study import leave_one_season_out, verdict

FORMAT = 1
DECIMALS = 5
_NORMAL = NormalDist()


def _round(value: Any) -> Any:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        return [_round(v) for v in value]
    return round(float(value), DECIMALS)


def _sex_part(found: Any, rho: Sequence[float], two: Optional[Mapping[str, Sequence[float]]]) -> Dict[str, Any]:
    n = len(found.nodes)
    return {"nodes": list(found.nodes), "component": [found.component[x] for x in found.nodes], "rho": _round(rho), "sigma": _round(found.sigma),
            "theta": _round(found.theta), "cov": _round([c[:n, :n].tolist() for c in found.cov]),
            "two": {"rho": _round(two["rho"]), "sigma": _round(two["sigma"])} if two else None}


def _validation(obs: List[Observation]) -> Dict[str, Any]:
    study = leave_one_season_out(movements(obs), stayers(obs))
    overall, call = study["overall"], verdict(study)
    keys = ("n", "mae_identity", "mae_rho_only", "mae_model", "coverage", "mean_width")
    return {**{k: (None if overall.get(k) is None else (overall[k] if k == "n" else round(float(overall[k]), 4))) for k in keys},
            "seasons": sorted(study["per_season"]) if "per_season" in study else [], "publish": bool(call["publish"])}


def build_document(rows: Iterable[Mapping[str, Any]], competitions: Mapping[str, Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """The document, or ``None`` when no sex has a graph (nothing to publish). ``rows`` carry ``comp`` (the key of their competition), ``competitions`` is ``{key: entry}`` of the manifest."""
    obs = observations(rows, competitions)
    if not obs:
        return None
    model = fit_observations(obs)
    if not model.fits:
        return None
    edges = sorted(({"from": a, "to": b, "persons": e["persons"], "moves": e["up"] + e["down"] + e["unranked"]} for (a, b), e in model.edges.items() if e["persons"] >= MIN_PERSONS),
                   key=lambda e: (e["from"], e["to"]))
    validation = _validation(obs)
    return {"format": FORMAT, "axes": list(AXES), "sexes": {sex: _sex_part(found, model.rho[sex], model.history.get(sex)) for sex, found in sorted(model.fits.items())},
            "edges": edges, "validation": validation, "usable": validation["publish"]}


def estimate_from_document(document: Mapping[str, Any], history: Sequence[Observation], to_node: str) -> Optional[List[Dict[str, Any]]]:
    """The estimate of ``history`` in ``to_node`` from the document alone (what the browser does): the same one as ``equivalence_model.estimate``, to the rounding of the file."""
    start = origin(history)
    if start is None:
        return None
    last, z, seasons = start
    sex = last.node.split("|")[0]
    part = document["sexes"].get(sex)
    if not part or to_node.split("|")[0] != sex or last.node not in part["nodes"] or to_node not in part["nodes"]:
        return None
    a, b = part["nodes"].index(last.node), part["nodes"].index(to_node)
    if part["component"][a] != part["component"][b]:
        return None
    two = part["two"] if seasons == 2 else None
    rho, sigma = (two["rho"], two["sigma"]) if two else (part["rho"], part["sigma"])
    out = []
    for i in range(len(document["axes"])):
        cov = part["cov"][i]
        variance = max(cov[b][b] + cov[a][a] - 2 * cov[a][b], 0.0)
        mean = rho[i] * float(z[i]) + part["theta"][i][b] - part["theta"][i][a]
        sd = (sigma[i] ** 2 + variance) ** 0.5
        lo, hi = mean - Z80 * sd, mean + Z80 * sd
        out.append({"mean": mean, "lo": lo, "hi": hi, "sd": sd, "se_level": variance ** 0.5,
                    "pct_lo": 100 * _NORMAL.cdf(lo), "pct_mean": 100 * _NORMAL.cdf(mean), "pct_hi": 100 * _NORMAL.cdf(hi),
                    "seasons": seasons, "from_node": last.node})
    return out
