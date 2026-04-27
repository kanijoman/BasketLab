"""Weekly report service.

Generates a ZIP bundle of PNG images equivalent to the Qt WeeklyReportGenerator.
No PyQt6 dependency — matplotlib Agg backend (via _weekly_report_helpers) is used
for all table rendering; ShotChartVisualizer / ZoneAnalyzer are already headless.

ZIP structure (mirrors Qt output folder):
    General/
        01_Basicas_Toda_Competicion.png
        01_Avanzadas_Toda_Competicion.png
        02_Basicas_Ganados_vs_Perdidos.png
        02_Avanzadas_Ganados_vs_Perdidos.png
        03_Basicas_Local_vs_Visitante.png
        03_Avanzadas_Local_vs_Visitante.png
        04_Basicas_Ultimo_Mes.png
        04_Avanzadas_Ultimo_Mes.png
        05_Ultimo_Partido_{team_a}.png
        05_Ultimo_Partido_{team_b}.png
    {team_a}/
        1_Estadisticas_Individuales/
            01_{team_a}_Promedios.png
            02_{team_a}_Totales.png
            03_{team_a}_Proyeccion_30min.png
        2_Graficos_Lanzamiento/
            Equipo/{team_a}_Mapa_Calor.png, {team_a}_Zonas.png
            Jugadoras/{player}/{player}_Mapa_Calor.png, {player}_Zonas.png
    {team_b}/  (same structure)
"""
from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from utils.collection_utils import is_fbcyl as _is_fbcyl
from stats.stats_calculator import StatsCalculator
from shotcharts import ShotChartVisualizer
from shotcharts.zone_analysis import ZoneAnalyzer
from shotcharts.coordinate_utils import convert_shots_for_zone_analysis

from src.services._weekly_report_helpers import (
    render_table_png, fig_to_png,
    BASIC_HEADERS, ADV_HEADERS, LAST_MATCH_ADV_HEADERS,
    build_basic_rows, build_advanced_rows,
    build_comparative_basic_rows, build_comparative_advanced_rows,
    build_last_match_rows, build_player_rows,
    CONSISTENCY_HEADERS, build_consistency_rows,
)


