"""Post-match analysis (issue #409): from the final FEB document of a game to a structured report the app turns into a PDF.

The document is replayed through ``LiveGame`` once, keeping the five own players on court at every basket, so a run can say who
was playing. The report has the periods with their keys (the ones of the quarter summary, ``rules_summary.period_keys``), the
evolution of the score, the runs (unanswered streaks) with an explanation, the lineups and players by plus/minus, the Four Factors,
what went well and what could be better (``postmatch_text``), and the alerts of the match with period, clock and score.
Everything is Spanish for the staff, JSON-serialisable, deterministic and standard library only (it runs on the tablet).
Thresholds are provisional (``RUN_MIN_PTS``...).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .advice_types import RuleContext
from .clock import elapsed_seconds, parse_clock, period_length, period_start
from .config import RuleConfig
from .engine import _events, _roster, _teams
from .four_factors import factors, possessions
from .postmatch_text import explain_run, strengths_and_weaknesses
from .rules_summary import period_keys
from .state import LiveGame
from .windows import window_stats

REPORT_VERSION = 1
RUN_MIN_PTS = 8            # unanswered points that make a run
TIMELINE_STEP_S = 60
LINEUP_MIN_S = 120         # a lineup needs these game-seconds to be ranked
PLAYER_MIN_S = 300         # and a player these to be ranked by plus/minus
RANKED = 3

Score = Tuple[int, str, int]    # (elapsed, team id, points)
_LABEL = re.compile(r"^(Q|PR)(\d+)\s+(\d{1,2}):(\d{2})")


def find_runs(scores: Sequence[Score], own: str, rival: str, min_pts: int = RUN_MIN_PTS) -> List[Dict[str, Any]]:
    """The streaks of unanswered points of ``min_pts`` or more, in game order (free throws count)."""
    runs: List[Dict[str, Any]] = []
    totals = {own: 0, rival: 0}
    streak: Optional[Dict[str, Any]] = None
    for t, team, value in scores:
        if streak is None or streak["team"] != team:
            if streak and streak["pts"] >= min_pts:
                runs.append(streak)
            streak = {"team": team, "start": t, "end": t, "pts": 0, "score_before": [totals[own], totals[rival]]}
        streak["pts"] += value
        streak["end"] = t
        totals[team] += value
        streak["score_after"] = [totals[own], totals[rival]]
    if streak and streak["pts"] >= min_pts:
        runs.append(streak)
    return runs


def evolution(scores: Sequence[Score], own: str, rival: str, end: int) -> Dict[str, Any]:
    """Lead changes, ties, biggest lead and deficit, and the net score every ``TIMELINE_STEP_S`` seconds."""
    net, lead, changes, ties = 0, 0, 0, 0
    best, worst = {"margin": 0, "elapsed": 0}, {"margin": 0, "elapsed": 0}
    timeline, step = [[0, 0]], TIMELINE_STEP_S
    for t, team, value in scores:
        while step < t:
            timeline.append([step, net])
            step += TIMELINE_STEP_S
        net += value if team == own else -value if team == rival else 0
        sign = (net > 0) - (net < 0)
        if net == 0:
            ties += 1
        elif lead and sign != lead:
            changes += 1
        lead = sign or lead
        if net > best["margin"]:
            best = {"margin": net, "elapsed": t}
        if -net > worst["margin"]:
            worst = {"margin": -net, "elapsed": t}
    while step < end:
        timeline.append([step, net])
        step += TIMELINE_STEP_S
    timeline.append([end, net])
    return {"lead_changes": changes, "ties": ties, "max_lead": best, "max_deficit": worst, "timeline": timeline}


def _label(period: int) -> str:
    return f"Prórroga {period - 4}" if period > 4 else f"Cuarto {period}"


def clock_text(period: int, remaining: int) -> str:
    """The label the app uses for a game clock: ``Q2 05:30``, ``PR1 03:00``."""
    return f"{'PR' + str(period - 4) if period > 4 else 'Q' + str(period)} {remaining // 60:02d}:{remaining % 60:02d}"


def _split(elapsed: int) -> Tuple[int, int]:
    period = 1
    while elapsed >= period_start(period) + period_length(period):
        period += 1
    return period, period_start(period) + period_length(period) - elapsed


def _on_court(game: LiveGame, team_id: str) -> List[str]:
    return sorted(pid for pid, p in game.players.items() if p.on_court and p.team_id == team_id)


def _replay(doc: Dict[str, Any], own: str) -> Tuple[LiveGame, List[Tuple[Score, List[str]]]]:
    """The game after all its events, and every basket with the own players on court when it was scored."""
    game = LiveGame(_teams(doc), _roster(doc))
    baskets: List[Tuple[Score, List[str]]] = []
    for ev in (e for e in _events(doc) if not e.deleted):
        before = len(game.log)
        game.apply(ev)
        for t, team, kind, value, _pid in game.log[before:]:
            if kind == "pts":
                baskets.append(((t, team, value), _on_court(game, own)))
    header = doc.get("HEADER") or {}
    remaining = parse_clock(header.get("time"))
    if remaining is not None and str(header.get("quarter")).isdigit():
        game.set_clock(int(str(header.get("quarter"))), remaining)
    return game, baskets


def _periods(snap: Dict[str, Any], own: str, rival: str, cfg: RuleConfig) -> List[Dict[str, Any]]:
    ctx = RuleContext(own_team_id=own, rival_team_id=rival, config=cfg, baselines={})
    out = []
    for period in range(1, snap["period"] + 1):
        start, end = period_start(period), period_start(period) + period_length(period)
        mine, theirs = (window_stats(snap["log"], t, start, end)["pts"] for t in (own, rival))
        keys, adjustments = period_keys(snap, ctx, period)
        out.append({"period": period, "label": _label(period), "own": mine, "rival": theirs, "net": mine - theirs,
                    "keys": keys, "adjustments": adjustments})
    return out


def _timeout_before(snap: Dict[str, Any], own: str, start: int) -> bool:
    return any(0 <= start - t <= 180 for t in (snap["teams"].get(own) or {}).get("timeouts", []))


def _run_row(run: Dict[str, Any], baskets: List[Tuple[Score, List[str]]], snap: Dict[str, Any], own: str, rival: str,
             cfg: RuleConfig) -> Dict[str, Any]:
    names = {pid: p["name"].strip() for pid, p in snap["players"].items()}
    first = next(i for i, (s, _) in enumerate(baskets) if s[0] == run["start"] and s[1] == run["team"])
    on_court = baskets[first][1]
    earlier = [oc for s, oc in baskets[:first + 1] if s[0] <= run["start"] - 120]
    before = earlier[-1] if earlier else on_court
    entered = [names.get(p, p) for p in sorted(set(on_court) - set(before))]
    left = [names.get(p, p) for p in sorted(set(before) - set(on_court))]
    period, remaining = _split(run["start"])
    stats = {t: window_stats(snap["log"], t, run["start"], run["end"]) for t in (own, rival)}
    return {
        "team": "own" if run["team"] == own else "rival", "start": run["start"], "end": run["end"], "pts": run["pts"],
        "period": period, "clock": clock_text(period, remaining), "score_before": run["score_before"],
        "score_after": run["score_after"], "lineup": [names.get(pid, pid) for pid in on_court], "entered": entered, "left": left,
        "explanation": explain_run(run["team"] == own, stats[own], stats[rival], names, entered, left,
                                   _timeout_before(snap, own, run["start"]), cfg),
    }


def _lineups(snap: Dict[str, Any], own: str) -> Dict[str, List[Dict[str, Any]]]:
    names = {pid: p["name"].strip() for pid, p in snap["players"].items()}
    rows = [{"players": [names.get(pid, pid) for pid in row["players"]], "seconds": row["seconds"], "pts_for": row["pts_for"],
             "pts_against": row["pts_against"], "net": row["pts_for"] - row["pts_against"]}
            for row in snap["lineups"].get(own, []) if row["seconds"] >= LINEUP_MIN_S]
    best = sorted(rows, key=lambda r: (-r["net"], -r["seconds"], r["players"]))
    worst = sorted(rows, key=lambda r: (r["net"], -r["seconds"], r["players"]))
    return {"best": best[:RANKED], "worst": worst[:RANKED]}


def _players(snap: Dict[str, Any], own: str) -> Dict[str, List[Dict[str, Any]]]:
    rows = [{"name": p["name"].strip(), "pm": p["pm"], "pts": p["pts"], "minutes": p["minutes"]}
            for p in snap["players"].values() if p["team_id"] == own and p["minutes"] >= PLAYER_MIN_S]
    return {"top": sorted(rows, key=lambda r: (-r["pm"], r["name"]))[:RANKED],
            "bottom": sorted(rows, key=lambda r: (r["pm"], r["name"]))[:RANKED]}


def _team_block(stats: Dict[str, int], other: Dict[str, int]) -> Dict[str, Any]:
    poss = possessions(stats)
    return {"stats": stats, "possessions": round(poss, 1), "rating": round(stats["pts"] / poss * 100, 1) if poss else 0.0,
            "factors": {k: round(v, 4) for k, v in factors(stats, other).items()}}


def enrich_alerts(alerts: Sequence[Dict[str, Any]], timeline: Sequence[Sequence[Any]]) -> List[Dict[str, Any]]:
    """The alerts of the match (``{alert, at}`` as the app keeps them) with period, clock, game second and the score then."""
    rows = []
    for item in alerts:
        alert, match = item["alert"], _LABEL.match(item.get("at") or "")
        period = elapsed = clock = score = None
        if match:
            period = int(match.group(2)) + (4 if match.group(1) == "PR" else 0)
            elapsed = elapsed_seconds(period, int(match.group(3)) * 60 + int(match.group(4)))
            clock = f"{match.group(3).zfill(2)}:{match.group(4)}"
            score = next((s for t, s in reversed(timeline) if t <= elapsed), [0, 0])
        rows.append({"key": alert["key"], "id": alert["id"], "severity": alert["severity"], "category": alert["category"],
                     "message": alert["message"], "proposal": [p.get("message") or p.get("type") for p in alert.get("proposal") or []],
                     "period": period, "clock": clock, "elapsed": elapsed, "score": score})
    return sorted(rows, key=lambda r: (r["elapsed"] is None, r["elapsed"] or 0))


def _timeline(scores: Sequence[Score], own: str, rival: str) -> List[List[Any]]:
    """``[elapsed, [own, rival]]`` after every basket."""
    mine = theirs = 0
    out: List[List[Any]] = []
    for t, team, value in scores:
        mine, theirs = mine + (value if team == own else 0), theirs + (value if team == rival else 0)
        out.append([t, [mine, theirs]])
    return out


def _narrative(evo: Dict[str, Any]) -> List[str]:
    out = []
    for key, text in (("max_lead", "Máxima ventaja propia"), ("max_deficit", "Máxima desventaja")):
        if evo[key]["margin"]:
            period, remaining = _split(evo[key]["elapsed"])
            out.append(f"{text}: {evo[key]['margin']} puntos ({clock_text(period, remaining)}).")
    out.append(f"{evo['lead_changes']} cambios de ventaja y {evo['ties']} empates.")
    return out


def build_report(doc: Dict[str, Any], own_team_id: str, alerts: Optional[Sequence[Dict[str, Any]]] = None,
                 config: Optional[RuleConfig] = None) -> Dict[str, Any]:
    """The post-match report of ``doc`` (the final merged FEB document) from the point of view of ``own_team_id``."""
    cfg = config or RuleConfig()
    game, baskets = _replay(doc, own_team_id)
    snap = game.snapshot()
    rival = next(tid for tid in snap["teams"] if tid != own_team_id)
    scores = [s for s, _ in baskets]
    mine, theirs = snap["score"][own_team_id], snap["score"][rival]
    own_stats, rival_stats = snap["teams"][own_team_id]["stats"], snap["teams"][rival]["stats"]
    team = {"own": _team_block(own_stats, rival_stats), "rival": _team_block(rival_stats, own_stats)}
    timeline = _timeline(scores, own_team_id, rival)
    report: Dict[str, Any] = {
        "version": REPORT_VERSION,
        "match": {"own": {"id": own_team_id, "name": snap["teams"][own_team_id]["name"]},
                  "rival": {"id": rival, "name": snap["teams"][rival]["name"]}, "home_id": snap["home_id"],
                  "score": {"own": mine, "rival": theirs}, "result": "win" if mine > theirs else "loss" if mine < theirs else "tie",
                  "periods": _periods(snap, own_team_id, rival, cfg)},
        "evolution": evolution(scores, own_team_id, rival, max(snap["elapsed"], 1)), "timeline": timeline,
        "runs": [_run_row(r, baskets, snap, own_team_id, rival, cfg) for r in find_runs(scores, own_team_id, rival)],
        "lineups": _lineups(snap, own_team_id), "players": _players(snap, own_team_id), "team": team,
        "four_factors": {"own": team["own"]["factors"], "rival": team["rival"]["factors"]},
    }
    report["evolution"]["narrative"] = _narrative(report["evolution"])
    report["went_well"], report["to_improve"] = strengths_and_weaknesses(report, snap, own_team_id, rival)
    report["alerts"] = enrich_alerts(alerts, timeline) if alerts is not None else []
    return report
