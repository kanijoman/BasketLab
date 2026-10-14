"""Our team against the scouted one, stat by stat (issue #299; the matchup part that came from #143).

Both teams' rows are the season team stats of the report engine (``src.report_engine.catalog``): a stat is an advantage of
one side when it is better in the direction that stat has (more points, fewer turnovers) and the two differ by at least
``threshold_pct`` of the rival's value; tempo and shot-mix stats depend on style and have no advantage. The roles are just
"own" and "rival": nothing is tied to a team.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.report_engine.catalog import CATALOG, format_value

DEFAULT_THRESHOLD_PCT = 5.0


def _number(stats: Dict[str, Any], key: str) -> Optional[float]:
    value = stats.get(key)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _text(stat: Any, value: float) -> str:
    text = format_value(stat, value).replace(".", ",")
    return text.replace("%", " %") if stat.pct else text


def compare_teams(own: Optional[Dict[str, Any]], rival: Optional[Dict[str, Any]],
                  threshold_pct: float = DEFAULT_THRESHOLD_PCT) -> List[Dict[str, Any]]:
    """Rows ``{key, label, group, own, rival, own_text, rival_text, diff_pct, advantage}``, the biggest gaps first.

    ``advantage`` is ``own``, ``rival``, ``even`` (under the threshold) or ``neutral`` (a stat of style). ``diff_pct`` is the
    gap relative to the rival's value. Stats missing on either side are left out.
    """
    if not own or not rival:
        return []
    rows = []
    for stat in CATALOG:
        a, b = _number(own, stat.key), _number(rival, stat.key)
        if a is None or b is None:
            continue
        diff = (a - b) / abs(b) * 100 if b else 0.0
        if stat.higher_is_better is None:
            advantage = "neutral"
        elif abs(diff) < threshold_pct:
            advantage = "even"
        else:
            advantage = "own" if (diff > 0) == bool(stat.higher_is_better) else "rival"
        rows.append({"key": stat.key, "label": stat.label, "group": stat.group, "own": a, "rival": b, "own_text": _text(stat, a),
                     "rival_text": _text(stat, b), "diff_pct": diff, "advantage": advantage})
    return sorted(rows, key=lambda r: (r["advantage"] == "neutral", -abs(r["diff_pct"])))
