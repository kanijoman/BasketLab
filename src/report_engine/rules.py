"""Rules: quartile strengths/weaknesses, league differentials and consistency (CV)."""
from typing import Any, Dict, List, Optional

from .catalog import CATALOG, BY_KEY, StatDef, format_value
from .config import ReportConfig
from .templates import CONSISTENCY, THEMES


def classify_quartile(value: float, q: Dict[str, Any]) -> Optional[int]:
    """1..4 position of ``value`` in the league quartiles, or None without data."""
    q1, q2, q3 = q.get("q1"), q.get("q2"), q.get("q3")
    if q1 is None or q2 is None or q3 is None:
        return None
    if value <= q1:
        return 1
    if value <= q2:
        return 2
    return 3 if value <= q3 else 4


def _number(stats: Dict[str, Any], key: str) -> Optional[float]:
    try:
        v = stats.get(key)
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def diff_pct(value: float, median: Optional[float]) -> Optional[float]:
    """Difference to the league median in % of the median (None if median is 0/missing)."""
    if not median:
        return None
    return (value - median) / abs(median) * 100.0


def _assess(value: float, level: int, higher_is_better: Optional[bool], median: float) -> Optional[str]:
    """Strength = clearly on the good side of the league median, weakness = worst quartile."""
    if higher_is_better is None:
        return None
    if higher_is_better:
        return "strength" if level >= 3 else ("weakness" if level == 1 else None)
    return "strength" if value < median else ("weakness" if level == 4 else None)


def _finding(stat: StatDef, value: float, level: int, d: Optional[float], kind: str, mode: str) -> Dict[str, Any]:
    t = THEMES[stat.theme]
    suffix = "own" if mode == "own" else "riv"
    text = t[("s_" if kind == "strength" else "w_") + suffix]
    return {
        "key": stat.key, "label": stat.label, "group": stat.group, "theme": stat.theme,
        "value": value, "formatted": format_value(stat, value),
        "quartile": level, "diff_pct": d, "kind": kind, "text": text,
    }


def quartile_findings(stats: Dict[str, Any], quartiles: Dict[str, Any], mode: str) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {"strength": [], "weakness": []}
    for stat in CATALOG:
        value = _number(stats, stat.key)
        q = quartiles.get(stat.key) or {}
        level = None if value is None else classify_quartile(value, q)
        kind = None if level is None else _assess(value, level, stat.higher_is_better, q["q2"])
        if kind:
            out[kind].append(_finding(stat, value, level, diff_pct(value, q.get("q2")), kind, mode))
    for lst in out.values():
        lst.sort(key=lambda f: -abs(f["diff_pct"] or 0.0))
    return out


def differentials(stats: Dict[str, Any], quartiles: Dict[str, Any], cfg: ReportConfig) -> List[Dict[str, Any]]:
    out = []
    for stat in CATALOG:
        value = _number(stats, stat.key)
        if value is None or stat.higher_is_better is None:
            continue
        d = diff_pct(value, (quartiles.get(stat.key) or {}).get("q2"))
        if d is None or abs(d) < cfg.diff_threshold_pct:
            continue
        better = d > 0 if stat.higher_is_better else d < 0
        out.append({"key": stat.key, "label": stat.label, "value": value,
                    "formatted": format_value(stat, value), "diff_pct": d, "advantage": better})
    return sorted(out, key=lambda x: -abs(x["diff_pct"]))


def consistency(cv_map: Optional[Dict[str, Any]], mode: str, cfg: ReportConfig) -> List[Dict[str, Any]]:
    out = []
    for key, m in (cv_map or {}).items():
        stat = BY_KEY.get(key)
        cv, n = (m or {}).get("cv"), (m or {}).get("n", 0)
        if stat is None or cv is None or n < cfg.min_games_cv:
            continue
        status = "inconsistent" if cv > cfg.cv_inconsistent else ("consistent" if cv < cfg.cv_consistent else None)
        if status:
            out.append({"key": key, "label": stat.label, "cv": cv, "status": status,
                        "text": CONSISTENCY[mode][status]})
    return sorted(out, key=lambda x: (x["status"] != "inconsistent", -x["cv"]))
