"""State machine that turns ordered play-by-play moves into possession rows."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .event_helpers import (
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
)
from .possession_classify import (
    _classify_ending,
    _classify_origin,
    _is_shot_attempt,
    _period_changed,
    _period_start_timestamp,
    _quarter_clock,
    is_controversial_possession,
)
from .possession_moves import _NEUTRAL, _get_moves, order_possession_moves


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
        self._reset_after_close(ending_pts, ending_type, is_correction)

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

    def _reset_after_close(self, ending_pts: int, ending_type: str, is_correction: bool = False) -> None:
        self.prev_ending = ending_type
        # A correction close is a phantom possession, not the period's real first
        # possession — keep the flag so the following real possession gets it.
        if not is_correction:
            self.is_period_start = False
        self.this_poss_has_orb = False
        if self.current_team is not None:
            self.running_score[self.current_team] = self.running_score.get(self.current_team, 0) + ending_pts
        self.current_team = None
        self.poss_pts = 0
