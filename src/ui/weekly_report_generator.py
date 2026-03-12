"""Weekly report generator for basketball team analysis using existing UI components."""

import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from PyQt6.QtWidgets import QApplication, QFileDialog, QTableWidget
from PyQt6.QtCore import QObject, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from database import MongoDBHandler
from shotcharts import ShotChartVisualizer
from shotcharts.zone_analysis import ZoneAnalyzer
from shotcharts.coordinate_utils import convert_shots_for_zone_analysis
from .stats_window import TeamStatsWindow
from .player_stats_window import PlayerStatsWindow
from .shotchart_window import ShotChartWindow
from .stats_filter_constants import RESULT_WON, RESULT_LOST, VENUE_HOME, VENUE_AWAY
from .team_utils import get_team_data_by_name, get_team_index_in_document
from .stats_calculator import StatsCalculator
from .stats_exporter import StatsExporter

from src.utils.collection_utils import is_fbcyl as _is_fbcyl


class WeeklyReportGenerator(QObject):
    """Generate comprehensive weekly reports using existing UI components."""

    progress_updated = pyqtSignal(str, int)
    report_completed = pyqtSignal(bool, str)

    def __init__(self, db_handler: MongoDBHandler, collection_name: str, scraper, parent=None):
        """
        Initialize the report generator.

        Args:
            db_handler: Database handler
            collection_name: MongoDB collection name
            scraper: FEB scraper instance
            parent: Parent QObject
        """
        super().__init__(parent)
        self.db_handler = db_handler
        self.collection_name = collection_name
        self.scraper = scraper
        self.shot_visualizer = ShotChartVisualizer()
        self.zone_analyzer = ZoneAnalyzer(detail_level='detailed')
        self.stats_calculator = StatsCalculator()
        self.stats_exporter = StatsExporter(parent)

    def generate_report(self, team_a_name: str, team_b_name: str, output_folder: str):
        """Generate complete weekly report for two teams."""
        try:
            self.progress_updated.emit("Iniciando generación de informes...", 0)

            # Create folder structure directly in the selected path
            base_path = Path(output_folder)

            # Create general folder for competition-wide stats
            general_folder = base_path / "General"
            general_folder.mkdir(parents=True, exist_ok=True)

            team_a_folder = base_path / self._sanitize_filename(team_a_name)
            team_b_folder = base_path / self._sanitize_filename(team_b_name)
            team_a_folder.mkdir(exist_ok=True)
            team_b_folder.mkdir(exist_ok=True)

            # Generate general competition statistics (once for all teams)
            self.progress_updated.emit("Generando estadísticas generales de la competición...", 5)
            self._generate_general_statistics(general_folder)

            # Generate last match for both teams in general folder
            self.progress_updated.emit(f"Generando último partido de {team_a_name}...", 15)
            self._generate_last_match_stats(team_a_name, general_folder)

            self.progress_updated.emit(f"Generando último partido de {team_b_name}...", 25)
            self._generate_last_match_stats(team_b_name, general_folder)

            # Generate reports for Team A
            self.progress_updated.emit(f"Generando informes para {team_a_name}...", 35)
            self._generate_team_report(team_a_name, team_a_folder)

            # Generate reports for Team B
            self.progress_updated.emit(f"Generando informes para {team_b_name}...", 65)
            self._generate_team_report(team_b_name, team_b_folder)

            self.progress_updated.emit("Informes completados", 100)
            self.report_completed.emit(True, f"Informes generados exitosamente en:\n{base_path}")

        except Exception as e:
            error_msg = f"Error al generar informes: {str(e)}"
            print(f"[WeeklyReportGenerator] {error_msg}")
            self.report_completed.emit(False, error_msg)

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize string for filename."""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        return name.strip()

    def _generate_general_statistics(self, output_folder: Path):
        """Generate general competition statistics for all teams (basic and advanced)."""
        try:
            # Create reload callback
            def reload_stats(coll_name: str, date_filter: dict = None,
                           venue_filter: bool = None, result_filter: str = None):
                team_data = self.db_handler.get_team_stats(coll_name, date_filter, venue_filter, result_filter)
                opponent_data = self.db_handler.get_opponent_stats(coll_name, date_filter, venue_filter, result_filter)
                return team_data, opponent_data

            # Get all stats
            team_stats = self.db_handler.get_team_stats(self.collection_name)
            opponent_stats = self.db_handler.get_opponent_stats(self.collection_name)

            # 1. All competition stats - BASIC and ADVANCED
            if team_stats:
                stats_window = TeamStatsWindow(
                    team_stats,
                    opponent_stats,
                    collection_name=self.collection_name,
                    reload_callback=reload_stats,
                    db_handler=self.db_handler,
                    parent=None
                )
                # Export basic stats (activate basic tab first)
                stats_window.tab_widget.setCurrentIndex(0)  # Basic stats tab
                QApplication.processEvents()
                self._export_table_to_png_improved(
                    stats_window.basic_table,
                    output_folder / f"01_Basicas_Toda_Competicion.png",
                    "Estadísticas Básicas - Toda la Competición"
                )
                # Export advanced stats (activate advanced tab first)
                stats_window.tab_widget.setCurrentIndex(1)  # Advanced stats tab
                QApplication.processEvents()
                self._export_table_to_png_improved(
                    stats_window.advanced_table,
                    output_folder / f"01_Avanzadas_Toda_Competicion.png",
                    "Estadísticas Avanzadas - Toda la Competición"
                )
                stats_window.deleteLater()

            # 2. Won vs Lost - COMPARATIVE MODE
            won_stats = self.db_handler.get_team_stats(self.collection_name, result_filter=RESULT_WON)
            lost_stats = self.db_handler.get_team_stats(self.collection_name, result_filter=RESULT_LOST)

            if won_stats and lost_stats:
                comparative_stats = self._create_comparative_stats(won_stats, lost_stats)

                if comparative_stats:
                    stats_window = TeamStatsWindow(
                        won_stats,
                        opponent_stats,
                        collection_name=self.collection_name,
                        reload_callback=reload_stats,
                        db_handler=self.db_handler,
                        parent=None
                    )
                    self._populate_comparative_table(stats_window.basic_table, comparative_stats, won_stats, is_basic=True)
                    stats_window.tab_widget.setCurrentIndex(0)  # Basic stats tab
                    QApplication.processEvents()
                    self._export_table_to_png_improved(
                        stats_window.basic_table,
                        output_folder / f"02_Basicas_Ganados_vs_Perdidos.png",
                        "Estadísticas Básicas - Ganados vs Perdidos"
                    )
                    self._populate_comparative_table(stats_window.advanced_table, comparative_stats, won_stats, is_basic=False)
                    stats_window.tab_widget.setCurrentIndex(1)  # Advanced stats tab
                    QApplication.processEvents()
                    self._export_table_to_png_improved(
                        stats_window.advanced_table,
                        output_folder / f"02_Avanzadas_Ganados_vs_Perdidos.png",
                        "Estadísticas Avanzadas - Ganados vs Perdidos"
                    )
                    stats_window.deleteLater()

            # 3. Home vs Away - COMPARATIVE MODE
            home_stats = self.db_handler.get_team_stats(self.collection_name, venue_filter=VENUE_HOME)
            away_stats = self.db_handler.get_team_stats(self.collection_name, venue_filter=VENUE_AWAY)

            if home_stats and away_stats:
                comparative_stats = self._create_comparative_stats(home_stats, away_stats)

                if comparative_stats:
                    stats_window = TeamStatsWindow(
                        home_stats,
                        opponent_stats,
                        collection_name=self.collection_name,
                        reload_callback=reload_stats,
                        db_handler=self.db_handler,
                        parent=None
                    )
                    self._populate_comparative_table(stats_window.basic_table, comparative_stats, home_stats, is_basic=True)
                    stats_window.tab_widget.setCurrentIndex(0)  # Basic stats tab
                    QApplication.processEvents()
                    self._export_table_to_png_improved(
                        stats_window.basic_table,
                        output_folder / f"03_Basicas_Local_vs_Visitante.png",
                        "Estadísticas Básicas - Local vs Visitante"
                    )
                    self._populate_comparative_table(stats_window.advanced_table, comparative_stats, home_stats, is_basic=False)
                    stats_window.tab_widget.setCurrentIndex(1)  # Advanced stats tab
                    QApplication.processEvents()
                    self._export_table_to_png_improved(
                        stats_window.advanced_table,
                        output_folder / f"03_Avanzadas_Local_vs_Visitante.png",
                        "Estadísticas Avanzadas - Local vs Visitante"
                    )
                    stats_window.deleteLater()

            # 4. Last month - COMPARATIVE MODE
            one_month_ago = datetime.now() - timedelta(days=30)
            date_filter = {"$gte": one_month_ago}
            month_stats = self.db_handler.get_team_stats(self.collection_name, date_filter=date_filter)
            rest_stats = self.db_handler.get_team_stats(self.collection_name, date_filter={"$lt": one_month_ago})

            if month_stats and rest_stats:
                comparative_stats = self._create_comparative_stats(month_stats, rest_stats)

                if comparative_stats:
                    stats_window = TeamStatsWindow(
                        month_stats,
                        opponent_stats,
                        collection_name=self.collection_name,
                        reload_callback=reload_stats,
                        db_handler=self.db_handler,
                        parent=None
                    )
                    self._populate_comparative_table(stats_window.basic_table, comparative_stats, month_stats, is_basic=True)
                    stats_window.tab_widget.setCurrentIndex(0)  # Basic stats tab
                    QApplication.processEvents()
                    self._export_table_to_png_improved(
                        stats_window.basic_table,
                        output_folder / f"04_Basicas_Ultimo_Mes.png",
                        "Estadísticas Básicas - Último Mes"
                    )
                    self._populate_comparative_table(stats_window.advanced_table, comparative_stats, month_stats, is_basic=False)
                    stats_window.tab_widget.setCurrentIndex(1)  # Advanced stats tab
                    QApplication.processEvents()
                    self._export_table_to_png_improved(
                        stats_window.advanced_table,
                        output_folder / f"04_Avanzadas_Ultimo_Mes.png",
                        "Estadísticas Avanzadas - Último Mes"
                    )
                    stats_window.deleteLater()

        except Exception as e:
            print(f"[WeeklyReportGenerator] Error generating general statistics: {e}")

    def _generate_team_report(self, team_name: str, output_folder: Path):
        """Generate all reports for a single team."""
        players_folder = output_folder / "1_Estadisticas_Individuales"
        shotcharts_folder = output_folder / "2_Graficos_Lanzamiento"
        players_folder.mkdir(exist_ok=True)
        shotcharts_folder.mkdir(exist_ok=True)

        # Generate player statistics using existing UI
        self._generate_player_statistics_ui(team_name, players_folder)

        # Generate shot charts
        self._generate_shot_charts_ui(team_name, shotcharts_folder)

    def _create_comparative_stats(self, period1_stats: list, period2_stats: list) -> list:
        """
        Create comparative statistics avoiding duplicates using team_id.
        Only includes teams with data in BOTH periods.

        Args:
            period1_stats: Stats for first period (e.g., won games, home games, last month)
            period2_stats: Stats for second period (e.g., lost games, away games, rest of season)

        Returns:
            List of comparative stats with trends
        """
        # Create dictionaries by team_id to avoid duplicates
        period1_dict = {str(team["_id"]): team for team in period1_stats}
        period2_dict = {str(team["_id"]): team for team in period2_stats}

        # Get teams that exist in BOTH periods
        common_team_ids = set(period1_dict.keys()) & set(period2_dict.keys())

        # Create comparative stats for common teams
        comparative_stats = []
        for team_id in common_team_ids:
            period1_data = period1_dict[team_id]
            period2_data = period2_dict[team_id]

            # Use stats calculator to create comparative stat with trends
            comp_stat = self.stats_calculator.create_comparative_stat(period1_data, period2_data)
            comparative_stats.append(comp_stat)

        return comparative_stats

    def _populate_comparative_table(self, table: QTableWidget, comparative_stats: list, period1_stats: list, is_basic: bool = True):
        """
        Populate table with comparative statistics.

        Args:
            table: QTableWidget to populate
            comparative_stats: List of comparative stats with trends
            period1_stats: Stats from first period (for quartile calculations)
            is_basic: True for basic table, False for advanced table
        """
        from .stats_config import get_basic_numeric_data, get_advanced_numeric_data, calculate_quartiles
        from .stats_table_manager import StatsTableManager
        from .trend_calculator import TrendCalculator

        # Get numeric data and quartiles for styling
        if is_basic:
            numeric_data = get_basic_numeric_data(period1_stats)
        else:
            numeric_data = get_advanced_numeric_data(period1_stats)

        quartiles = {key: calculate_quartiles(values) for key, (values, _) in numeric_data.items()}

        # Create trend calculator and table manager
        trend_calculator = TrendCalculator()
        table_manager = StatsTableManager(trend_calculator)

        # Clear and populate table
        table.setRowCount(0)
        table.setRowCount(len(comparative_stats))
        table.setSortingEnabled(False)

        for row, stats in enumerate(comparative_stats):
            if is_basic:
                table_manager.populate_comparative_basic_row(
                    table, row, stats, numeric_data, quartiles
                )
            else:
                table_manager.populate_comparative_advanced_row(
                    table, row, stats, numeric_data, quartiles
                )

        table.setSortingEnabled(True)

        # Force update after population
        table.updateGeometry()
        QApplication.processEvents()

    def _generate_player_statistics_ui(self, team_name: str, output_folder: Path):
        """Generate player statistics using PlayerStatsWindow - includes basic, advanced, and projection."""
        try:
            all_player_stats = self.db_handler.get_player_stats(self.collection_name)
            team_players = [p for p in all_player_stats if p.get('team_name') == team_name]

            if not team_players:
                return

            # Create player stats window
            player_window = PlayerStatsWindow(
                team_players,
                collection_name=self.collection_name,
                reload_callback=None,
                db_handler=self.db_handler,
                parent=None
            )

            # 1. Export basic stats (promedios)
            player_window.view_mode = "average"
            player_window.populate_table()
            self._export_table_to_png_improved(
                player_window.table,
                output_folder / f"01_{self._sanitize_filename(team_name)}_Promedios.png",
                f"{team_name} - Promedios por Partido"
            )

            # 2. Export totals
            player_window.view_mode = "total"
            player_window.populate_table()
            self._export_table_to_png_improved(
                player_window.table,
                output_folder / f"02_{self._sanitize_filename(team_name)}_Totales.png",
                f"{team_name} - Totales Acumulados"
            )

            # 3. Export projection to 30 minutes
            player_window.view_mode = "projection"
            player_window.populate_table()
            self._export_table_to_png_improved(
                player_window.table,
                output_folder / f"03_{self._sanitize_filename(team_name)}_Proyeccion_30min.png",
                f"{team_name} - Proyección a 30 Minutos"
            )

            # 4. Export advanced stats if available
            if player_window.advanced_stats_calculated:
                player_window.view_mode = "advanced"
                player_window.populate_table()
                self._export_table_to_png_improved(
                    player_window.table,
                    output_folder / f"04_{self._sanitize_filename(team_name)}_Avanzadas.png",
                    f"{team_name} - Estadísticas Avanzadas"
                )

            player_window.deleteLater()

        except Exception as e:
            print(f"[WeeklyReportGenerator] Error generating player statistics: {e}")

    def _generate_shot_charts_ui(self, team_name: str, output_folder: Path):
        """Generate shot charts using existing chart generation."""
        try:
            # Create subfolders
            team_charts_folder = output_folder / "Equipo"
            player_charts_folder = output_folder / "Jugadoras"
            team_charts_folder.mkdir(exist_ok=True)
            player_charts_folder.mkdir(exist_ok=True)

            # Get all shots for this team
            collection = self.db_handler.connection.get_collection(self.collection_name)
            if collection is None:
                return

            documents = list(collection.find({}))
            if not documents:
                return

            # Detect format
            is_fbcyl = _is_fbcyl(self.collection_name)

            # Find team data
            team_data = None
            team_code = None
            for doc in documents:
                team_dict, team_idx = get_team_data_by_name(doc, team_name)
                if team_dict is not None:
                    team_data = team_dict
                    if is_fbcyl:
                        team_code = team_dict.get('teamIdExtern') or team_dict.get('teamIdIntern')
                    else:
                        team_code = team_dict.get('teamCode') or team_dict.get('code')
                    break

            if not team_data:
                print(f"[WeeklyReportGenerator] Team {team_name} not found")
                return

            # Collect shots
            all_shots = []
            player_id_map = {}

            if is_fbcyl:
                # FBCYL format: extract from player metadata
                for doc in documents:
                    if 'stats' not in doc or 'teams' not in doc['stats']:
                        continue

                    teams = doc['stats']['teams']
                    for team_idx, team in enumerate(teams):
                        if team.get('name') != team_name:
                            continue

                        # Extract shots from player arrays
                        players = team.get('players', [])
                        for player in players:
                            player_uuid = player.get('uuid', '')
                            player_name = player.get('name', '')
                            player_data = player.get('data', {})

                            # Extract successful 2-pointers
                            for coord in player_data.get('shootingOfTwoSuccessfulPoint', []):
                                if isinstance(coord, dict) and 'xnormalize' in coord and 'ynormalize' in coord:
                                    all_shots.append({
                                        'x': coord['xnormalize'], 'y': coord['ynormalize'], 'm': 1, 'value': 2,
                                        'team': str(team_idx), 'player': player_uuid,
                                        'player_uuid': player_uuid, 'player_name': player_name
                                    })

                            # Extract failed 2-pointers
                            for coord in player_data.get('shootingOfTwoFailedPoint', []):
                                if isinstance(coord, dict) and 'xnormalize' in coord and 'ynormalize' in coord:
                                    all_shots.append({
                                        'x': coord['xnormalize'], 'y': coord['ynormalize'], 'm': 0, 'value': 2,
                                        'team': str(team_idx), 'player': player_uuid,
                                        'player_uuid': player_uuid, 'player_name': player_name
                                    })

                            # Extract successful 3-pointers
                            for coord in player_data.get('shootingOfThreeSuccessfulPoint', []):
                                if isinstance(coord, dict) and 'xnormalize' in coord and 'ynormalize' in coord:
                                    all_shots.append({
                                        'x': coord['xnormalize'], 'y': coord['ynormalize'], 'm': 1, 'value': 3,
                                        'team': str(team_idx), 'player': player_uuid,
                                        'player_uuid': player_uuid, 'player_name': player_name
                                    })

                            # Extract failed 3-pointers
                            for coord in player_data.get('shootingOfThreeFailedPoint', []):
                                if isinstance(coord, dict) and 'xnormalize' in coord and 'ynormalize' in coord:
                                    all_shots.append({
                                        'x': coord['xnormalize'], 'y': coord['ynormalize'], 'm': 0, 'value': 3,
                                        'team': str(team_idx), 'player': player_uuid,
                                        'player_uuid': player_uuid, 'player_name': player_name
                                    })

                            # Build player map for FBCYL
                            if player_uuid:
                                player_id_map[player_uuid] = {
                                    'id': player_uuid,
                                    'name': player_name,
                                    'uuid': player_uuid
                                }
            else:
                # FEB format: extract from SHOTCHART
                for doc in documents:
                    if 'SHOTCHART' not in doc or not doc['SHOTCHART']:
                        continue
                    if 'SHOTS' not in doc['SHOTCHART']:
                        continue

                    shots = doc['SHOTCHART']['SHOTS']
                    team_index = get_team_index_in_document(doc, team_code)

                    if team_index is None:
                        continue

                    # Extract player info
                    shotchart = doc['SHOTCHART']
                    if 'TEAM' in shotchart and isinstance(shotchart['TEAM'], list):
                        if team_index < len(shotchart['TEAM']):
                            team_sc_data = shotchart['TEAM'][team_index]
                            if 'PLAYER' in team_sc_data and isinstance(team_sc_data['PLAYER'], list):
                                for player in team_sc_data['PLAYER']:
                                    dorsal = str(player.get('no', '')).lstrip('0') or player.get('no', '')
                                    player_id = player.get('id', '')
                                    player_name = player.get('name', '')

                                    if dorsal and player_id:
                                        key = (team_index, str(dorsal))
                                        player_id_map[key] = {
                                            'id': player_id,
                                            'name': player_name,
                                            'dorsal': str(dorsal)
                                        }

                    # Add shots
                    for shot in shots:
                        if shot.get('team', '') == str(team_index):
                            shot_copy = shot.copy()
                            dorsal = str(shot.get('player', ''))
                            key = (team_index, dorsal)
                            if key in player_id_map:
                                shot_copy['player_id'] = player_id_map[key]['id']
                                shot_copy['player_name'] = player_id_map[key]['name']
                                shot_copy['player_dorsal'] = player_id_map[key]['dorsal']
                            all_shots.append(shot_copy)

            if not all_shots:
                return

            # Generate team charts
            self._save_team_shot_charts(all_shots, team_name, team_charts_folder)

            # Generate player charts
            self._save_player_shot_charts(all_shots, team_name, player_id_map, player_charts_folder, is_fbcyl)

        except Exception as e:
            print(f"[WeeklyReportGenerator] Error generating shot charts: {e}")

    def _export_table_to_png(self, table, output_path: Path, title: str):
        """Export a QTableWidget to PNG."""
        try:
            # Grab the table as pixmap
            pixmap = table.grab()

            # Save directly
            pixmap.save(str(output_path), "PNG")

        except Exception as e:
            print(f"[WeeklyReportGenerator] Error exporting table: {e}")

    def _export_table_to_png_improved(self, table: QTableWidget, output_path: Path, title: str = ""):
        """
        Export a QTableWidget to PNG using StatsExporter with proper sizing.
        """
        try:
            # Use stats_exporter which now handles large tables properly
            self.stats_exporter.export_to_png(
                table=table,
                table_name=output_path.stem,
                subtitle="",
                file_path=str(output_path)
            )

        except Exception as e:
            print(f"[WeeklyReportGenerator] Error exporting table to PNG: {e}")

    def _generate_last_match_stats(self, team_name: str, output_folder: Path):
        """Generate last match statistics showing team vs opponent with trends."""
        try:
            # Get the last match using the repository method
            last_match = self.db_handler.get_last_match(self.collection_name, team_name)

            if not last_match:
                print(f"[WeeklyReportGenerator] No last match found for {team_name}")
                return

            # Detect if FBCYL format
            is_fbcyl = 'stats' in last_match and 'teams' in last_match.get('stats', {})

            # Get season stats for trends first
            season_team_stats = self.db_handler.get_team_stats(self.collection_name)

            if not season_team_stats:
                print(f"[WeeklyReportGenerator] No season stats available in collection")
                return

            if is_fbcyl:
                # FBCYL format: stats.teams[]
                stats_data = last_match.get('stats', {})
                teams_data = stats_data.get('teams', [])

                if len(teams_data) != 2:
                    print(f"[WeeklyReportGenerator] Invalid FBCYL match data")
                    return

                # Find which team is the selected one
                selected_team_data, selected_idx = get_team_data_by_name(last_match, team_name)

                if selected_team_data is None:
                    print(f"[WeeklyReportGenerator] Team {team_name} not found in last match")
                    return

                # Get opponent data
                opponent_idx = 1 - selected_idx
                opponent_team_data = teams_data[opponent_idx]
                selected_is_home = (selected_idx == 0)

                # For FBCYL, aggregate player stats to get team totals
                selected_players = selected_team_data.get('players', [])
                opponent_players = opponent_team_data.get('players', [])

                # Helper function to aggregate player stats into team stats
                def aggregate_fbcyl_team_stats(players):
                    """Aggregate individual player stats into team totals."""
                    # Initialize aggregation with FBCYL field names
                    fbcyl_totals = {
                        'shotsOfTwoAttempted': 0, 'shotsOfTwoSuccessful': 0,
                        'shotsOfThreeAttempted': 0, 'shotsOfThreeSuccessful': 0,
                        'shotsOfOneAttempted': 0, 'shotsOfOneSuccessful': 0,
                        'offensiveRebound': 0, 'defensiveRebound': 0, 'rebounds': 0,
                        'lost': 0, 'faults': 0,
                        'assists': 0, 'steals': 0, 'block': 0, 'score': 0
                    }

                    for player in players:
                        data = player.get('data', {})
                        for key in fbcyl_totals:
                            fbcyl_totals[key] += data.get(key, 0)

                    # Convert to StatsCalculator compatible format
                    team_stats = {
                        'p2a': fbcyl_totals['shotsOfTwoAttempted'],
                        'p2m': fbcyl_totals['shotsOfTwoSuccessful'],
                        'p3a': fbcyl_totals['shotsOfThreeAttempted'],
                        'p3m': fbcyl_totals['shotsOfThreeSuccessful'],
                        'p1a': fbcyl_totals['shotsOfOneAttempted'],
                        'p1m': fbcyl_totals['shotsOfOneSuccessful'],
                        'ro': fbcyl_totals['offensiveRebound'],
                        'rd': fbcyl_totals['defensiveRebound'],
                        'to': fbcyl_totals['lost'],
                        'faults': fbcyl_totals['faults'],
                        'assist': fbcyl_totals['assists'],
                        'st': fbcyl_totals['steals'],
                        'bs': fbcyl_totals['block'],
                        'pts': fbcyl_totals['score']
                    }

                    return team_stats

                # Aggregate to get team-level stats
                selected_stats = aggregate_fbcyl_team_stats(selected_players)
                opponent_stats = aggregate_fbcyl_team_stats(opponent_players)

                # Calculate derived stats using StatsCalculator
                selected_stats = self.stats_calculator.calculate_single_match_stats(selected_stats, opponent_stats)
                opponent_stats = self.stats_calculator.calculate_single_match_stats(opponent_stats, selected_stats)

                # Get opponent name
                opponent_name = opponent_team_data.get("name", "")

                # Add team names to stats (required for table display)
                selected_stats["team_name"] = team_name
                opponent_stats["team_name"] = opponent_name

                # Extract match date
                match_date = stats_data.get("startDate", "")[:10] if stats_data.get("startDate") else ""

                # Find season stats for both teams
                selected_season = next((t for t in season_team_stats if t["team_name"] == team_name), None)
                opponent_season = next((t for t in season_team_stats if t["team_name"] == opponent_name), None)

                if not selected_season:
                    print(f"[WeeklyReportGenerator] Season stats not found for {team_name}")
                    print(f"[WeeklyReportGenerator] Available teams: {[t['team_name'] for t in season_team_stats]}")
                    return

                if not opponent_season:
                    print(f"[WeeklyReportGenerator] Season stats not found for {opponent_name}")
                    print(f"[WeeklyReportGenerator] Available teams: {[t['team_name'] for t in season_team_stats]}")
                    return

            else:
                # FEB format: HEADER and BOXSCORE
                header = last_match.get("HEADER", {})
                boxscore = last_match.get("BOXSCORE", {})
                teams_data = boxscore.get("TEAM", [])

                if len(teams_data) != 2:
                    print(f"[WeeklyReportGenerator] Invalid boxscore in last match")
                    return

                # Find which team is the selected one
                selected_team_data, selected_idx = get_team_data_by_name(last_match, team_name)

                if selected_team_data is None:
                    print(f"[WeeklyReportGenerator] Team {team_name} not found in last match")
                    return

                # Get opponent data
                opponent_idx = 1 - selected_idx
                opponent_team_data = teams_data[opponent_idx].get("TOTAL", {})
                selected_is_home = (selected_idx == 0)

                # Calculate match stats for both teams
                selected_stats = self.stats_calculator.calculate_single_match_stats(selected_team_data, opponent_team_data)
                opponent_stats = self.stats_calculator.calculate_single_match_stats(opponent_team_data, selected_team_data)

                # Get opponent name
                opponent_name = opponent_team_data.get("name", "")

                # Find season stats for both teams
                selected_season = next((t for t in season_team_stats if t["team_name"] == team_name), None)
                opponent_season = next((t for t in season_team_stats if t["team_name"] == opponent_name), None)

                if not selected_season:
                    print(f"[WeeklyReportGenerator] Season stats not found for {team_name}")
                    print(f"[WeeklyReportGenerator] Available teams: {[t['team_name'] for t in season_team_stats]}")
                    return

                if not opponent_season:
                    print(f"[WeeklyReportGenerator] Season stats not found for {opponent_name}")
                    print(f"[WeeklyReportGenerator] Available teams: {[t['team_name'] for t in season_team_stats]}")
                    return

            # Create table to show both teams with trends - USE ADVANCED STATS
            # This is common for both FBCYL and FEB formats
            from PyQt6.QtWidgets import QTableWidget
            from .stats_table_manager import StatsTableManager
            from .trend_calculator import TrendCalculator
            from .stats_config import ADVANCED_COLUMNS

            table = QTableWidget()

            # Use the same columns as ADVANCED stats window
            table.setColumnCount(len(ADVANCED_COLUMNS))
            table.setHorizontalHeaderLabels(ADVANCED_COLUMNS)
            table.setRowCount(2)
            table.setSortingEnabled(False)

            # Create table manager with trend calculator
            trend_calculator = TrendCalculator()
            table_manager = StatsTableManager(trend_calculator)

            # Populate rows using ADVANCED stats (is_basic=False)
            table_manager.populate_last_match_row(
                table, 0, selected_stats, opponent_stats, selected_season, True, is_basic=False
            )
            table_manager.populate_last_match_row(
                table, 1, opponent_stats, selected_stats, opponent_season, False, is_basic=False
            )

            table.setSortingEnabled(True)
            table.resizeColumnsToContents()

            # Export table
            venue_text = "Local" if selected_is_home else "Visitante"
            output_path = output_folder / f"05_Ultimo_Partido_{self._sanitize_filename(team_name)}.png"
            self._export_table_to_png_improved(table, output_path, f"Último Partido - {team_name} ({venue_text}) - {match_date}")

            table.deleteLater()

        except Exception as e:
            print(f"[WeeklyReportGenerator] Error generating last match stats: {e}")

    def _save_team_shot_charts(self, shots, team_name: str, output_folder: Path):
        """Save team shot charts."""
        try:
            made_count = sum(1 for s in shots if int(s.get('m', 0)) == 1)
            total_count = len(shots)
            accuracy = (made_count / total_count * 100) if total_count > 0 else 0

            # Heatmap
            title = f"{team_name}\n{made_count}/{total_count} ({accuracy:.1f}%)"
            fig_heatmap = self.shot_visualizer.plot_heatmap(
                shots=shots, title=title, figsize=(10, 10), alpha=0.6
            )
            heatmap_path = output_folder / f"{self._sanitize_filename(team_name)}_Mapa_Calor.png"
            fig_heatmap.savefig(str(heatmap_path), dpi=150, bbox_inches='tight')
            plt.close(fig_heatmap)

            # Zones
            processed_shots = convert_shots_for_zone_analysis(shots)
            stats = self.zone_analyzer.analyze_zone_performance(processed_shots)
            fig_zones = self.zone_analyzer.plot_zone_analysis(
                stats=stats,
                title=f"{team_name} - Análisis por Zonas\n{made_count}/{total_count} ({accuracy:.1f}%)",
                figsize=(10, 10)
            )
            zones_path = output_folder / f"{self._sanitize_filename(team_name)}_Zonas.png"
            fig_zones.savefig(str(zones_path), dpi=150, bbox_inches='tight')
            plt.close(fig_zones)

        except Exception as e:
            print(f"[WeeklyReportGenerator] Error saving team charts: {e}")


    def _save_player_shot_charts(self, all_shots, team_name: str, player_id_map, output_folder: Path, is_fbcyl=False):
        """Save player shot charts."""
        try:
            players_shots = {}
            for shot in all_shots:
                if is_fbcyl:
                    player_id = shot.get('player_uuid', '')
                else:
                    player_id = shot.get('player_id', '')

                if player_id:
                    if player_id not in players_shots:
                        players_shots[player_id] = []
                    players_shots[player_id].append(shot)

            for player_id, shots in players_shots.items():
                if len(shots) < 5:
                    continue

                player_name = shots[0].get('player_name', f'Jugador {player_id}')

                if is_fbcyl:
                    player_dorsal = ''  # FBCYL doesn't have dorsal
                    safe_player_name = self._sanitize_filename(player_name)
                    title = f"{player_name}"
                else:
                    player_dorsal = shots[0].get('player_dorsal', '')
                    safe_player_name = self._sanitize_filename(f"{player_dorsal}_{player_name}")
                    title = f"{player_name} (#{player_dorsal})"

                made_count = sum(1 for s in shots if int(s.get('m', 0)) == 1)
                total_count = len(shots)
                accuracy = (made_count / total_count * 100) if total_count > 0 else 0

                player_folder = output_folder / safe_player_name
                player_folder.mkdir(exist_ok=True)

                # Heatmap
                chart_title = f"{title}\n{made_count}/{total_count} ({accuracy:.1f}%)"
                fig_heatmap = self.shot_visualizer.plot_heatmap(
                    shots=shots, title=chart_title, figsize=(10, 10), alpha=0.6
                )
                heatmap_path = player_folder / f"{safe_player_name}_Mapa_Calor.png"
                fig_heatmap.savefig(str(heatmap_path), dpi=150, bbox_inches='tight')
                plt.close(fig_heatmap)

                # Zones
                processed_shots = convert_shots_for_zone_analysis(shots)
                stats = self.zone_analyzer.analyze_zone_performance(processed_shots)
                fig_zones = self.zone_analyzer.plot_zone_analysis(
                    stats=stats,
                    title=f"{title} - Análisis por Zonas\n{made_count}/{total_count} ({accuracy:.1f}%)",
                    figsize=(10, 10)
                )
                zones_path = player_folder / f"{safe_player_name}_Zonas.png"
                fig_zones.savefig(str(zones_path), dpi=150, bbox_inches='tight')
                plt.close(fig_zones)

        except Exception as e:
            print(f"[WeeklyReportGenerator] Error saving player charts: {e}")
