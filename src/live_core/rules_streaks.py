"""Team shooting streaks (issue #243), read from the event log with ``windows.last_shots``.

* T1 cold field goals and T2 cold threes (own team): look for inside play, fouls, the rim.
* T3 hot rival and T4 hot rival threes: change the defence or the pressure, close the three-point line.
* T5 cold free throws (own team, whole game): in the close finish the ball goes to the good free-throw shooters.

A streak is the last N attempts of a kind (oldest first). T1-T4 are keyed by the block of N attempts the team is in, so a
streak that goes on is said once and comes back only after a whole new window of attempts (not at every period change or
timeout). T5 is said once in the normal game and once more in the close finish (a warning there). Thresholds are in ``RuleConfig``.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .advice_types import Advice, RuleContext
from .game_context import game_phase
from .proposals import tactic_proposal
from .windows import last_shots

_THREES = ("fg3",)


def _bucket(snap: Dict[str, Any], team_id: str, n: int, kinds) -> int:
    """Which block of ``n`` attempts of ``kinds`` the team is in: a streak that goes on is the same alert until a whole new
    window of attempts has gone by (a period change or a timeout does not make it a new one)."""
    return len(last_shots(snap.get("log", []), team_id, len(snap.get("log", [])), kinds)) // n


def _streak(snap: Dict[str, Any], team_id: str, n: int, kinds=("fg2", "fg3")) -> List[int]:
    """The last ``n`` attempts, only if there are that many (a shorter list is not a streak yet)."""
    results = last_shots(snap.get("log", []), team_id, n, kinds)
    return results if len(results) == n else []


def cold_shooting_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    cfg, own, out = ctx.config, ctx.own_team_id, []
    fg = _streak(snap, own, cfg.cold_fg_n)
    if fg and sum(fg) <= cfg.cold_fg_max_made:
        out.append(Advice(
            key=f"cold_fg:{_bucket(snap, own, cfg.cold_fg_n, ('fg2', 'fg3'))}", id="cold_fg_streak", severity="warning", category="four_factors",
            message=f"Racha fría: {sum(fg)}/{len(fg)} en los últimos tiros de campo. Buscar juego interior y provocar faltas.",
            evidence={"made": sum(fg), "attempts": len(fg)},
            proposal=[tactic_proposal("Juego interior y buscar la falta")]))
    threes = _streak(snap, own, cfg.cold_3p_n, _THREES)
    if threes and sum(threes) <= cfg.cold_3p_max_made:
        out.append(Advice(
            key=f"cold_3p:{_bucket(snap, own, cfg.cold_3p_n, _THREES)}", id="cold_3p_streak", severity="info", category="four_factors",
            message=f"Triples fríos: {sum(threes)}/{len(threes)} seguidos. Atacar el aro.",
            evidence={"made": sum(threes), "attempts": len(threes)},
            proposal=[tactic_proposal("Atacar el aro, menos triples")]))
    return out


def rival_hot_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    rival = ctx.rival_team_id
    if not rival:
        return []
    cfg, out = ctx.config, []
    fg = _streak(snap, rival, cfg.hot_fg_n)
    if fg and sum(fg) >= cfg.hot_fg_min_made:
        out.append(Advice(
            key=f"rival_hot_fg:{_bucket(snap, rival, cfg.hot_fg_n, ('fg2', 'fg3'))}", id="rival_hot_streak", severity="warning", category="rival",
            message=f"El rival está en racha: {sum(fg)}/{len(fg)} en sus últimos tiros de campo. Cambiar la defensa o la presión.",
            evidence={"made": sum(fg), "attempts": len(fg), "team_id": rival},
            proposal=[tactic_proposal("Cambiar de defensa o subir la presión")]))
    threes = _streak(snap, rival, cfg.hot_3p_n, _THREES)
    if threes and sum(threes) >= cfg.hot_3p_min_made:
        out.append(Advice(
            key=f"rival_hot_3p:{_bucket(snap, rival, cfg.hot_3p_n, _THREES)}", id="rival_3p_streak", severity="info", category="rival",
            message=f"El rival está en racha de triples: {sum(threes)}/{len(threes)}. Cerrar la línea de 3.",
            evidence={"made": sum(threes), "attempts": len(threes), "team_id": rival},
            proposal=[tactic_proposal("Cerrar la línea de 3 puntos")]))
    return out


def free_throw_rule(snap: Dict[str, Any], ctx: RuleContext) -> List[Advice]:
    cfg = ctx.config
    results = last_shots(snap.get("log", []), ctx.own_team_id, len(snap.get("log", [])), ("ft",))
    attempts, made = len(results), sum(results)
    if attempts < cfg.ft_cold_min_attempts or made / attempts > cfg.ft_cold_max_pct:
        return []
    close = (cfg.enabled("game_context")
             and game_phase(snap, ctx.own_team_id, ctx.rival_team_id, cfg)["phase"] == "close_late")
    return [Advice(
        key=f"ft_cold:{'close_late' if close else 'normal'}", id="ft_cold", severity="warning" if close else "info",
        category="four_factors",
        message=(f"Tiros libres {made}/{attempts} ({round(100 * made / attempts)} %). En el cierre, "
                 "el balón a los buenos tiradores de tiros libres."),
        evidence={"made": made, "attempts": attempts},
        proposal=[tactic_proposal("Balón a los buenos tiradores de tiros libres en el cierre")])]
