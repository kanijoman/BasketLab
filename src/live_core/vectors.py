"""Runner for the shared test vectors (standard library only).

The same code runs under CPython (pytest, reference) and inside Pyodide on the tablet
(``tests/pyodide``), so both are compared on identical inputs. A suite has:

* ``unit``   - cases ``{"fn", "args"}`` over the pure functions of ``live_core``;
* ``engine`` - a full-game replay at several clock checkpoints (snapshot, alerts and
  analysis are compared through SHA-256 digests of their canonical JSON, plus a readable
  summary to debug a mismatch).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import time
from typing import Any, Callable, Dict, List, Optional

from . import clock, events, four_factors, profiles, rules_fouls, zones
from .advice import AdviceEngine
from .config import RuleConfig
from .engine import LiveEngine
from .package import PreparationPackage
from .recommender import Recommender
from .replay import truncate_doc
from .rules_rotation import fatigue_index


def to_jsonable(obj: Any) -> Any:
    """Dataclasses -> dicts, tuples -> lists (recursively): what crosses the Pyodide boundary."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return to_jsonable(dataclasses.asdict(obj))
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    return obj


def canonical(obj: Any) -> str:
    return json.dumps(to_jsonable(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(obj: Any) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def unwrap_extended_json(obj: Any) -> Any:
    """MongoDB extended JSON ($numberInt, ...) -> plain values."""
    if isinstance(obj, dict):
        if set(obj) == {"$numberInt"} or set(obj) == {"$numberLong"}:
            return int(next(iter(obj.values())))
        if set(obj) == {"$numberDouble"}:
            return float(obj["$numberDouble"])
        if set(obj) == {"$oid"}:
            return obj["$oid"]
        return {k: unwrap_extended_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [unwrap_extended_json(v) for v in obj]
    return obj


# --- unit functions ---------------------------------------------------------------------

def _advice_sequence(a: Dict[str, Any]) -> List[Any]:
    """Run snapshots through one AdviceEngine: exercises dedupe, re-arm and proposals."""
    engine = AdviceEngine(
        own_team_id=a["own"], rival_team_id=a.get("rival"), baselines=a.get("baselines"),
        config=RuleConfig.from_dict(a.get("config")), team_baselines=a.get("team_baselines"),
        rival_baselines=a.get("rival_baselines"), impact_league=a.get("impact_league"),
        zone_ref=a.get("zone_ref"),
    )
    return [engine.evaluate(snap) for snap in a["snapshots"]]


def _four_factors_evaluate(a: Dict[str, Any]) -> Any:
    model = four_factors.FourFactorsModel(a["own"], a["rival"], a.get("baselines"),
                                          RuleConfig.from_dict(a.get("config")))
    return model.evaluate(a["snapshot"])


def _recommender(method: str) -> Callable[[Dict[str, Any]], Any]:
    def call(a: Dict[str, Any]) -> Any:
        rec = Recommender(a["own"], a["table"], RuleConfig.from_dict(a.get("config")))
        if method == "swaps":
            return rec.suggest_swaps(a["snapshot"], a["out"], lever=a.get("lever"))
        return rec.suggest_for_lever(a["snapshot"], a["lever"])
    return call


UNIT_FUNCTIONS: Dict[str, Callable[[Any], Any]] = {
    "clock.elapsed_seconds": lambda a: clock.elapsed_seconds(*a),
    "clock.parse_clock": lambda a: clock.parse_clock(*a),
    "clock.period_and_remaining": lambda a: clock.period_and_remaining(*a),
    "events.parse_line": lambda a: events.parse_line(a[0]),
    "fouls.warn_threshold": lambda a: rules_fouls.warn_threshold(*a),
    "fouls.evaluate": lambda a: rules_fouls.evaluate_player_fouls(*a),
    "fatigue.index": lambda a: fatigue_index(*a),
    "four_factors.possessions": lambda a: four_factors.possessions(*a),
    "four_factors.factors": lambda a: four_factors.factors(*a),
    "four_factors.differentials": lambda a: four_factors.differentials(*a),
    "four_factors.shrink": lambda a: four_factors.shrink(*a),
    "four_factors.evaluate": _four_factors_evaluate,
    "profiles.raw_rates": lambda a: profiles.raw_rates(*a),
    "profiles.shrink_rates": lambda a: profiles.shrink_rates(*a),
    "profiles.z_scores": lambda a: profiles.z_scores(*a),
    "profiles.role_distance": lambda a: profiles.role_distance(*a),
    "profiles.impact_rates": lambda a: profiles.impact_rates(*a),
    "zones.classify_fiba": lambda a: zones.classify_fiba(*a),
    "zones.feb_to_fiba": lambda a: zones.feb_to_fiba(*a),
    "zones.family_totals": lambda a: zones.family_totals(*a),
    "recommender.suggest_swaps": _recommender("swaps"),
    "recommender.suggest_for_lever": _recommender("lever"),
    "advice.sequence": _advice_sequence,
}


def run_unit_vectors(cases: List[Dict[str, Any]]) -> List[Any]:
    return [to_jsonable(UNIT_FUNCTIONS[case["fn"]](case["args"])) for case in cases]


# --- engine vectors ---------------------------------------------------------------------

def run_engine_vectors(spec: Dict[str, Any], game_doc: Dict[str, Any],
                       timings: Optional[List[float]] = None) -> Dict[str, Any]:
    engine = LiveEngine()
    advice = AdviceEngine.from_package(PreparationPackage.loads(spec["package"]))
    out = []
    for period, remaining in spec["checkpoints"]:
        started = time.perf_counter()
        snapshot = engine.update(truncate_doc(game_doc, period, remaining))
        alerts = to_jsonable(advice.evaluate(snapshot))
        analysis = to_jsonable(advice.analyze(snapshot))
        if timings is not None:
            timings.append((time.perf_counter() - started) * 1000)
        out.append({
            "period": period, "remaining": remaining, "elapsed": snapshot["elapsed"],
            "score": snapshot["score"], "alerts": [a["key"] for a in alerts],
            "lever": (analysis.get("four_factors") or {}).get("lever"),
            "digests": {"snapshot": digest(snapshot), "alerts": digest(alerts), "analysis": digest(analysis)},
        })
    return {"checkpoints": out}


def run_suite(suite: Dict[str, Any], game_doc: Dict[str, Any], timings: Optional[List[float]] = None) -> Dict[str, Any]:
    return {"unit": run_unit_vectors(suite["unit"]),
            "engine": run_engine_vectors(suite["engine"], game_doc, timings)}


def run_suite_json(suite_json: str, game_json: str) -> str:
    """Entry point for Pyodide: JSON in, canonical JSON out (adds per-update timings)."""
    timings: List[float] = []
    result = run_suite(json.loads(suite_json), unwrap_extended_json(json.loads(game_json)), timings)
    return json.dumps({"result": to_jsonable(result), "timings_ms": [round(t, 3) for t in timings]},
                      sort_keys=True, ensure_ascii=False)
