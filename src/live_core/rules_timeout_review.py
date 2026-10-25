"""Timeout review (the staff's request of 23/10/2026): an alert when a timeout is called, own or rival, with a short analysis of the two minutes before (why it was
called, what went well and badly, what to do with it) and another two minutes later (did it work). The analysis is in ``timeout_review``.

* ``timeout_review``: once per timeout, as soon as it is in the feed. Only timeouts recent enough (``timeout_fresh_s``): an engine that starts late does not review the whole game.
* ``timeout_followup``: when the two minutes after it are over (or the period ended, with at least ``timeout_followup_min_s``). For a rival timeout only if the rival answered
  strongly (``timeout_rival_answer_net``); for ours always: it worked, it did not, or there was no clear effect.

Standard library only; thresholds provisional, in ``RuleConfig``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .advice_types import Advice, RuleContext
from .clock import period_and_remaining, period_length, period_start
from .proposals import tactic_proposal, timeout_proposal
from .rules_rotation import _level as fatigue_level, fatigue_index
from .timeout_review import proposals_for, reason_of, well_and_bad
from .timeouts import timeouts_left
from .windows import window_stats

_ORDINAL = {1: "1.er cuarto", 2: "2.º cuarto", 3: "3.er cuarto", 4: "4.º cuarto"}


def _clock(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def _when(at: int) -> str:
    period, remaining = period_and_remaining(at)
    return f"{_ORDINAL.get(period, 'prórroga')}, {_clock(remaining)}"


def _timeouts(snap: Dict[str, Any], ctx: RuleContext) -> List[Tuple[str, int]]:
    """The timeouts of both teams already in the feed, ``(team, game-second)``, oldest first."""
    found = [(tid, t) for tid in (ctx.own_team_id, ctx.rival_team_id) if tid for t in (snap["teams"].get(tid) or {}).get("timeouts", []) if t <= snap["elapsed"]]
    return sorted(found, key=lambda x: x[1])


def _names(snap: Dict[str, Any]) -> Dict[str, str]:
    return {pid: p["name"].strip() for pid, p in snap.get("players", {}).items()}


def _on_court(snap: Dict[str, Any], team: str) -> List[Tuple[str, Dict[str, Any]]]:
    return [(pid, p) for pid, p in snap.get("players", {}).items() if p["team_id"] == team and p["on_court"]]


def _tired(snap: Dict[str, Any], ctx: RuleContext, team: str) -> List[Tuple[str, str]]:
    baselines = ctx.baselines if team == ctx.own_team_id else ctx.rival_baselines
    found = []
    for pid, p in _on_court(snap, team):
        index, _ = fatigue_index(p["stint"], p["minutes"], snap["elapsed"], baselines.get(pid), ctx.config)
        if fatigue_level(index, ctx.config, p["stint"]) is not None:
            found.append((pid, p["name"].strip()))
    return found


def timeout_review_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    rival, cfg, own, now, log = ctx.rival_team_id, ctx.config, ctx.own_team_id, snap["elapsed"], snap.get("log", [])
    if not rival:
        return []
    out: List[Advice] = []
    for team, at in _timeouts(snap, ctx):
        if now - at > cfg.timeout_fresh_s:
            continue
        other = rival if team == own else own
        period, remaining = period_and_remaining(at)
        start = max(at - cfg.timeout_review_window_s, period_start(period))
        mine, theirs = window_stats(log, team, start, at), window_stats(log, other, start, at)
        own_w, rival_w = (mine, theirs) if team == own else (theirs, mine)
        tired = _tired(snap, ctx, team)
        kind, reason, who = reason_of(team, own, rival, mine, theirs, log, at, remaining, [n for _, n in tired], cfg)
        ids = [pid for pid, _ in tired] if who else None
        well, bad = well_and_bad(own_w, rival_w, cfg)
        score = snap.get("score") or {}
        text = (f"Tiempo muerto {'propio' if team == own else 'del rival'} ({_when(at)}, {score.get(own, 0)}-{score.get(rival, 0)}): {reason}."
                + (f" Ha ido bien: {'; '.join(well)}." if well else "") + (f" Ha ido mal: {'; '.join(bad)}." if bad else ""))
        proposal = proposals_for(kind, team, own, own_w, rival_w, _names(snap), cfg, who, ids)
        if team == own and kind == "fatigue" and ctx.recommender is not None:
            for pid in ids or []:
                proposal += ctx.recommender.suggest_swaps(snap, pid, max_results=1)
        out.append(Advice(
            key=f"timeout_review:{team}:{at}", id="timeout_review", severity="info", category="gestion", message=text,
            evidence={"team_id": team, "at": at, "reason": kind, "net": mine["pts"] - theirs["pts"], "own_points": own_w["pts"], "rival_points": rival_w["pts"],
                      "well": well, "bad": bad, "window_s": at - start},
            proposal=proposal))
    return out


def _after_window(at: int, cfg: Any) -> Tuple[int, int]:
    """The window after a timeout: ``timeout_review_window_s`` seconds or what is left of its period."""
    period = period_and_remaining(at)[0]
    end = period_start(period) + period_length(period)
    return at, min(at + cfg.timeout_review_window_s, end)


def timeout_followup_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    rival, cfg, own, now, log = ctx.rival_team_id, ctx.config, ctx.own_team_id, snap["elapsed"], snap.get("log", [])
    if not rival:
        return []
    out: List[Advice] = []
    for team, at in _timeouts(snap, ctx):
        start, end = _after_window(at, cfg)
        if end - start < cfg.timeout_followup_min_s or now < end or now - end > cfg.timeout_fresh_s:
            continue
        other = rival if team == own else own
        mine, theirs = window_stats(log, team, start + 1, end), window_stats(log, other, start + 1, end)
        net = mine["pts"] - theirs["pts"]
        own_side = team == own
        if own_side:
            worked: Optional[bool] = True if net >= cfg.timeout_followup_net else False if net <= -cfg.timeout_followup_net else None
        elif net >= cfg.timeout_rival_answer_net:
            worked = True
        else:
            continue
        score = f"{mine['pts']}-{theirs['pts']}" if own_side else f"{theirs['pts']}-{mine['pts']}"
        if own_side:
            verdict = "Ha funcionado" if worked else "No ha funcionado" if worked is False else "Sin efecto claro"
            text = f"Tras el tiempo muerto propio ({_when(at)}): {score} en los {end - start} s siguientes ({net:+d}). {verdict}."
        else:
            text = f"Tras el tiempo muerto del rival ({_when(at)}): el rival ha respondido, {score} en los {end - start} s siguientes (+{net} para él)."
        left = timeouts_left(snap, own)
        proposal: List[Dict[str, Any]] = []
        if own_side and worked:
            proposal.append(tactic_proposal("Mantener lo que ha funcionado: mismo quinteto y misma defensa"))
        elif own_side and worked is None:
            proposal.append(tactic_proposal("Mantener y vigilar: aún no hay un efecto claro"))
        else:
            if left > 0:
                proposal.append(timeout_proposal(left))
            proposal.append(tactic_proposal("Cambiar de defensa o de quinteto: lo hecho en el tiempo muerto no ha cortado el parcial" if own_side
                                            else "Ajustar la defensa: el rival ha sabido aprovechar su tiempo muerto"))
        out.append(Advice(
            key=f"timeout_followup:{team}:{at}", id="timeout_followup", severity="info", category="gestion", message=text,
            evidence={"team_id": team, "at": at, "worked": worked, "net": net, "window_s": end - start,
                      "own_points": (mine if own_side else theirs)["pts"], "rival_points": (theirs if own_side else mine)["pts"]},
            proposal=proposal))
    return out
