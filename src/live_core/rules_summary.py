"""Summary of the quarter and of the first half (issue #246, C3), delivered in the pause where latency does not matter.

At the end of the 1st, 2nd (halftime: the first half) and 3rd periods (``remaining == 0``) one alert of category ``resumen`` says
the score of the period, up to three keys and one or two adjustments. The keys are the first three that apply of a fixed list
(priority order below), so the summary is deterministic and a quiet period says so. #402: besides the weak points it has two positive
keys, a comeback (first) with its complement, a hard run conceded in the period, and a clearly won period (last, only if there is room). Thresholds are provisional, in ``RuleConfig``.

P6 (``period_edges``, issue #250) is delivered in the same pause: when the first ``edge_window_s`` (2:00) of the quarters played, or their
last ``edge_window_s``, add up to ``edge_net`` (6) points against or worse, with at least ``edge_min_periods`` (2) negative quarters,
it says so and asks to prepare the way out of the next quarter. Said once per kind and pause.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from .advice_types import Advice, RuleContext
from .clock import period_length, period_start
from .proposals import tactic_proposal
from .summary_pace import pace_facts, pace_key, pace_line
from .windows import player_points, window_stats

_TITLES = {1: "Fin del 1.er cuarto", 2: "Descanso", 3: "Fin del 3.er cuarto"}
MAX_KEYS, MAX_ADJUSTMENTS = 3, 2

Facts = Dict[str, Any]
# (id, test) -> (key text, adjustment text) or None, in priority order
_Candidate = Callable[[Facts], Optional[Tuple[str, str]]]


def _pct(made: int, attempts: int) -> float:
    return made / attempts if attempts else 0.0


def _turnovers(f: Facts) -> Optional[Tuple[str, str]]:
    if f["own"]["tov"] - f["rival"]["tov"] >= f["cfg"].summary_tov_diff:
        return f"Pérdidas: {f['own']['tov']} vs {f['rival']['tov']}", "Asegurar el balón en la salida de pista"
    return None


def _rival_orb(f: Facts) -> Optional[Tuple[str, str]]:
    if f["rival"]["orb"] - f["own"]["orb"] >= f["cfg"].summary_orb_diff:
        return f"Rebotes ofensivos del rival: {f['rival']['orb']} vs {f['own']['orb']}", "Cerrar el rebote: bloqueo y balance"
    return None


def _rival_scorer(f: Facts) -> Optional[Tuple[str, str]]:
    name, pts = f["scorer"]
    if name and pts >= f["cfg"].summary_scorer_pts:
        return f"{name} anota {pts} puntos", f"Ayudas sobre {name}"
    return None


def _own_ft(f: Facts) -> Optional[Tuple[str, str]]:
    made, att = f["own"]["ft"]
    if att >= f["cfg"].summary_ft_min_att and _pct(made, att) <= f["cfg"].ft_cold_max_pct:
        return f"Tiros libres: {made}/{att}", "Balón a los buenos tiradores de tiros libres"
    return None


def _own_threes(f: Facts) -> Optional[Tuple[str, str]]:
    made, att = f["own"]["fg3"]
    if att >= f["cfg"].summary_3p_min_att and _pct(made, att) <= f["cfg"].summary_3p_max_pct:
        return f"Triples: {made}/{att}", "Más juego interior y menos triples"
    return None


def _rival_threes(f: Facts) -> Optional[Tuple[str, str]]:
    made, att = f["rival"]["fg3"]
    if att >= f["cfg"].summary_3p_min_att and _pct(made, att) >= f["cfg"].summary_rival_3p_min_pct:
        return f"Triples del rival: {made}/{att}", "Salir al tirador y cerrar la línea de 3"
    return None


def _own_fg(f: Facts) -> Optional[Tuple[str, str]]:
    (m2, a2), (m3, a3) = f["own"]["fg2"], f["own"]["fg3"]
    att = a2 + a3
    if att >= f["cfg"].summary_fg_min_att and (m2 + m3 + 0.5 * m3) / att <= f["cfg"].summary_fg_max_efg:
        return f"Tiro de campo: {m2 + m3}/{att}", "Mejorar la selección de tiro"
    return None


def _fouls(f: Facts) -> Optional[Tuple[str, str]]:
    if f["fouls"] >= f["cfg"].summary_fouls:
        return f"Faltas de equipo: {f['fouls']}", "Defender sin falta"
    return None


def _comeback(f: Facts) -> Optional[Tuple[str, str]]:
    """From the deepest point INSIDE the summarised window (where it started counts) to where it ended (issue #419)."""
    worst, now = f["worst_net"], f["net"]
    if -worst >= f["cfg"].summary_comeback_deficit and now - worst >= f["cfg"].summary_comeback_recovery:
        return f"Remontada {f['scope']}: de {worst:+d} a {now:+d}", "Mantener lo que ha funcionado"
    return None


def _pace(f: Facts) -> Optional[Tuple[str, str]]:
    cfg = f["cfg"]
    return pace_key(f["pace"], f["own"]["pts"] - f["rival"]["pts"], cfg.summary_pace_delta, cfg.summary_pace_min_net)


def _collapse(f: Facts) -> Optional[Tuple[str, str]]:
    if f["drop"] >= f["cfg"].summary_collapse_drop:
        return f"Parcial en contra: {-f['drop']:+d}", "Parar el parcial antes: tiempo muerto o cambio de defensa"
    return None


def _period_net(f: Facts) -> Optional[Tuple[str, str]]:
    net = f["own"]["pts"] - f["rival"]["pts"]
    if net >= f["cfg"].summary_period_net:
        return f"Parcial del cuarto: {net:+d}", "Mantener lo que ha funcionado"
    return None


_CANDIDATES: List[Tuple[str, _Candidate]] = [
    ("comeback", _comeback), ("collapse", _collapse), ("pace", _pace), ("turnovers", _turnovers), ("rival_orb", _rival_orb), ("rival_scorer", _rival_scorer), ("own_ft", _own_ft),
    ("own_threes", _own_threes), ("rival_threes", _rival_threes), ("own_fg", _own_fg), ("fouls", _fouls),
    ("period_net", _period_net),
]


def _net_range(log: List[Any], own: str, rival: str, start: int, end: int) -> Tuple[int, int]:
    """(worst, final) net points (own - rival) inside ``[start, end]``: the deepest the net went, the start counting, and where it ended.
    What happened before ``start`` only gives the net the window starts from (issue #419: a quarter is measured on its own)."""
    net = sum((e[3] if e[1] == own else -e[3] if e[1] == rival else 0) for e in log if e[2] == "pts" and e[0] < start)
    worst = net
    for e in log:
        if start <= e[0] <= end and e[2] == "pts":
            net += e[3] if e[1] == own else -e[3] if e[1] == rival else 0
            worst = min(worst, net)
    return worst, net


def _net_drop(log: List[Any], own: str, rival: str, start: int, end: int) -> int:
    """The biggest fall of the net score (own - rival) from its best point within ``[start, end]``: a hard run conceded."""
    net = best = drop = 0
    for e in log:
        if start <= e[0] <= end and e[2] == "pts":
            net += e[3] if e[1] == own else -e[3] if e[1] == rival else 0
            best = max(best, net)
            drop = max(drop, best - net)
    return drop


def _facts(snap: Dict[str, Any], ctx: RuleContext, start: int, end: int, periods: List[int]) -> Facts:
    """What the summary of the window ``[start, end]`` knows. Everything is measured inside the window, except the pace, which is also
    compared with the game before it."""
    log, rival = snap.get("log", []), ctx.rival_team_id or ""
    scorers = [(player_points(log, pid, start, end), p["name"].strip()) for pid, p in snap["players"].items()
               if p["team_id"] == rival]
    pts, name = max(scorers, default=(0, ""))
    own_fouls = ((snap["teams"].get(ctx.own_team_id) or {}).get("fouls_by_period") or {})
    worst, net = _net_range(log, ctx.own_team_id, rival, start, end)
    return {"cfg": ctx.config, "own": window_stats(log, ctx.own_team_id, start, end), "rival": window_stats(log, rival, start, end),
            "scorer": (name, pts), "fouls": sum(own_fouls.get(str(p), 0) for p in periods), "worst_net": worst, "net": net,
            "drop": _net_drop(log, ctx.own_team_id, rival, start, end), "scope": "en la 1.ª parte" if len(periods) > 1 else "en el cuarto",
            "pace": pace_facts(log, ctx.own_team_id, rival, start, end, ctx.team_baselines)}


def _period_to_sum_up(snap: Dict[str, Any], grace_s: int) -> Optional[int]:
    """The period whose summary is due: the one that has just ended (clock at 0:00) or, if the poll missed that instant, the
    previous one while the next period is still in its first ``grace_s`` seconds. The key makes sure it is said once."""
    period, remaining = snap["period"], snap["remaining"]
    if remaining == 0 and period in _TITLES:
        return period
    if period - 1 in _TITLES and period_length(period) - remaining <= grace_s:
        return period - 1
    return None


def period_keys(snap: Dict[str, Any], ctx: RuleContext, period: int) -> Tuple[List[str], List[str]]:
    """The keys and the adjustments of ONE period as the summary of the quarter would say them (used by the post-match report)."""
    facts = _facts(snap, ctx, period_start(period), period_start(period) + period_length(period), [period])
    found = [hit for _, test in _CANDIDATES if (hit := test(facts)) is not None][:MAX_KEYS]
    return [text for text, _ in found], list(dict.fromkeys(adjustment for _, adjustment in found))[:MAX_ADJUSTMENTS]


def summary_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    period = _period_to_sum_up(snap, ctx.config.summary_grace_s)
    if period is None:
        return []
    start = 0 if period == 2 else period_start(period)           # halftime sums up the whole first half
    end = period_start(period) + period_length(period)
    facts = _facts(snap, ctx, start, end, [1, 2] if period == 2 else [period])
    found = [(key, hit) for key, test in _CANDIDATES if (hit := test(facts)) is not None][:MAX_KEYS]
    adjustments = list(dict.fromkeys(adjustment for _, (_, adjustment) in found))[:MAX_ADJUSTMENTS]
    own, rival = facts["own"]["pts"], facts["rival"]["pts"]
    message = f"{_TITLES[period]}: {own}-{rival} ({own - rival:+d}). "
    message += "Claves: " + "; ".join(text for _, (text, _) in found) + "." if found else "Sin claves destacadas."
    if facts["pace"]:
        message += " " + pace_line(facts["pace"])
    return [Advice(
        key=f"summary:{period}", id="period_summary", severity="info", category="resumen", message=message,
        evidence={"period": period, "own_points": own, "rival_points": rival, "keys": [key for key, _ in found],
                  "adjustments": adjustments, "pace": facts["pace"]},
        proposal=[tactic_proposal(a) for a in adjustments])]


def _edge_nets(snap: Dict[str, Any], ctx: RuleContext, through: int, kind: str) -> List[int]:
    """Net points (own - rival) of the first or last ``edge_window_s`` of each quarter up to ``through``."""
    log, rival, width = snap.get("log", []), ctx.rival_team_id or "", ctx.config.edge_window_s
    nets = []
    for p in range(1, through + 1):
        start, end = period_start(p), period_start(p) + period_length(p)
        lo, hi = (start, start + width) if kind == "start" else (end - width, end)
        nets.append(window_stats(log, ctx.own_team_id, lo, hi)["pts"] - window_stats(log, rival, lo, hi)["pts"])
    return nets


_EDGE_TEXT = {
    "start": ("Inicios de cuarto", "Preparar la salida del próximo cuarto: quinteto y primera jugada"),
    "end": ("Cierres de cuarto", "Cuidar los últimos 2:00 de cada cuarto: última posesión y no regalar faltas"),
}


def edges_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    period = _period_to_sum_up(snap, ctx.config.summary_grace_s)
    if period is None or not ctx.rival_team_id:
        return []
    cfg, out = ctx.config, []
    for kind, (label, advice) in _EDGE_TEXT.items():
        nets = _edge_nets(snap, ctx, period, kind)
        if len(nets) < cfg.edge_min_periods or sum(1 for n in nets if n < 0) < cfg.edge_min_periods or sum(nets) > -cfg.edge_net:
            continue
        out.append(Advice(
            key=f"edges:{kind}:{period}", id="period_edge_deficit", severity="info", category="resumen",
            message=f"{label}: {', '.join(f'{n:+d}' for n in nets)} ({sum(nets):+d} acumulado).",
            evidence={"kind": kind, "nets": nets, "total": sum(nets), "window_s": cfg.edge_window_s},
            proposal=[tactic_proposal(advice)]))
    return out