def _sanitize(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()


# ---------------------------------------------------------------------------
# FBCYL per-team aggregation helper
# ---------------------------------------------------------------------------

def _aggregate_fbcyl_players(players: List[Dict]) -> Dict:
    keys = (
        'shotsOfTwoAttempted', 'shotsOfTwoSuccessful',
        'shotsOfThreeAttempted', 'shotsOfThreeSuccessful',
        'shotsOfOneAttempted', 'shotsOfOneSuccessful',
        'offensiveRebound', 'defensiveRebound',
        'lost', 'assists', 'steals', 'block', 'score',
    )
    totals = {k: 0 for k in keys}
    for player in players:
        data = player.get('data', {})
        for k in keys:
            totals[k] += data.get(k, 0)
    return {
        'p2a': totals['shotsOfTwoAttempted'], 'p2m': totals['shotsOfTwoSuccessful'],
        'p3a': totals['shotsOfThreeAttempted'], 'p3m': totals['shotsOfThreeSuccessful'],
        'p1a': totals['shotsOfOneAttempted'],   'p1m': totals['shotsOfOneSuccessful'],
        'ro':  totals['offensiveRebound'],      'rd':  totals['defensiveRebound'],
        'to':  totals['lost'], 'assist': totals['assists'],
        'st':  totals['steals'], 'bs': totals['block'], 'pts': totals['score'],
    }


# ---------------------------------------------------------------------------
# Shot extraction helper (FEB + FBCYL)
# ---------------------------------------------------------------------------

def _extract_shots(
    db: Any, collection_name: str, team_name: str,
) -> Tuple[List[Dict], Dict, bool]:
    """Return (all_shots, player_id_map, is_fbcyl) for a team across all games."""
    from src.utils.team_utils import get_team_data_by_name, get_team_index_in_document

    coll = db.connection.get_collection(collection_name)
    if coll is None:
        return [], {}, False

    documents = list(coll.find({}))
    is_fbcyl  = _is_fbcyl(collection_name)

    all_shots:    List[Dict] = []
    player_id_map: Dict      = {}

    if is_fbcyl:
        for doc in documents:
            if 'stats' not in doc or 'teams' not in doc['stats']:
                continue
            for team_idx, team in enumerate(doc['stats']['teams']):
                if team.get('name') != team_name:
                    continue
                for player in team.get('players', []):
                    uuid   = player.get('uuid', '')
                    pname  = player.get('name', '')
                    data   = player.get('data', {})
                    common = {'team': str(team_idx), 'player': uuid,
                              'player_uuid': uuid, 'player_name': pname}
                    for coord in data.get('shootingOfTwoSuccessfulPoint', []):
                        if isinstance(coord, dict) and 'xnormalize' in coord:
                            all_shots.append({**common, 'x': coord['xnormalize'],
                                              'y': coord['ynormalize'], 'm': 1, 'value': 2})
                    for coord in data.get('shootingOfTwoFailedPoint', []):
                        if isinstance(coord, dict) and 'xnormalize' in coord:
                            all_shots.append({**common, 'x': coord['xnormalize'],
                                              'y': coord['ynormalize'], 'm': 0, 'value': 2})
                    for coord in data.get('shootingOfThreeSuccessfulPoint', []):
                        if isinstance(coord, dict) and 'xnormalize' in coord:
                            all_shots.append({**common, 'x': coord['xnormalize'],
                                              'y': coord['ynormalize'], 'm': 1, 'value': 3})
                    for coord in data.get('shootingOfThreeFailedPoint', []):
                        if isinstance(coord, dict) and 'xnormalize' in coord:
                            all_shots.append({**common, 'x': coord['xnormalize'],
                                              'y': coord['ynormalize'], 'm': 0, 'value': 3})
                    if uuid:
                        player_id_map[uuid] = {'id': uuid, 'name': pname, 'uuid': uuid}
    else:
        # FEB: discover team code first
        team_code = None
        for doc in documents:
            td, _ = get_team_data_by_name(doc, team_name)
            if td is not None:
                team_code = td.get('teamCode') or td.get('code')
                break

        for doc in documents:
            if 'SHOTCHART' not in doc or not doc.get('SHOTCHART'):
                continue
            shots_raw  = doc['SHOTCHART'].get('SHOTS', [])
            team_index = get_team_index_in_document(doc, team_code)
            if team_index is None:
                continue
            shotchart = doc['SHOTCHART']
            if 'TEAM' in shotchart and team_index < len(shotchart['TEAM']):
                for pl in shotchart['TEAM'][team_index].get('PLAYER', []):
                    raw_no  = str(pl.get('no', ''))
                    stripped = raw_no.lstrip('0') or raw_no
                    pid = str(pl.get('id', ''))
                    if pid:
                        info = {'id': pid, 'name': pl.get('name', ''), 'dorsal': raw_no}
                        player_id_map[(team_index, raw_no)]   = info
                        player_id_map[(team_index, stripped)] = info
            for shot in shots_raw:
                try:
                    ti = int(shot.get('team'))
                except (TypeError, ValueError):
                    continue
                if ti != team_index:
                    continue
                sc     = shot.copy()
                dorsal = str(shot.get('player', ''))
                key    = (team_index, dorsal)
                if key in player_id_map:
                    sc['player_id']     = player_id_map[key]['id']
                    sc['player_name']   = player_id_map[key]['name']
                    sc['player_dorsal'] = player_id_map[key]['dorsal']
                all_shots.append(sc)

    return all_shots, player_id_map, is_fbcyl


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

class WeeklyReportService:
    """Generate a ZIP of PNG images matching Qt WeeklyReportGenerator output."""

    def __init__(self, db_handler: Any) -> None:
        self._db    = db_handler
        self._vis   = ShotChartVisualizer()
        self._zones = ZoneAnalyzer(detail_level='detailed')
        self._calc  = StatsCalculator()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def generate_report_zip(self, collection: str, team_a: str, team_b: str) -> bytes:
        """Return ZIP bytes with the full weekly report."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            self._gen_general_stats(zf, collection)
            self._gen_last_match(zf, collection, team_a)
            self._gen_last_match(zf, collection, team_b)
            self._gen_team_report(zf, collection, team_a)
            self._gen_team_report(zf, collection, team_b)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # General competition stats (10 PNGs)
    # ------------------------------------------------------------------

    def _gen_general_stats(self, zf: zipfile.ZipFile, collection: str) -> None:
        ts = self._db.get_team_stats(collection) or []
        if ts:
            rows, cols = build_basic_rows(ts)
            zf.writestr('General/01_Basicas_Toda_Competicion.png',
                        render_table_png(BASIC_HEADERS, rows, cols,
                                        'Estadísticas Básicas - Toda la Competición'))
            rows, cols = build_advanced_rows(ts)
            zf.writestr('General/01_Avanzadas_Toda_Competicion.png',
                        render_table_png(ADV_HEADERS, rows, cols,
                                        'Estadísticas Avanzadas - Toda la Competición'))

        self._gen_compare_result(zf, collection, 'won', 'lost',
                                 'Ganados vs Perdidos', '02')
        self._gen_compare_venue(zf, collection, 'Local vs Visitante', '03')
        self._gen_compare_month(zf, collection, 'Último Mes', '04')
        self._gen_consistency_png(zf, collection)

    def _gen_consistency_png(
        self, zf: zipfile.ZipFile, collection: str,
    ) -> None:
        """Add a league-wide consistency (CV) table PNG to the General/ folder."""
        try:
            from src.services.team_stats_service import TeamStatsService
            consistency = TeamStatsService(self._db).get_consistency(collection)
            own_map = consistency.get("own", {})
            if not own_map:
                return
            rows, cols = build_consistency_rows(own_map)
            if not rows:
                return
            zf.writestr(
                'General/06_Consistencia_Liga.png',
                render_table_png(CONSISTENCY_HEADERS, rows, cols,
                                 'Consistencia Intraequipo - CV% (menor = más consistente)'),
            )
        except Exception as exc:
            print(f'[WeeklyReportService] consistency_png: {exc}')

    def _gen_compare_result(
        self, zf: zipfile.ZipFile, collection: str,
        res1: str, res2: str, label: str, prefix: str,
    ) -> None:
        ts1 = self._db.get_team_stats(collection, result_filter=res1) or []
        ts2 = self._db.get_team_stats(collection, result_filter=res2) or []
        self._write_comparative(zf, ts1, ts2, label, prefix)

    def _gen_compare_venue(
        self, zf: zipfile.ZipFile, collection: str, label: str, prefix: str,
    ) -> None:
        ts1 = self._db.get_team_stats(collection, venue_filter=True) or []
        ts2 = self._db.get_team_stats(collection, venue_filter=False) or []
        self._write_comparative(zf, ts1, ts2, label, prefix)

    def _gen_compare_month(
        self, zf: zipfile.ZipFile, collection: str, label: str, prefix: str,
    ) -> None:
        one_month_ago = datetime.now() - timedelta(days=30)
        ts1 = self._db.get_team_stats(collection, date_filter={'$gte': one_month_ago}) or []
        ts2 = self._db.get_team_stats(collection, date_filter={'$lt': one_month_ago}) or []
        self._write_comparative(zf, ts1, ts2, label, prefix)

    def _write_comparative(
        self, zf: zipfile.ZipFile,
        ts1: List[Dict], ts2: List[Dict],
        label: str, prefix: str,
    ) -> None:
        if not (ts1 and ts2):
            return
        d1 = {str(t['_id']): t for t in ts1}
        d2 = {str(t['_id']): t for t in ts2}
        comp = [self._calc.create_comparative_stat(d1[k], d2[k]) for k in (set(d1) & set(d2))]
        if not comp:
            return
        rows, cols = build_comparative_basic_rows(comp)
        zf.writestr(f'General/{prefix}_Basicas_{label.replace(" ", "_")}.png',
                    render_table_png(BASIC_HEADERS, rows, cols,
                                    f'Estadísticas Básicas - {label}'))
        rows, cols = build_comparative_advanced_rows(comp)
        zf.writestr(f'General/{prefix}_Avanzadas_{label.replace(" ", "_")}.png',
                    render_table_png(ADV_HEADERS, rows, cols,
                                    f'Estadísticas Avanzadas - {label}'))

    # ------------------------------------------------------------------
    # Last match (1 PNG per team in General/)
    # ------------------------------------------------------------------

    def _gen_last_match(
        self, zf: zipfile.ZipFile, collection: str, team_name: str,
    ) -> None:
        try:
            last = self._db.get_last_match(collection, team_name)
            if not last:
                return
            season_ts = self._db.get_team_stats(collection) or []
            if not season_ts:
                return

            from src.utils.team_utils import get_team_data_by_name
            is_fbcyl = 'stats' in last and 'teams' in last.get('stats', {})

            if is_fbcyl:
                teams_data = last['stats'].get('teams', [])
                if len(teams_data) != 2:
                    return
                sel_dict, sel_idx = get_team_data_by_name(last, team_name)
                if sel_dict is None:
                    return
                opp_dict   = teams_data[1 - sel_idx]
                sel_raw    = _aggregate_fbcyl_players(sel_dict.get('players', []))
                opp_raw    = _aggregate_fbcyl_players(opp_dict.get('players', []))
                sel_stats  = self._calc.calculate_single_match_stats(sel_raw, opp_raw)
                opp_stats  = self._calc.calculate_single_match_stats(opp_raw, sel_raw)
                opp_name   = opp_dict.get('name', '')
                match_date = last['stats'].get('startDate', '')[:10]
            else:
                boxscore  = last.get('BOXSCORE', {})
                teams_box = boxscore.get('TEAM', [])
                if len(teams_box) != 2:
                    return
                sel_dict, sel_idx = get_team_data_by_name(last, team_name)
                if sel_dict is None:
                    return
                sel_total  = teams_box[sel_idx].get('TOTAL', {})
                opp_total  = teams_box[1 - sel_idx].get('TOTAL', {})
                sel_stats  = self._calc.calculate_single_match_stats(sel_total, opp_total)
                opp_stats  = self._calc.calculate_single_match_stats(opp_total, sel_total)
                opp_name   = opp_total.get('name', '')
                match_date = str(last.get('HEADER', {}).get('starttime', ''))[:10]

            sel_season = next((t for t in season_ts if t.get('team_name') == team_name), None)
            opp_season = next((t for t in season_ts if t.get('team_name') == opp_name), None)
            if not sel_season or not opp_season:
                return

            rows_t, rows_c = build_last_match_rows(
                sel_stats, opp_stats, sel_season, opp_season, team_name, opp_name)
            safe = _sanitize(team_name)
            zf.writestr(
                f'General/05_Ultimo_Partido_{safe}.png',
                render_table_png(LAST_MATCH_ADV_HEADERS, rows_t, rows_c,
                                f'Último Partido - {team_name} - {match_date}'),
            )
        except Exception as exc:
            print(f'[WeeklyReportService] last_match {team_name}: {exc}')

    # ------------------------------------------------------------------
    # Per-team report
    # ------------------------------------------------------------------

    def _gen_team_report(
        self, zf: zipfile.ZipFile, collection: str, team_name: str,
    ) -> None:
        safe = _sanitize(team_name)
        self._gen_player_tables(zf, collection, team_name, safe)
        self._gen_shot_charts(zf, collection, team_name, safe)

    def _gen_player_tables(
        self, zf: zipfile.ZipFile, collection: str, team_name: str, folder: str,
    ) -> None:
        try:
            all_players = self._db.get_player_stats(collection) or []
            players = [p for p in all_players if p.get('team_name') == team_name]
            if not players:
                return
            safe   = _sanitize(team_name)
            prefix = f'{folder}/1_Estadisticas_Individuales'
            for mode, num, label in [
                ('avg',        '01', 'Promedios'),
                ('total',      '02', 'Totales'),
                ('projection', '03', 'Proyeccion_30min'),
            ]:
                headers, rows, cols = build_player_rows(players, mode)
                zf.writestr(
                    f'{prefix}/{num}_{safe}_{label}.png',
                    render_table_png(headers, rows, cols,
                                    f'{team_name} - {label.replace("_", " ")}'),
                )
        except Exception as exc:
            print(f'[WeeklyReportService] player_tables {team_name}: {exc}')

    def _gen_shot_charts(
        self, zf: zipfile.ZipFile, collection: str, team_name: str, folder: str,
    ) -> None:
        try:
            shots, player_map, is_fbcyl = _extract_shots(self._db, collection, team_name)
            if not shots:
                return

            safe         = _sanitize(team_name)
            team_prefix  = f'{folder}/2_Graficos_Lanzamiento/Equipo'
            player_prefix = f'{folder}/2_Graficos_Lanzamiento/Jugadoras'

            # Team charts
            made = sum(1 for s in shots if int(s.get('m', 0)) == 1)
            tot  = len(shots)
            acc  = (made / tot * 100) if tot > 0 else 0
            title = f'{team_name}\n{made}/{tot} ({acc:.1f}%)'
            fig = self._vis.plot_heatmap(shots=shots, title=title, figsize=(10, 10), alpha=0.6)
            zf.writestr(f'{team_prefix}/{safe}_Mapa_Calor.png', fig_to_png(fig))

            processed = convert_shots_for_zone_analysis(shots)
            stats_z   = self._zones.analyze_zone_performance(processed)
            fig = self._zones.plot_zone_analysis(
                stats=stats_z,
                title=f'{team_name} - Análisis por Zonas\n{made}/{tot} ({acc:.1f}%)',
                figsize=(10, 10))
            zf.writestr(f'{team_prefix}/{safe}_Zonas.png', fig_to_png(fig))

            # Per-player charts
            by_player: Dict[str, List[Dict]] = {}
            for shot in shots:
                pid = shot.get('player_uuid') if is_fbcyl else shot.get('player_id', '')
                if pid:
                    by_player.setdefault(str(pid), []).append(shot)

            for pid, pshots in by_player.items():
                if len(pshots) < 5:
                    continue
                pname   = pshots[0].get('player_name', f'Jugador {pid}')
                safe_p  = _sanitize(pname if is_fbcyl
                                    else f"{pshots[0].get('player_dorsal', '')}_{pname}")
                ptitle  = pname if is_fbcyl else f"{pname} (#{pshots[0].get('player_dorsal', '')})"
                pm      = sum(1 for s in pshots if int(s.get('m', 0)) == 1)
                pt      = len(pshots)
                pa      = (pm / pt * 100) if pt > 0 else 0
                ctitle  = f'{ptitle}\n{pm}/{pt} ({pa:.1f}%)'

                fig = self._vis.plot_heatmap(shots=pshots, title=ctitle,
                                             figsize=(10, 10), alpha=0.6)
                zf.writestr(f'{player_prefix}/{safe_p}/{safe_p}_Mapa_Calor.png', fig_to_png(fig))

                pp     = convert_shots_for_zone_analysis(pshots)
                zstats = self._zones.analyze_zone_performance(pp)
                fig = self._zones.plot_zone_analysis(
                    stats=zstats,
                    title=f'{ptitle} - Análisis por Zonas\n{pm}/{pt} ({pa:.1f}%)',
                    figsize=(10, 10))
                zf.writestr(f'{player_prefix}/{safe_p}/{safe_p}_Zonas.png', fig_to_png(fig))

        except Exception as exc:
            print(f'[WeeklyReportService] shot_charts {team_name}: {exc}')
