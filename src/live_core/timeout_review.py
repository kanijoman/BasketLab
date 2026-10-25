"""What a timeout was for and what it did (the staff's request of 23/10/2026): the analysis behind ``timeout_review`` and ``timeout_followup``.

Pure functions over the window statistics of the log (``windows.window_stats``). The reason of a timeout is read from the two minutes before it: a run against the team that called it,
the last possession of a period, turnovers, a drought or tired players (never fouls: a foul is not why a game is stopped, #563); without any of them it is rest or a play being prepared. What went well and badly is
always told from OUR side, whoever called the timeout. Thresholds are provisional, in ``RuleConfig``. Standard library only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .config import RuleConfig
from .proposals import tactic_proposal
from .windows import run_causes, scoring_gap, window_stats

# the usual way to answer the cause of a run against us (the kinds of ``windows.run_causes``)
_ANSWER = {
    "turnovers": "Asegurar la salida del balón: ayuda al base y un segundo manejador",
    "rival_orb": "Cerrar el rebote: balance defensivo y un reboteador más en pista",
    "rival_threes": "Salir al tirador: defender la línea de 3 con ayudas más cortas",
    "rival_free_throws": "Defender sin falta: manos arriba y verticalidad",
    "own_free_throws": "Los tiros libres: el balón a los mejores tiradores de tiros libres",
    "own_cold": "Cambiar el sistema ofensivo: buscar el aro y cambiar de tirador",
}


def _n(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def other_team(team: str, own: str, rival: str) -> str:
    return rival if team == own else own


def reason_of(team: str, own: str, rival: str, mine: Dict[str, Any], theirs: Dict[str, Any], log: List[Any], now: int, remaining: int,
              tired: List[str], cfg: RuleConfig, own_first: bool = True) -> Tuple[str, str, Optional[List[str]]]:
    """``(kind, text, names)``: why ``team`` called the timeout, from the window before it. ``mine``/``theirs`` are the window of the team and of the other one."""
    net = mine["pts"] - theirs["pts"]
    own_w, rival_w = (mine, theirs) if team == own else (theirs, mine)
    score = f"{own_w['pts']}-{rival_w['pts']}" if own_first else f"{rival_w['pts']}-{own_w['pts']}"      # the order of the scoreboard (#560)
    if net <= -cfg.timeout_run_net:
        return "run", ("para cortar el parcial rival (" + score + ")") if team == own else ("para cortar nuestro parcial (" + score + ")"), None
    if 0 < remaining <= cfg.timeout_last_possession_s:
        return "last_possession", "para preparar la última posesión del cuarto", None
    if mine["tov"] >= cfg.timeout_tov_n:
        return "turnovers", f"tras {_n(mine['tov'], 'pérdida', 'pérdidas')}" + (" propias" if team == own else " del rival"), None
    gap = scoring_gap(log, team, now, now - cfg.timeout_review_window_s)
    if gap >= cfg.timeout_drought_s:
        clock = ("más de " if gap >= cfg.timeout_review_window_s else "") + f"{gap // 60}:{gap % 60:02d}"
        return "drought", (f"tras {clock} sin anotar" if team == own else f"tras {clock} sin anotar el rival"), None
    if tired:
        return "fatigue", ("por cansancio de " if team == own else "para descansar a ") + ", ".join(tired), tired
    made, tried = theirs["fg2"][0] + theirs["fg3"][0], theirs["fg2"][1] + theirs["fg3"][1]
    if made >= cfg.timeout_scoring_n and made / tried >= cfg.timeout_scoring_pct:
        return "rival_scoring", (f"tras {made} canastas del rival en {tried} tiros" if team == own else f"para frenar nuestro acierto ({made} canastas en {tried} tiros)"), None
    behind = window_stats(log, other_team(team, own, rival), 0, now)["pts"] - window_stats(log, team, 0, now)["pts"]
    if behind >= cfg.timeout_deficit:
        return "deficit", f"con el marcador en contra ({-behind:+d})" if team == own else f"con el rival {behind} puntos por debajo", None
    return "none", "sin motivo claro: descanso o preparar una jugada", None


def well_and_bad(own_w: Dict[str, Any], rival_w: Dict[str, Any], cfg: RuleConfig) -> Tuple[List[str], List[str]]:
    """What went well and what went badly for US in the window (two lines each at most)."""
    well: List[str] = []
    bad: List[str] = []
    net = own_w["pts"] - rival_w["pts"]
    if net >= cfg.timeout_good_net:
        well.append(f"parcial {own_w['pts']}-{rival_w['pts']} a favor")
    elif net <= -cfg.timeout_good_net:
        bad.append(f"parcial {own_w['pts']}-{rival_w['pts']} en contra")
    fga = own_w["fg2"][1] + own_w["fg3"][1]
    fgm = own_w["fg2"][0] + own_w["fg3"][0]
    if fga >= cfg.timeout_shots_min:
        efg = (fgm + 0.5 * own_w["fg3"][0]) / fga
        if efg >= cfg.timeout_efg_good:
            well.append(f"tiro propio {fgm}/{fga}")
        elif efg <= cfg.timeout_efg_bad:
            bad.append(f"tiro propio {fgm}/{fga}")
    if rival_w["tov"] >= cfg.timeout_tov_n:
        well.append(_n(rival_w["tov"], "pérdida del rival", "pérdidas del rival"))
    if own_w["orb"] >= cfg.timeout_tov_n:
        well.append(_n(own_w["orb"], "rebote ofensivo propio", "rebotes ofensivos propios"))
    if own_w["tov"] >= cfg.timeout_tov_n:
        bad.append(_n(own_w["tov"], "pérdida propia", "pérdidas propias"))
    if rival_w["orb"] >= cfg.timeout_tov_n:
        bad.append(_n(rival_w["orb"], "rebote ofensivo del rival", "rebotes ofensivos del rival"))
    if rival_w["fg3"][0] >= cfg.timeout_tov_n:
        bad.append(_n(rival_w["fg3"][0], "triple del rival", "triples del rival"))
    return well[:3], bad[:3]


def proposals_for(kind: str, team: str, own: str, own_w: Dict[str, Any], rival_w: Dict[str, Any], names: Dict[str, str], cfg: RuleConfig,
                  who: Optional[List[str]] = None, player_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """What to do with the timeout: the answer to its cause when it is ours, the restart and the intensity when it is the rival's."""
    out: List[Dict[str, Any]] = []
    if team != own:       # the rival stopped the game: receive the restart, do not lose the intensity, rest what is tired
        if kind == "run":
            out.append(tactic_proposal("Mantener la intensidad: el parcial propio se corta si se baja el ritmo"))
        out.append(tactic_proposal("Defensa del saque tras el tiempo muerto: cerrar la primera jugada del rival y el saque de fondo"))
        for pid, name in zip(player_ids or [], who or []):
            out.append(tactic_proposal(f"Aprovechar la parada para dar descanso a {name}", pid, name))
        return out
    if kind == "run":
        causes = run_causes(own_w, rival_w, names, cfg)
        answers = [_ANSWER[c["kind"]] for c in causes if c["kind"] in _ANSWER]
        out += [tactic_proposal(a) for a in answers] or [tactic_proposal("Defensa alternativa: cambiar de defensa (zona o presión al balón) y cortar el ritmo del rival")]
    elif kind == "turnovers":
        out.append(tactic_proposal(_ANSWER["turnovers"]))
    elif kind == "rival_scoring":
        out.append(tactic_proposal("Cambiar la defensa: el rival está anotando casi todo lo que tira (ayudas, defensa del balón o cambio de emparejamientos)"))
    elif kind == "drought":
        out.append(tactic_proposal("Jugada preparada para la primera posesión: atacar el aro o buscar al mejor tirador"))
    elif kind == "last_possession":
        out.append(tactic_proposal("Preparar la última posesión: jugada para el mejor tirador y cerrar la defensa del último tiro"))
    elif kind == "fatigue":
        out += [tactic_proposal(f"Dar descanso a {name}", pid, name) for pid, name in zip(player_ids or [], who or [])]
    if kind in ("none", "run") or not out:
        out.append(tactic_proposal("Definir la primera jugada tras el tiempo muerto"))
    return out
