"""The registry of the team formulas (#1153): ``config/formulas.json`` defines every rate once; this module evaluates it on a dict of counters (``evaluate``), builds the equivalent Mongo
expression for the pipelines (``mongo_expression``) and the browser reads the same file (``frontend/src/lib/formulas.ts``). Before it, the same column was computed in five ways: TOV% was
TOV / possessions in the team table and TOV / (FGA + 0.44 FTA + TOV) in Multifase and Live; ORB% divided by the own or the rival's rebounds; DER by the own or the rival's possessions.

A rate with an empty denominator is ``None`` here and ``0`` in a Mongo expression (``safe_divide``, the convention of the tables); the consumers that show «-» map the ``None``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

_PATH = Path(__file__).resolve().parents[2] / "config" / "formulas.json"
_DOC = json.loads(_PATH.read_text(encoding="utf-8"))
COUNTERS: List[str] = list(_DOC["counters"])
FORMULAS: Dict[str, Dict[str, Any]] = dict(_DOC["formulas"])


def _combo(terms: Mapping[str, float], counters: Mapping[str, float]) -> float:
    total = 0.0
    for name, coefficient in terms.items():
        total += coefficient * counters[name]                       # a missing counter is a KeyError, never a silent zero
    return total


def evaluate(name: str, counters: Mapping[str, float]) -> Optional[float]:
    """The value of the formula ``name`` for ``counters``; ``None`` when a denominator is 0."""
    formula = FORMULAS[name]
    if "minus" in formula:
        left, right = (evaluate(part, counters) for part in formula["minus"])
        return None if left is None or right is None else left - right
    denominator = _combo(formula["den"], counters)
    if denominator == 0:
        return None
    return _combo(formula["num"], counters) / denominator * formula["scale"]


def evaluate_all(counters: Mapping[str, float]) -> Dict[str, Optional[float]]:
    return {name: evaluate(name, counters) for name in FORMULAS}


def _mongo_combo(terms: Mapping[str, float], fields: Mapping[str, Any]) -> Any:
    parts = [fields[name] if coefficient == 1 else {"$multiply": [coefficient, fields[name]]} for name, coefficient in terms.items()]
    return parts[0] if len(parts) == 1 else {"$add": parts}


def mongo_expression(name: str, fields: Mapping[str, Any], empty: Any = 0) -> Dict[str, Any]:
    """The Mongo expression of the formula ``name``: ``fields`` maps each counter to the expression that holds it (``"$total_possessions"``...). An empty denominator gives ``empty``:
    0 for the tables (``safe_divide``), ``None`` for the per-game fields the consistency skips."""
    formula = FORMULAS[name]
    if "minus" in formula:
        left, right = formula["minus"]
        ready = {"$and": [{"$ne": [_denominator(part, fields), 0]} for part in formula["minus"]]}
        return {"$cond": [ready, {"$subtract": [mongo_expression(left, fields, empty), mongo_expression(right, fields, empty)]}, empty]}
    denominator = _mongo_combo(formula["den"], fields)
    return {"$cond": [{"$eq": [denominator, 0]}, empty, {"$multiply": [{"$divide": [_mongo_combo(formula["num"], fields), denominator]}, formula["scale"]]}]}


def _denominator(name: str, fields: Mapping[str, Any]) -> Any:
    return _mongo_combo(FORMULAS[name]["den"], fields)
