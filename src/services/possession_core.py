"""Shared possession reconstruction core used by multiple consumers."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from src.database._possession_helpers import (
    detect_and1_indices,
    detect_offensive_rebounds,
    detect_shooting_foul_indices,
    detect_steal_turnover_indices,
    ft_sequence_info,
    get_timestamp,
    is_ft_event,
    is_missed_fg,
    is_missed_ft,
    is_rebound,
    is_steal,
    is_turnover,
    points_from_move,
)

_NEUTRAL = frozenset(("subst", "foul", "timeout", "assist"))
QUALITY_METRICS = ("T2M", "T2A", "T3M", "T3A", "T1M", "T1A", "RebO", "RebD", "TOV")


def is_controversial_possession(duration: int, points: int) -> bool:
    """Flag possessions that should be reviewed in quality workflows."""
    if duration == 0 and points > 0:
        return True
    if duration > 90:
        return True
    if duration > 40:
        return True
    return False


def order_possession_moves(moves: List[Dict], is_fbcyl: bool) -> List[Dict]:
    """Return deterministic chronological order for possession reconstruction."""

    def _sort_key(move: Dict) -> Tuple[int, int, int]:
        ts = get_timestamp(move, is_fbcyl)
        event_number = int(move.get("num") or 0) if not is_fbcyl else 0
        ft_points = 0
        if not is_fbcyl:
            text = str(move.get("text") or "")
            if "TIRO DE 1" in text.upper() or "TIRO LIBRE" in text.upper():
                match = re.search(r"Puntos:\s*(\d+)", text)
                if match:
                    ft_points = int(match.group(1))
        return ts, event_number, ft_points

    return sorted(moves, key=_sort_key)


def extract_possession_rows(
    game_data: Dict,
    is_fbcyl: bool,
    game_id: str,
    team_info: Dict[str, Dict],
) -> List[Dict]:
    """Return canonical possession rows used by exporter and analyzer."""
    engine = _PossessionExtractionEngine(game_data, is_fbcyl, game_id, team_info)
    return engine.run()


class _PossessionExtractionEngine:
    """Stateful extractor that keeps transition logic in focused methods."""

    def __init__(self, game_data: Dict, is_fbcyl: bool, game_id: str, team_info: Dict[str, Dict]):
        self.game_data = game_data
        self.is_fbcyl = is_fbcyl
        self.game_id = game_id
        self.team_info = team_info
        self.moves = order_possession_moves(_get_moves(game_data, is_fbcyl), is_fbcyl)
        self.orebs = detect_offensive_rebounds(self.moves, is_fbcyl)
        self.sfouls = detect_shooting_foul_indices(self.moves, is_fbcyl)
        self.and1s = detect_and1_indices(self.moves, is_fbcyl)
        self.steal_tovs = detect_steal_turnover_indices(self.moves, is_fbcyl)

        self.rows: List[Dict] = []
        self.team_ids = list(team_info.keys())
        self.opp_map = {
            self.team_ids[0]: self.team_ids[1],
            self.team_ids[1]: self.team_ids[0],
        } if len(self.team_ids) >= 2 else {}

        self.current_team: Optional[str] = None
        self.start_ts: int = 0
        self.start_idx: int = 0
        self.poss_pts: int = 0
        self.prev_ending: Optional[str] = None
        self.is_period_start: bool = True
        self.this_poss_has_orb: bool = False
        self.running_score: Dict[str, int] = {}
        self.start_score: Dict[str, int] = {}

    def run(self) -> List[Dict]:
        if len(self.team_ids) < 2:
            return []
        for i, move in enumerate(self.moves):
            if self._handle_period_marker(i, move):
                continue
            if self._handle_period_boundary(i, move):
                continue
            self._handle_team_move(i, move)
        if self.current_team is not None and self.moves:
            self._close(len(self.moves) - 1, self.moves[-1], self.poss_pts)
        return self.rows

    def _handle_period_marker(self, idx: int, move: Dict) -> bool:
        tid = str(move.get("idTeam") or "")
        action = str(move.get("action") or "").lower()
        if action != "period" and tid:
            return False
        if action == "period":
            if self.current_team is not None:
                self._close(idx, move, self.poss_pts)
            self.is_period_start = True
        return True

    def _handle_period_boundary(self, idx: int, move: Dict) -> bool:
        if idx <= 0:
            return False
        if not _period_changed(move, self.moves[idx - 1], self.is_fbcyl):
            return False
        if self.current_team is not None:
            self._close(idx, move, self.poss_pts)
        self.is_period_start = True
        return False

    def _handle_team_move(self, idx: int, move: Dict) -> None:
        tid = str(move.get("idTeam") or "")
        if tid not in self.team_ids:
            return
        ts = get_timestamp(move, self.is_fbcyl)
        action = str(move.get("action") or "").lower()
        text = str(move.get("move") or "") if self.is_fbcyl else str(move.get("text") or "")
        opp = self.opp_map.get(tid, tid)

        self._apply_ownership_corrections(idx, move, tid, ts)
        possession_change, new_team, pts_scored = self._apply_event_rules(idx, move, tid, opp, text)

        if self.current_team == tid and pts_scored > 0:
            self.poss_pts += pts_scored
        if self.current_team is None and action not in _NEUTRAL:
            self._switch(tid, ts, idx, pts_scored)
            pts_scored = 0
        if possession_change and new_team and (self.current_team is None or self.current_team != new_team):
            self._close(idx, move, self.poss_pts)
            self._switch(new_team, ts, idx, pts_scored if new_team == tid else 0)

    def _apply_ownership_corrections(self, idx: int, move: Dict, tid: str, ts: int) -> None:
        if self.current_team is None or self.current_team == tid:
            return
        if is_turnover(move, self.is_fbcyl) or _is_shot_attempt(move, self.is_fbcyl):
            self._close(idx, move, self.poss_pts, is_correction=True)
            self._switch(tid, ts, idx, 0)

    def _apply_event_rules(
        self,
        idx: int,
        move: Dict,
        tid: str,
        opp: str,
        text: str,
    ) -> Tuple[bool, Optional[str], int]:
        possession_change, new_team, pts_scored = self._apply_scoring_rules(idx, move, opp, text)
        possession_change, new_team = self._apply_turnover_rule(move, opp, possession_change, new_team)
        possession_change, new_team = self._apply_missed_fg_rule(idx, move, opp, possession_change, new_team)
        possession_change, new_team = self._apply_rebound_rule(idx, move, tid, possession_change, new_team)
        possession_change, new_team = self._apply_steal_rules(idx, move, tid, opp, possession_change, new_team)
        return possession_change, new_team, pts_scored

    def _apply_scoring_rules(self, idx: int, move: Dict, opp: str, text: str) -> Tuple[bool, Optional[str], int]:
        if self.is_fbcyl:
            return self._apply_fbcyl_scoring_rules(idx, move, opp, text)
        return self._apply_feb_scoring_rules(idx, move, opp, text)

    def _apply_feb_scoring_rules(self, idx: int, move: Dict, opp: str, text: str) -> Tuple[bool, Optional[str], int]:
        text_u = text.upper()
        if "TIRO DE 2" in text_u and "FALLADO" not in text_u and "FALLA" not in text_u:
            return self._scoring_result(idx, opp, 2)
        if "TIRO DE 3" in text_u or "TRIPLE" in text_u:
            if "FALLADO" not in text_u and "FALLA" not in text_u:
                return self._scoring_result(idx, opp, 3)
            return False, None, 0
        if not is_ft_event(move, False):
            return False, None, 0
        return self._ft_scoring_result(idx, move, opp, False)

    def _apply_fbcyl_scoring_rules(self, idx: int, move: Dict, opp: str, text: str) -> Tuple[bool, Optional[str], int]:
        if "Canasta de 2" in text:
            return self._scoring_result(idx, opp, 2)
        if "Canasta de 3" in text:
            return self._scoring_result(idx, opp, 3)
        if not is_ft_event(move, True):
            return False, None, 0
        return self._ft_scoring_result(idx, move, opp, True)

    def _scoring_result(self, idx: int, opp: str, points: int) -> Tuple[bool, Optional[str], int]:
        if idx in self.and1s:
            return False, None, points
        return True, opp, points

    def _ft_scoring_result(self, idx: int, move: Dict, opp: str, is_fbcyl: bool) -> Tuple[bool, Optional[str], int]:
        is_last, _ = ft_sequence_info(idx, self.moves, is_fbcyl)
        scored = 0 if is_missed_ft(move, is_fbcyl) else 1
        if is_last and not (is_missed_ft(move, is_fbcyl) and idx in self.orebs):
            return True, opp, scored
        return False, None, scored

    def _apply_turnover_rule(
        self,
        move: Dict,
        opp: str,
        possession_change: bool,
        new_team: Optional[str],
    ) -> Tuple[bool, Optional[str]]:
        if not is_turnover(move, self.is_fbcyl):
            return possession_change, new_team
        return True, opp

    def _apply_missed_fg_rule(
        self,
        idx: int,
        move: Dict,
        opp: str,
        possession_change: bool,
        new_team: Optional[str],
    ) -> Tuple[bool, Optional[str]]:
        if not is_missed_fg(move, self.is_fbcyl) or idx in self.sfouls:
            return possession_change, new_team
        if idx in self.orebs:
            self.this_poss_has_orb = True
            return possession_change, new_team
        return True, opp

    def _apply_rebound_rule(
        self,
        idx: int,
        move: Dict,
        tid: str,
        possession_change: bool,
        new_team: Optional[str],
    ) -> Tuple[bool, Optional[str]]:
        if not is_rebound(move, self.is_fbcyl):
            return possession_change, new_team
        new_owner = self._defensive_rebound_owner(idx, tid)
        if new_owner is None:
            return possession_change, new_team
        return True, new_owner

    def _defensive_rebound_owner(self, idx: int, tid: str) -> Optional[str]:
        for lb in range(1, min(3, idx + 1)):
            prev_move = self.moves[idx - lb]
            action = str(prev_move.get("action") or "").lower()
            if action in _NEUTRAL:
                continue
            if self._is_rebound_breaker(prev_move):
                return None
            if is_missed_fg(prev_move, self.is_fbcyl) or is_missed_ft(prev_move, self.is_fbcyl):
                prev_tid = str(prev_move.get("idTeam") or "")
                return tid if prev_tid != tid else None
        return None

    def _is_rebound_breaker(self, move: Dict) -> bool:
        text = str(move.get("move") or "") if self.is_fbcyl else str(move.get("text") or "")
        text_u = text.upper()
        if ("ANOTADO" in text_u and "FALLADO" not in text_u) or "PÉRDIDA" in text_u or "PERDIDA" in text_u:
            return True
        return str(move.get("action") or "").lower() in ("rebound", "steal")

    def _apply_steal_rules(
        self,
        idx: int,
        move: Dict,
        tid: str,
        opp: str,
        possession_change: bool,
        new_team: Optional[str],
    ) -> Tuple[bool, Optional[str]]:
        if self._needs_steal_pretransfer(idx, move, tid):
            self.current_team = opp
            self.poss_pts = 0
        if not is_steal(move, self.is_fbcyl):
            return possession_change, new_team
        return True, tid

    def _needs_steal_pretransfer(self, idx: int, move: Dict, tid: str) -> bool:
        if not is_steal(move, self.is_fbcyl):
            return False
        if self.current_team is None or self.current_team != tid:
            return False
        ts = get_timestamp(move, self.is_fbcyl)
        return self._has_following_turnover_same_timestamp(idx, tid, ts)

    def _has_following_turnover_same_timestamp(self, idx: int, team_id: str, ts: int) -> bool:
        for fw in range(idx + 1, min(idx + 5, len(self.moves))):
            nxt = self.moves[fw]
            nxt_action = str(nxt.get("action") or "").lower()
            if nxt_action in _NEUTRAL:
                continue
            nxt_ts = get_timestamp(nxt, self.is_fbcyl)
            if nxt_ts != ts:
                break
            nxt_tid = str(nxt.get("idTeam") or "")
            return nxt_tid != team_id and is_turnover(nxt, self.is_fbcyl)
        return False

    def _switch(self, new_team: str, ts: int, idx: int, starting_pts: int) -> None:
        self.current_team = new_team
        self.start_ts = _period_start_timestamp(self.moves[idx], self.is_fbcyl) if self.is_period_start else ts
        self.start_idx = idx
        self.poss_pts = starting_pts
        self.start_score = dict(self.running_score)

    def _close(self, end_idx: int, ending_move: Dict, ending_pts: int, is_correction: bool = False) -> None:
        if self.current_team is None:
            return
        end_ts = get_timestamp(ending_move, self.is_fbcyl)
        duration = max(0, end_ts - self.start_ts)
        ending_type = "otro" if is_correction else _classify_ending(
            ending_move, ending_pts, end_idx, self.steal_tovs, self.is_fbcyl
        )
        start_move = self.moves[self.start_idx] if self.start_idx < len(self.moves) else None
        origin = _classify_origin(self.prev_ending, start_move, self.is_period_start)
        row = self._build_row(ending_pts, ending_type, origin, duration)
        self.rows.append(row)
        self._reset_after_close(ending_pts, ending_type)

    def _build_row(self, ending_pts: int, ending_type: str, origin: str, duration: int) -> Dict:
        rival_id = self.opp_map.get(self.current_team or "", "")
        info = self.team_info.get(self.current_team or "", {})
        rival_info = self.team_info.get(rival_id, {})
        quarter_key = "period" if self.is_fbcyl else "quarter"
        quarter = self.moves[self.start_idx].get(quarter_key, "?") if self.start_idx < len(self.moves) else "?"
        start_move = self.moves[self.start_idx] if self.start_idx < len(self.moves) else None
        my_pts = self.start_score.get(self.current_team or "", 0)
        opp_pts = self.start_score.get(rival_id, 0)
        return {
            "ID_Partido": self.game_id,
            "Equipo": info.get("name", self.current_team),
            "Equipo_ID": self.current_team,
            "Rival": rival_info.get("name", rival_id),
            "Rival_ID": rival_id,
            "Local_Visitante": info.get("home_away", ""),
            "Cuarto": quarter,
            "Tiempo_de_juego": _quarter_clock(start_move, self.is_fbcyl),
            "Diferencia_marcador": my_pts - opp_pts,
            "Origen_posesion": origin,
            "Duracion_posesion": duration,
            "Tipo_finalizacion": ending_type,
            "Puntos_obtenidos": ending_pts,
            "Tiene_rebote_ofensivo": 1 if self.this_poss_has_orb else 0,
            "Controversial_Possession": is_controversial_possession(duration, ending_pts),
        }

    def _reset_after_close(self, ending_pts: int, ending_type: str) -> None:
        self.prev_ending = ending_type
        self.is_period_start = False
        self.this_poss_has_orb = False
        if self.current_team is not None:
            self.running_score[self.current_team] = self.running_score.get(self.current_team, 0) + ending_pts
        self.current_team = None
        self.poss_pts = 0


def count_quality_pbp_metrics(game_data: Dict, is_fbcyl: bool, team_ids: List[str]) -> Dict[str, Dict[str, int]]:
    """Count per-team quality metrics from PBP using shared ordering and rebound lookup."""
    counts = {tid: {metric: 0 for metric in QUALITY_METRICS} for tid in team_ids}
    moves = order_possession_moves(_get_moves(game_data, is_fbcyl), is_fbcyl)
    orebs = detect_offensive_rebounds(moves, is_fbcyl)

    for idx, move in enumerate(moves):
        tid = str(move.get("idTeam") or "")
        if tid not in counts:
            continue
        _update_quality_counts_for_move(counts[tid], moves, idx, orebs, is_fbcyl)
    return counts


def previous_missed_shot_index(moves: List[Dict], rebound_idx: int, is_fbcyl: bool) -> Optional[int]:
    """Return index of the closest preceding missed shot linked to a rebound event."""
    for offset in range(1, min(5, rebound_idx + 1)):
        previous_idx = rebound_idx - offset
        previous = moves[previous_idx]
        action = str(previous.get("action") or "").lower()
        if action in _NEUTRAL:
            continue
        if is_missed_fg(previous, is_fbcyl) or is_missed_ft(previous, is_fbcyl):
            return previous_idx
        text = str(previous.get("move") or "") if is_fbcyl else str(previous.get("text") or "")
        text_upper = text.upper()
        if ("ANOTADO" in text_upper and "FALLADO" not in text_upper) or is_turnover(previous, is_fbcyl):
            break
        if action in ("rebound", "steal") or "REBOTE" in text_upper or "ROBO" in text_upper:
            break
    return None


def _update_quality_counts_for_move(
    team_counts: Dict[str, int],
    moves: List[Dict],
    idx: int,
    orebs: set,
    is_fbcyl: bool,
) -> None:
    move = moves[idx]
    text = str(move.get("move") or "") if is_fbcyl else str(move.get("text") or "")
    if _count_ft_quality_event(team_counts, move, is_fbcyl):
        return
    if _count_fg_quality_event(team_counts, move, text, is_fbcyl):
        return
    if not is_fbcyl and is_rebound(move, is_fbcyl) and not move.get("idPlayer"):
        return  # team rebound (no player) — official boxscore ro/rd totals don't credit these
    if _count_rebound_quality_event(team_counts, moves, idx, orebs, is_fbcyl):
        return
    if is_turnover(move, is_fbcyl):
        team_counts["TOV"] += 1


def _count_ft_quality_event(team_counts: Dict[str, int], move: Dict, is_fbcyl: bool) -> bool:
    if not is_ft_event(move, is_fbcyl):
        return False
    team_counts["T1A"] += 1
    if not is_missed_ft(move, is_fbcyl):
        team_counts["T1M"] += 1
    return True


def _count_fg_quality_event(team_counts: Dict[str, int], move: Dict, text: str, is_fbcyl: bool) -> bool:
    text_u = text.upper()
    if not is_fbcyl:
        if "TIRO DE 3" in text_u or "TRIPLE" in text_u:
            team_counts["T3A"] += 1
            if "FALLADO" not in text_u and "FALLA" not in text_u:
                team_counts["T3M"] += 1
            return True
        if "TIRO DE 2" in text_u:
            team_counts["T2A"] += 1
            if "FALLADO" not in text_u and "FALLA" not in text_u:
                team_counts["T2M"] += 1
            return True
        return False

    text_l = text.lower()
    if "Canasta de 3" in text or "Intento fallado de 3" in text or ("fallado" in text_l and "de 3" in text_l):
        team_counts["T3A"] += 1
        if "Canasta de 3" in text:
            team_counts["T3M"] += 1
        return True
    if "Canasta de 2" in text or "Intento fallado de 2" in text or ("fallado" in text_l and "de 2" in text_l):
        team_counts["T2A"] += 1
        if "Canasta de 2" in text:
            team_counts["T2M"] += 1
        return True
    if is_missed_fg(move, is_fbcyl):
        team_counts["T2A"] += 1
        return True
    return False


def _count_rebound_quality_event(
    team_counts: Dict[str, int],
    moves: List[Dict],
    idx: int,
    orebs: set,
    is_fbcyl: bool,
) -> bool:
    move = moves[idx]
    if not is_rebound(move, is_fbcyl):
        return False
    missed_idx = previous_missed_shot_index(moves, idx, is_fbcyl)
    if missed_idx in orebs:
        team_counts["RebO"] += 1
        return True
    if missed_idx is None:
        return True
    prev_tid = str(moves[missed_idx].get("idTeam") or "")
    curr_tid = str(move.get("idTeam") or "")
    if prev_tid != curr_tid:
        team_counts["RebD"] += 1
    return True


def _get_moves(game_data: Dict, is_fbcyl: bool) -> List[Dict]:
    if is_fbcyl:
        return game_data.get("moves", [])
    return game_data.get("PLAYBYPLAY", {}).get("LINES", [])


def _is_shot_attempt(move: Dict, is_fbcyl: bool) -> bool:
    text = str(move.get("move") or "") if is_fbcyl else str(move.get("text") or "")
    text_u = text.upper()
    return (
        is_ft_event(move, is_fbcyl)
        or is_missed_fg(move, is_fbcyl)
        or (not is_fbcyl and ("TIRO DE 2" in text_u or "TIRO DE 3" in text_u or "TRIPLE" in text_u)
            and "FALLADO" not in text_u and "FALLA" not in text_u)
        or (is_fbcyl and ("Canasta de 2" in text or "Canasta de 3" in text))
    )


def _period_changed(curr: Dict, prev: Dict, is_fbcyl: bool) -> bool:
    if is_fbcyl:
        return curr.get("period") != prev.get("period")
    return str(curr.get("quarter") or "") != str(prev.get("quarter") or "")


def _classify_ending(move: Dict, points: int, idx: int, steal_tovs: frozenset, is_fbcyl: bool) -> str:
    text = str(move.get("move") or "") if is_fbcyl else str(move.get("text") or "")
    text_u = text.upper()
    if is_turnover(move, is_fbcyl):
        return "recuperacion" if idx in steal_tovs else "violacion"
    if is_missed_fg(move, is_fbcyl):
        return "tiro_fallado"
    if is_ft_event(move, is_fbcyl) or is_missed_ft(move, is_fbcyl):
        return "tiros_libres"
    effective_pts = points if points > 0 else points_from_move(move, is_fbcyl)
    if effective_pts == 3:
        return "triple"
    if effective_pts == 2:
        if "BANDEJA" in text_u or "LAYUP" in text_u or "bandeja" in text.lower():
            return "bandeja"
        if "MATE" in text_u or "SLAM" in text_u or "mate" in text.lower():
            return "mate"
        return "tiro_2"
    if effective_pts >= 1:
        return "tiros_libres"
    if is_rebound(move, is_fbcyl):
        return "rebote_defensivo"
    if is_steal(move, is_fbcyl):
        return "recuperacion"
    return "otro"


def _classify_origin(prev_ending: Optional[str], start_move: Optional[Dict], is_period_start: bool) -> str:
    del start_move
    if is_period_start:
        return "saque_inicial_periodo"
    if prev_ending is None:
        return "inicio_partido"
    if prev_ending in ("rebote_defensivo", "tiro_fallado"):
        return "rebote_defensivo"
    if prev_ending == "recuperacion":
        return "recuperacion"
    if prev_ending == "violacion":
        return "violacion"
    return "saque_fondo"


def _quarter_clock(move: Optional[Dict], is_fbcyl: bool) -> str:
    if move is None:
        return "10:00"
    if is_fbcyl:
        period = int(move.get("period") or 1)
        quarter_secs = 300 if period > 4 else 600
        elapsed = int(move.get("min") or 0) * 60 + int(move.get("sec") or 0)
        remaining = max(0, quarter_secs - elapsed)
        mins, secs = divmod(remaining, 60)
        return f"{mins:02d}:{secs:02d}"
    raw = str(move.get("time") or "10:00")
    return raw if ":" in raw else "10:00"


def _period_start_timestamp(move: Dict, is_fbcyl: bool) -> int:
    period = int(move.get("period" if is_fbcyl else "quarter") or 1)
    if period > 4:
        return 4 * 600 + (period - 5) * 300
    return (period - 1) * 600
