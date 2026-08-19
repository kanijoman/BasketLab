"""Possession analyzer — aggregated duration/efficiency stats from play-by-play."""
from __future__ import annotations

from typing import Any, Dict, List

from ._possession_helpers import (
    detect_and1_indices,
    detect_offensive_rebounds,
    detect_shooting_foul_indices,
    ft_sequence_info,
    get_opponent_team,
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


class PossessionAnalyzer:
    """Aggregated pace/OER stats per team from play-by-play data."""

    def __init__(self, game_data: Dict, is_fbcyl: bool = False):
        self.game_data = game_data
        self.is_fbcyl = is_fbcyl
        if is_fbcyl:
            self.moves = game_data.get("moves", [])
        else:
            pbp = game_data.get("PLAYBYPLAY", {})
            self.moves = pbp.get("LINES", [])
        self.team_mapping = self._get_team_mapping()

    def _get_team_mapping(self) -> Dict[str, str]:
        if self.is_fbcyl:
            stats = self.game_data.get("stats", {})
            teams = stats.get("teams", [])
            if len(teams) >= 2:
                t1 = teams[0].get("teamIdIntern") or teams[0].get("teamIdExtern")
                t2 = teams[1].get("teamIdIntern") or teams[1].get("teamIdExtern")
                return {t1: "team1", t2: "team2"}
        else:
            teams = self.game_data.get("HEADER", {}).get("TEAM", [])
            if len(teams) >= 2:
                return {teams[0].get("id"): "team1", teams[1].get("id"): "team2"}
        return {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_possessions(self, team_id: str) -> Dict[str, Any]:
        """Return aggregated possession stats: total, avg duration, per-bucket OER."""
        team_id_str = str(team_id)
        moves_sorted = sorted(self.moves, key=lambda m: get_timestamp(m, self.is_fbcyl))
        orebs = detect_offensive_rebounds(moves_sorted, self.is_fbcyl)
        sfouls = detect_shooting_foul_indices(moves_sorted, self.is_fbcyl)
        and1s = detect_and1_indices(moves_sorted, self.is_fbcyl)
        possessions = self._run_possession_state_machine(
            moves_sorted, team_id_str, orebs, sfouls, and1s
        )
        return self._aggregate_possession_stats(possessions)

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def _run_possession_state_machine(
        self,
        moves: List[Dict],
        team_id_str: str,
        orebs: set,
        sfouls: set,
        and1s: set,
    ) -> List[Dict]:
        possessions: List[Dict] = []
        current_team = None
        start_time = 0
        points = 0

        all_ids = {str(m.get("idTeam") or "") for m in moves if m.get("idTeam")} - {team_id_str, ""}
        opp_id = all_ids.pop() if all_ids else team_id_str

        def _flush(end_ts: int) -> None:
            nonlocal current_team, start_time, points
            if current_team != team_id_str:
                current_team = None
                points = 0
                return
            dur = end_ts - start_time
            if 0 < dur <= 90:
                possessions.append({"duration": dur, "points": points,
                                    "start_time": start_time, "end_time": end_ts})
            current_team = None
            points = 0

        for i, move in enumerate(moves):
            tid = str(move.get("idTeam") or "")
            ts = get_timestamp(move, self.is_fbcyl)
            action = str(move.get("action") or "").lower()
            text = str(move.get("move") or "") if self.is_fbcyl else str(move.get("text") or "")
            text_u = text.upper()

            # FEB period markers — flush on explicit period boundary
            if action == "period" or not tid:
                if action == "period":
                    _flush(ts)
                    start_time = 0
                continue

            # Quarter / period boundary detected via attribute change
            if i > 0:
                prev = moves[i - 1]
                changed = (
                    self.is_fbcyl and move.get("period") != prev.get("period")
                ) or (
                    not self.is_fbcyl
                    and str(move.get("quarter")) != str(prev.get("quarter"))
                )
                if changed:
                    _flush(ts)
                    start_time = 0

            possession_change = False
            new_team = None
            pts_scored = 0
            opp = opp_id if tid == team_id_str else team_id_str

            # 1. Made field goals (FEB)
            if not self.is_fbcyl:
                if "TIRO DE 2" in text_u and "FALLADO" not in text_u and "FALLA" not in text_u:
                    pts_scored = 2
                    if i not in and1s:
                        possession_change, new_team = True, opp
                elif (("TIRO DE 3" in text_u or "TRIPLE" in text_u)
                      and "FALLADO" not in text_u and "FALLA" not in text_u):
                    pts_scored = 3
                    if i not in and1s:
                        possession_change, new_team = True, opp
                elif is_ft_event(move, False):
                    is_last, _ = ft_sequence_info(i, moves, False)
                    if not is_missed_ft(move, False):
                        pts_scored = 1
                    if is_last and not (is_missed_ft(move, False) and i in orebs):
                        possession_change, new_team = True, opp
            else:
                # 1. Made field goals (FBCYL)
                if "Canasta de 2" in text:
                    pts_scored = 2
                    if i not in and1s:
                        possession_change, new_team = True, opp
                elif "Canasta de 3" in text:
                    pts_scored = 3
                    if i not in and1s:
                        possession_change, new_team = True, opp
                elif is_ft_event(move, True):
                    is_last, _ = ft_sequence_info(i, moves, True)
                    if not is_missed_ft(move, True):
                        pts_scored = 1
                    if is_last and not (is_missed_ft(move, True) and i in orebs):
                        possession_change, new_team = True, opp

            # 2. Turnovers
            if is_turnover(move, self.is_fbcyl):
                possession_change, new_team = True, opp

            # 3. Missed field goals (not OReb continuations, not shooting fouls)
            if is_missed_fg(move, self.is_fbcyl) and i not in orebs and i not in sfouls:
                possession_change, new_team = True, opp

            # 4. Defensive rebounds
            if is_rebound(move, self.is_fbcyl):
                for lb in range(1, min(3, i + 1)):
                    prev = moves[i - lb]
                    prev_act = str(prev.get("action") or "").lower()
                    if prev_act in _NEUTRAL:
                        continue
                    prev_tid = str(prev.get("idTeam") or "")
                    prev_txt = str(prev.get("move") or "") if self.is_fbcyl else str(prev.get("text") or "")
                    prev_u = prev_txt.upper()
                    if is_missed_fg(prev, self.is_fbcyl) or is_missed_ft(prev, self.is_fbcyl):
                        if prev_tid != tid:
                            possession_change, new_team = True, tid
                        break
                    if (("ANOTADO" in prev_u and "FALLADO" not in prev_u)
                            or "PÉRDIDA" in prev_u or "PERDIDA" in prev_u):
                        break
                    if prev_act in ("rebound", "steal") or "REBOTE" in prev_u or "ROBO" in prev_u:
                        break

            # 5. Steals
            if is_steal(move, self.is_fbcyl):
                possession_change, new_team = True, tid

            # Accumulate points for current possession owner
            if current_team == tid and pts_scored > 0:
                points += pts_scored

            # Handle possession change
            if possession_change and new_team and (current_team is None or current_team != new_team):
                _flush(ts)
                current_team = new_team
                start_time = ts
                points = pts_scored if new_team == tid else 0

        return possessions

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def _aggregate_possession_stats(self, possessions: List[Dict]) -> Dict[str, Any]:
        if not possessions:
            return {
                "total_possessions": 0,
                "avg_duration": 0.0,
                "possessions_by_duration": {
                    "<=8s":  {"count": 0, "percentage": 0.0, "total_points": 0, "oer": 0.0},
                    "8-16s": {"count": 0, "percentage": 0.0, "total_points": 0, "oer": 0.0},
                    ">16s":  {"count": 0, "percentage": 0.0, "total_points": 0, "oer": 0.0},
                },
            }

        short = [p for p in possessions if p["duration"] <= 8]
        med   = [p for p in possessions if 8 < p["duration"] <= 16]
        long_ = [p for p in possessions if p["duration"] > 16]
        total = len(possessions)
        avg   = sum(p["duration"] for p in possessions) / total

        def _bucket(lst):
            cnt = len(lst)
            pts = sum(p["points"] for p in lst)
            return {
                "count": cnt,
                "percentage": round(cnt / total * 100, 1),
                "total_points": pts,
                "oer": round(pts / cnt * 100, 2) if cnt else 0.0,
            }

        return {
            "total_possessions": total,
            "avg_duration": round(avg, 2),
            "possessions_by_duration": {
                "<=8s":  _bucket(short),
                "8-16s": _bucket(med),
                ">16s":  _bucket(long_),
            },
        }

    # ------------------------------------------------------------------
    # Backward-compatible wrappers (used by existing tests)
    # ------------------------------------------------------------------

    def _get_timestamp(self, move: Dict) -> int:
        return get_timestamp(move, self.is_fbcyl)

    def _get_points_from_move(self, move: Dict) -> int:
        return points_from_move(move, self.is_fbcyl)

    def _get_opponent_team(self, team_id: str, moves: List[Dict]) -> str:
        return get_opponent_team(team_id, moves)

    def _is_possession_ending_event(self, move: Dict) -> bool:
        text = str(move.get("move") or "") if self.is_fbcyl else str(move.get("text") or "")
        text_u = text.upper()
        action = str(move.get("action") or "").lower()
        if self.is_fbcyl:
            return (
                "Canasta de 2" in text or "Canasta de 3" in text
                or "Pérdida" in text or "pérdida" in text
                or "Canasta de 1" in text
            )
        made_fg = (
            ("TIRO DE 2" in text_u or "CANASTA DE 2" in text_u
             or "TIRO DE 3" in text_u or "CANASTA DE 3" in text_u or "TRIPLE" in text_u)
            and "FALLADO" not in text_u and "FALLA" not in text_u
        )
        turnover = "PÉRDIDA" in text_u or "PERDIDA" in text_u or action in ("turnover", "lose")
        made_ft = "TIRO LIBRE" in text_u and "ANOTADO" in text_u
        return made_fg or turnover or made_ft
