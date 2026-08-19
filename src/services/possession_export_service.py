"""Per-possession CSV export service for possession analysis."""
from __future__ import annotations

import csv
import io
from typing import Any, Dict, Iterator, List, Optional

from src.database._possession_helpers import (
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

_KNOWN_ENDINGS = frozenset((
    "perdida", "triple", "tiro_2", "bandeja", "mate",
    "tiros_libres", "tiro_fallado", "rebote_defensivo", "recuperacion", "otro",
))


class PossessionExportService:
    """Extracts per-possession rows ready for CSV export from a single game document."""

    CSV_COLUMNS = [
        "ID_Partido", "Equipo", "Equipo_ID", "Rival", "Rival_ID",
        "Local_Visitante", "Cuarto", "Tiempo_de_juego",
        "Diferencia_marcador", "Origen_posesion", "Duracion_posesion",
        "Tipo_finalizacion", "Puntos_obtenidos",
    ]

    def __init__(self, game_data: Dict, is_fbcyl: bool, game_id: str):
        self.game_data = game_data
        self.is_fbcyl = is_fbcyl
        self.game_id = game_id
        if is_fbcyl:
            self.moves: List[Dict] = game_data.get("moves", [])
        else:
            pbp = game_data.get("PLAYBYPLAY", {})
            self.moves = pbp.get("LINES", [])
        self.team_info: Dict[str, Dict] = self._build_team_info()

    # ------------------------------------------------------------------
    # Team metadata
    # ------------------------------------------------------------------

    def _build_team_info(self) -> Dict[str, Dict]:
        result: Dict[str, Dict] = {}
        if self.is_fbcyl:
            teams = self.game_data.get("stats", {}).get("teams", [])
            for idx, team in enumerate(teams[:2]):
                tid = str(team.get("teamIdIntern") or team.get("teamIdExtern") or "")
                result[tid] = {
                    "name": team.get("name") or team.get("shortName") or tid,
                    "home_away": "Local" if idx == 0 else "Visitante",
                }
        else:
            for idx, team in enumerate(self.game_data.get("HEADER", {}).get("TEAM", [])[:2]):
                tid = str(team.get("id") or "")
                result[tid] = {
                    "name": team.get("name") or tid,
                    "home_away": "Local" if idx == 0 else "Visitante",
                }
        return result

    # ------------------------------------------------------------------
    # Running score
    # ------------------------------------------------------------------

    def _running_score(self, moves: List[Dict], up_to: int) -> Dict[str, int]:
        score: Dict[str, int] = {}
        for m in moves[:up_to]:
            tid = str(m.get("idTeam") or "")
            pts = points_from_move(m, self.is_fbcyl)
            if tid and pts > 0:
                score[tid] = score.get(tid, 0) + pts
        return score

    # ------------------------------------------------------------------
    # Classifiers
    # ------------------------------------------------------------------

    def _classify_ending(self, move: Dict, points: int) -> str:
        text = str(move.get("move") or "") if self.is_fbcyl else str(move.get("text") or "")
        text_u = text.upper()
        if is_turnover(move, self.is_fbcyl):
            return "perdida"
        if is_missed_fg(move, self.is_fbcyl):
            return "tiro_fallado"
        # Free-throw ending (1 or more FTs scored in this possession)
        if is_ft_event(move, self.is_fbcyl) or is_missed_ft(move, self.is_fbcyl):
            return "tiros_libres"
        if points == 3:
            return "triple"
        if points == 2:
            if "BANDEJA" in text_u or "LAYUP" in text_u or "bandeja" in text.lower():
                return "bandeja"
            if "MATE" in text_u or "SLAM" in text_u or "mate" in text.lower():
                return "mate"
            return "tiro_2"
        if points >= 1:
            return "tiros_libres"
        if is_rebound(move, self.is_fbcyl):
            return "rebote_defensivo"
        if is_steal(move, self.is_fbcyl):
            return "recuperacion"
        return "otro"

    def _classify_origin(
        self,
        prev_ending: Optional[str],
        start_move: Optional[Dict],
        is_period_start: bool,
    ) -> str:
        if is_period_start:
            return "saque_inicial_periodo"
        if prev_ending is None:
            return "inicio_partido"
        if prev_ending in ("rebote_defensivo", "tiro_fallado"):
            return "rebote_defensivo"
        if prev_ending == "recuperacion":
            return "recuperacion"
        if prev_ending == "perdida":
            return "saque_fondo"
        if prev_ending in ("tiro_2", "triple", "tiros_libres", "bandeja", "mate"):
            return "saque_fondo"
        return "otro"

    # ------------------------------------------------------------------
    # Core extraction
    # ------------------------------------------------------------------

    def extract_possessions(self) -> List[Dict]:
        """Return one dict per possession with all CSV columns populated."""

        def _sort_key(m: Dict) -> tuple:
            ts = get_timestamp(m, self.is_fbcyl)
            # For FEB, sort FTs within same timestamp by "Puntos" ascending
            # so earlier FTs (lower cumulative score) come first.
            if not self.is_fbcyl:
                t = str(m.get("text") or "")
                if ("TIRO DE 1" in t.upper() or "TIRO LIBRE" in t.upper()):
                    import re
                    m_pts = re.search(r"Puntos:\s*(\d+)", t)
                    if m_pts:
                        return (ts, int(m_pts.group(1)))
            return (ts, 0)

        moves = sorted(self.moves, key=_sort_key)
        orebs = detect_offensive_rebounds(moves, self.is_fbcyl)
        sfouls = detect_shooting_foul_indices(moves, self.is_fbcyl)
        and1s = detect_and1_indices(moves, self.is_fbcyl)

        rows: List[Dict] = []

        # State
        current_team: Optional[str] = None
        start_ts: int = 0
        start_idx: int = 0
        poss_pts: int = 0
        prev_ending: Optional[str] = None
        last_quarter: Optional[Any] = None
        is_period_start: bool = True
        poss_id: int = 0

        team_ids = list(self.team_info.keys())
        if len(team_ids) < 2:
            return rows

        opp_map: Dict[str, str] = {
            team_ids[0]: team_ids[1],
            team_ids[1]: team_ids[0],
        }

        def _close(end_idx: int, ending_move: Dict, ending_pts: int) -> None:
            nonlocal current_team, start_ts, start_idx, poss_pts, prev_ending, poss_id, is_period_start
            if current_team is None:
                return
            end_ts = get_timestamp(ending_move, self.is_fbcyl)
            duration = end_ts - start_ts
            if duration < 0:
                duration = 0

            ending_type = self._classify_ending(ending_move, ending_pts)
            origin = self._classify_origin(prev_ending, moves[start_idx] if start_idx < len(moves) else None, is_period_start)

            score = self._running_score(moves, start_idx)
            my_pts = score.get(current_team, 0)
            opp_pts_val = score.get(opp_map.get(current_team, ""), 0)
            diff = my_pts - opp_pts_val

            info = self.team_info.get(current_team, {})
            rival_id = opp_map.get(current_team, "")
            rival_info = self.team_info.get(rival_id, {})

            q = moves[start_idx].get("period" if self.is_fbcyl else "quarter", "?") if start_idx < len(moves) else "?"
            start_move = moves[start_idx] if start_idx < len(moves) else None
            time_str = _quarter_clock(start_move, self.is_fbcyl)

            poss_id += 1
            rows.append({
                "ID_Partido": self.game_id,
                "Equipo": info.get("name", current_team),
                "Equipo_ID": current_team,
                "Rival": rival_info.get("name", rival_id),
                "Rival_ID": rival_id,
                "Local_Visitante": info.get("home_away", ""),
                "Cuarto": q,
                "Tiempo_de_juego": time_str,
                "Diferencia_marcador": diff,
                "Origen_posesion": origin,
                "Duracion_posesion": max(0, duration),
                "Tipo_finalizacion": ending_type,
                "Puntos_obtenidos": ending_pts,
            })
            prev_ending = ending_type
            is_period_start = False
            current_team = None
            poss_pts = 0

        def _switch(new_team: str, ts: int, idx: int, starting_pts: int) -> None:
            nonlocal current_team, start_ts, start_idx, poss_pts
            current_team = new_team
            start_ts = ts
            start_idx = idx
            poss_pts = starting_pts

        for i, move in enumerate(moves):
            tid = str(move.get("idTeam") or "")
            ts = get_timestamp(move, self.is_fbcyl)
            action = str(move.get("action") or "").lower()
            text = str(move.get("move") or "") if self.is_fbcyl else str(move.get("text") or "")

            if action == "period" or not tid:
                if action == "period":
                    if current_team is not None:
                        _close(i, move, poss_pts)
                    is_period_start = True
                continue

            # Quarter / period boundary
            if i > 0:
                prev = moves[i - 1]
                changed = (
                    self.is_fbcyl and move.get("period") != prev.get("period")
                ) or (
                    not self.is_fbcyl
                    and str(move.get("quarter")) != str(prev.get("quarter"))
                )
                if changed:
                    if current_team is not None:
                        _close(i, move, poss_pts)
                    is_period_start = True

            if tid not in team_ids:
                continue

            opp = opp_map.get(tid, tid)
            possession_change = False
            new_team: Optional[str] = None
            pts_scored = 0

            # FT shooting means the fouled team controls the ball.
            # For any scoring event, if the tracker has the wrong team, fix it.
            _is_scoring_event = (
                is_ft_event(move, self.is_fbcyl)
                or (
                    not self.is_fbcyl and (
                        ("TIRO DE 2" in text.upper() or "TIRO DE 3" in text.upper() or "TRIPLE" in text.upper())
                        and "FALLADO" not in text.upper() and "FALLA" not in text.upper()
                    )
                )
                or (
                    self.is_fbcyl and ("Canasta de 2" in text or "Canasta de 3" in text)
                )
            )
            if _is_scoring_event and current_team is not None and current_team != tid:
                _close(i, move, poss_pts)
                _switch(tid, ts, i, 0)

            # Made FGs
            if not self.is_fbcyl:
                text_u = text.upper()
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

            if is_turnover(move, self.is_fbcyl):
                possession_change, new_team = True, opp

            if is_missed_fg(move, self.is_fbcyl) and i not in orebs and i not in sfouls:
                possession_change, new_team = True, opp

            if is_rebound(move, self.is_fbcyl):
                for lb in range(1, min(3, i + 1)):
                    prev_m = moves[i - lb]
                    if str(prev_m.get("action") or "").lower() in _NEUTRAL:
                        continue
                    prev_tid = str(prev_m.get("idTeam") or "")
                    prev_txt = str(prev_m.get("move") or "") if self.is_fbcyl else str(prev_m.get("text") or "")
                    prev_u = prev_txt.upper()
                    if is_missed_fg(prev_m, self.is_fbcyl) or is_missed_ft(prev_m, self.is_fbcyl):
                        if prev_tid != tid:
                            possession_change, new_team = True, tid
                        break
                    if (("ANOTADO" in prev_u and "FALLADO" not in prev_u)
                            or "PÉRDIDA" in prev_u or "PERDIDA" in prev_u):
                        break
                    if str(prev_m.get("action") or "").lower() in ("rebound", "steal"):
                        break

            if is_steal(move, self.is_fbcyl):
                possession_change, new_team = True, tid

            # Accumulate
            if current_team == tid and pts_scored > 0:
                poss_pts += pts_scored

            # If no active possession yet, start one for the team that just acted
            if current_team is None and tid in team_ids:
                _switch(tid, ts, i, pts_scored)
                pts_scored = 0  # already captured in poss_pts via _switch

            # Possession change
            if possession_change and new_team and (current_team is None or current_team != new_team):
                ending_pts = poss_pts
                _close(i, move, ending_pts)
                _switch(new_team, ts, i, pts_scored if new_team == tid else 0)

        # Flush any remaining possession at end of game
        if current_team is not None and poss_pts > 0 and moves:
            _close(len(moves) - 1, moves[-1], poss_pts)

        return rows

    # ------------------------------------------------------------------
    # CSV rendering
    # ------------------------------------------------------------------

    def to_csv_bytes(self) -> bytes:
        rows = self.extract_possessions()
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=self.CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8-sig")

    # ------------------------------------------------------------------
    # Collection iteration helper
    # ------------------------------------------------------------------

    @staticmethod
    def iter_collection(
        db_handler: Any,
        collection_name: str,
        team_id: Optional[str] = None,
    ) -> Iterator[Dict]:
        """Yield raw game documents from *collection_name* that contain play-by-play."""
        repo = db_handler.repository
        is_fbcyl = "FBCYL" in collection_name.upper()

        pbp_filter: Dict = {}
        if is_fbcyl:
            pbp_filter = {"moves": {"$exists": True, "$not": {"$size": 0}}}
            if team_id:
                pbp_filter["stats.teams.teamIdIntern"] = team_id
        else:
            pbp_filter = {"PLAYBYPLAY.LINES": {"$exists": True, "$not": {"$size": 0}}}
            if team_id:
                pbp_filter["$or"] = [
                    {"HEADER.TEAM.0.id": team_id},
                    {"HEADER.TEAM.1.id": team_id},
                ]

        try:
            col = repo.connection.get_collection(collection_name)
            yield from col.find(pbp_filter)
        except Exception:
            return


def _quarter_clock(move: Optional[Dict], is_fbcyl: bool) -> str:
    """Game clock within the quarter, counting down (e.g. '08:34')."""
    if move is None:
        return "10:00"
    if is_fbcyl:
        period = int(move.get("period") or 1)
        quarter_secs = 300 if period > 4 else 600
        elapsed = int(move.get("min") or 0) * 60 + int(move.get("sec") or 0)
        remaining = max(0, quarter_secs - elapsed)
    else:
        raw = str(move.get("time") or "10:00")
        # FEB 'time' field is already a countdown clock string (e.g. '08:34')
        return raw if ":" in raw else "10:00"
    m, s = divmod(remaining, 60)
    return f"{m:02d}:{s:02d}"


def _format_time(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def _classify_ending(move: Dict, points: int) -> str:
    """Module-level convenience — delegates to PossessionExportService._classify_ending."""
    svc = PossessionExportService.__new__(PossessionExportService)
    svc.is_fbcyl = False  # not used directly
    return svc._classify_ending(move, points)
