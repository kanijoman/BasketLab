"""Per-rule metrics of the rule evaluator, over the alert rows of ONE configuration.

Rows are what ``rule_evaluation`` produces for every alert (rule id, key, severity, ``elapsed`` / ``shown`` seconds,
the coach's ``label`` / ``delay``, the ``outcome``, and the staff's ``verdict`` when feedback was supplied);
``team_games`` has one entry per team-game evaluated (duration and own timeouts). Everything is plain data.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .eval_labels import ACTION_FOR

DUPLICATE_WINDOW_S = 600
SEVERITIES = ("critical", "warning", "info")
LABELS = ("seguida", "anticipada", "tarde", "no")
VERDICTS = ("seguida", "descartada", "ya_hecho")
_SUBJECT_FIELDS = ("player_id", "metric", "lever", "zone", "pf", "period")


def _mean(values: Iterable[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _share(count: int, total: int) -> Optional[float]:
    return count / total if total else None


def _subject(row: Dict[str, Any]) -> Tuple[Any, ...]:
    evidence = row.get("evidence") or {}
    return tuple(evidence.get(f) for f in _SUBJECT_FIELDS)


def count_duplicates(rows: Sequence[Dict[str, Any]]) -> int:
    """Alerts repeating one that was shown within ten minutes: same rule, subject and severity, in the same game."""
    last: Dict[Tuple[Any, ...], int] = {}
    duplicates = 0
    for r in sorted(rows, key=lambda r: (r["game"], r["team"], r["elapsed"])):
        key = (r["game"], r["team"], r["id"], r["severity"], _subject(r))
        if key in last and r["elapsed"] - last[key] <= DUPLICATE_WINDOW_S:
            duplicates += 1
        last[key] = r["elapsed"]
    return duplicates


def _volume(rows: List[Dict[str, Any]], team_games: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    minutes = sum(g["duration_s"] for g in team_games) / 600
    severity = Counter(r["severity"] for r in rows)
    return {
        "alerts": len(rows),
        "per_team_game": len(rows) / len(team_games) if team_games else 0,
        "per_10min": len(rows) / minutes if minutes else 0,
        "severity": {s: severity.get(s, 0) for s in SEVERITIES},
        "visible": len({(r["game"], r["team"], r["key"]) for r in rows}),
        "duplicates": count_duplicates(rows),
    }


def _follow_up(rows: List[Dict[str, Any]], windows: Sequence[int]) -> Dict[str, Any]:
    acted = [r for r in rows if r.get("label") is not None]
    if not acted:
        return {"actions": None, "followed": None, "anticipated": None}
    labels = Counter(r["label"] for r in acted)
    delays = [r["delay"] for r in acted if r["label"] == "seguida" or r["label"] == "tarde"]
    return {
        "actions": {name: labels.get(name, 0) for name in LABELS},
        "followed": {str(w): _share(sum(1 for d in delays if 0 < d <= w), len(acted)) for w in windows},
        "anticipated": _share(labels.get("anticipada", 0), len(acted)),
    }


def _coverage(rule_id: str, rows: List[Dict[str, Any]], team_games: Sequence[Dict[str, Any]], follow_s: int) -> Optional[float]:
    """Share of the team's own timeouts preceded (within ``follow_s``) by an alert of this timeout-answered rule."""
    if ACTION_FOR.get(rule_id) != "timeout":
        return None
    shown: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for r in rows:
        shown[(r["game"], r["team"])].append(r["shown"])
    total = covered = 0
    for g in team_games:
        for t in g.get("timeouts", []):
            total += 1
            covered += any(s <= t <= s + follow_s for s in shown.get((g["game"], g["team"]), []))
    return _share(covered, total)


def _outcome(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_label: Dict[str, List[float]] = defaultdict(list)
    for r in rows:
        if r.get("label") is not None:
            by_label[r["label"]].append(r["outcome"]["net_delta"])
    pairs = [(r["outcome"]["measure"]) for r in rows if r["outcome"].get("measure")]
    valid = [m for m in pairs if m["before"] is not None and m["after"] is not None]
    return {
        "net_delta": _mean(r["outcome"]["net_delta"] for r in rows),
        "net_delta_by_label": {k: _mean(v) for k, v in by_label.items()},
        "measure": ({"name": valid[0]["name"], "before": _mean(m["before"] for m in valid),
                     "after": _mean(m["after"] for m in valid), "n": len(valid)} if valid else None),
    }


def _verdicts(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    judged = [r for r in rows if r.get("feedback")]
    if not judged:
        return None
    count = Counter(r.get("verdict") for r in judged)
    out: Dict[str, Any] = {v: count.get(v, 0) for v in VERDICTS}
    out["sin_respuesta"] = count.get(None, 0)
    out["obediencia"] = _share(out["seguida"], out["seguida"] + out["descartada"])
    return out


def rule_metrics(rows: Sequence[Dict[str, Any]], team_games: Sequence[Dict[str, Any]],
                 follow_s: int = 120, windows: Sequence[int] = (60, 120, 180)) -> Dict[str, Dict[str, Any]]:
    """Metrics per rule id and, under ``"all"``, the volume of the whole configuration."""
    by_rule: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_rule[r["id"]].append(r)
    out: Dict[str, Dict[str, Any]] = {}
    for rule_id, group in sorted(by_rule.items()):
        out[rule_id] = {**_volume(group, team_games), **_follow_up(group, windows),
                        "coverage": _coverage(rule_id, group, team_games, follow_s),
                        **_outcome(group), "verdicts": _verdicts(group)}
    out["all"] = _volume(list(rows), team_games)
    return out
