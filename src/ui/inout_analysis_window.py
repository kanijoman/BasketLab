"""IN/OUT Analysis Window - Player impact and teammate comparison analysis."""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
                              QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
                              QMessageBox, QProgressDialog, QHeaderView, QApplication)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from typing import Dict, Optional, List
from datetime import datetime, timedelta

from .stats_calculator import StatsCalculator
from .stats_exporter import StatsExporter
from .table_items import NumericTableWidgetItem
from .ui_utils import set_app_icon
from .inout_stats_helper import InOutStatsHelper
from .inout_ui_builder import InOutUIBuilder
from .export_menu_helper import ExportMenuHelper
from .analysis_progress_helper import AnalysisProgressHelper


class InOutAnalysisWindow(QMainWindow):
    """Window for IN/OUT analysis and teammate comparison."""

    def __init__(self, db_handler, collection_name: str, scope: str, season: str, 
                 group: str, competition: str, team_stats: List[Dict]):
        """
        Initialize IN/OUT analysis window.

        Args:
            db_handler: MongoDBHandler instance
            collection_name: Database collection name
            scope: Scope (FEB/FBCYL)
            season: Season identifier
            group: Group identifier
            competition: Competition name
            team_stats: List of team statistics
        """
        super().__init__()
        
        self.db_handler = db_handler
        self.collection_name = collection_name
        self.scope = scope
        self.season = season
        self.group = group
        self.competition = competition
        self.team_stats = team_stats
        self.is_fbcyl = "FBCYL" in scope
        
        self.stats_calculator = StatsCalculator()
        
        # Initialize exporters for each tab
        self.inout_exporter = None  # Initialized when table has data
        self.invin_exporter = None
        self.comparison_exporter = None
        
        # Store players list for each team
        self.team_players = {}  # team_name -> [(player_name, player_id), ...]
        
        self.setWindowTitle(f"Análisis IN/OUT - {competition} {season}")
        self.setMinimumSize(1000, 700)
        set_app_icon(self)
        
        self._setup_ui()
        self._load_team_players()
        
    def _setup_ui(self):
        """Setup the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Team selector and period filter
        controls_layout = QHBoxLayout()
        
        team_label = QLabel("Equipo:")
        team_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        controls_layout.addWidget(team_label)
        
        self.team_combo = QComboBox()
        teams_list = [t.get('team_name') or t.get('name') for t in self.team_stats]
        seen = set()
        for name in teams_list:
            if name and name not in seen:
                seen.add(name)
                self.team_combo.addItem(name)
        self.team_combo.currentIndexChanged.connect(self._on_team_changed)
        controls_layout.addWidget(self.team_combo)
        
        controls_layout.addSpacing(20)
        
        # Add period selector ComboBox (reusing from TeamStatsWindow)
        period_label = QLabel("Período:")
        period_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        controls_layout.addWidget(period_label)
        
        self.period_combo = QComboBox()
        self.period_combo.addItem("General (toda la temporada)", "general")
        self.period_combo.addItem("Últimos 7 días", "comparative_7")
        self.period_combo.addItem("Últimos 15 días", "comparative_15")
        self.period_combo.addItem("Últimos 30 días", "comparative_30")
        self.period_combo.addItem("Últimos 60 días", "comparative_60")
        self.period_combo.setToolTip("Seleccionar período de análisis IN/OUT")
        controls_layout.addWidget(self.period_combo)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Tab widget for different analyses
        self.tab_widget = QTabWidget()
        
        # Tab 1: Traditional IN/OUT analysis
        self.inout_tab = self._create_inout_tab()
        self.tab_widget.addTab(self.inout_tab, "Análisis IN/OUT")
        
        # Tab 2: IN vs IN comparison (compare 2 players)
        self.invin_tab = self._create_invin_tab()
        self.tab_widget.addTab(self.invin_tab, "IN vs IN")
        
        # Tab 3: Teammate comparison
        self.comparison_tab = self._create_comparison_tab()
        self.tab_widget.addTab(self.comparison_tab, "Comparación con Compañeros")
        
        layout.addWidget(self.tab_widget)
        
    def _create_inout_tab(self) -> QWidget:
        """Create the traditional IN/OUT analysis tab."""
        (tab, self.inout_search, self.inout_player_combo, self.inout_calc_button,
         self.inout_table, self.inout_info_label, self.inout_export_button) = InOutUIBuilder.create_inout_tab_ui(self)
        self.inout_export_button.clicked.connect(self._export_inout_stats)
        self.inout_search.textChanged.connect(
            lambda text: self._filter_players_combo(text, self.inout_player_combo)
        )
        return tab
        
    def _create_invin_tab(self) -> QWidget:
        """Create the IN vs IN comparison tab."""
        (tab, self.invin_search1, self.invin_player1_combo,
         self.invin_search2, self.invin_player2_combo, self.invin_calc_button,
         self.invin_table, self.invin_info_label, self.invin_export_button) = InOutUIBuilder.create_invin_tab_ui(self)
        self.invin_export_button.clicked.connect(self._export_invin_stats)
        self.invin_search1.textChanged.connect(
            lambda text: self._filter_players_combo(text, self.invin_player1_combo)
        )
        self.invin_search2.textChanged.connect(
            lambda text: self._filter_players_combo(text, self.invin_player2_combo)
        )
        return tab
        
    def _create_comparison_tab(self) -> QWidget:
        """Create the teammate comparison tab."""
        (tab, self.main_search, self.main_player_combo,
         self.teammate_a_search, self.teammate_a_combo,
         self.teammate_b_search, self.teammate_b_combo,
         self.comparison_calc_button, self.comparison_table,
         self.comparison_info_label, self.comparison_export_button) = InOutUIBuilder.create_comparison_tab_ui(self)
        self.comparison_export_button.clicked.connect(self._export_comparison_stats)
        self.main_search.textChanged.connect(
            lambda text: self._filter_players_combo(text, self.main_player_combo)
        )
        self.teammate_a_search.textChanged.connect(
            lambda text: self._filter_players_combo(text, self.teammate_a_combo)
        )
        self.teammate_b_search.textChanged.connect(
            lambda text: self._filter_players_combo(text, self.teammate_b_combo)
        )
        return tab
        
    def _load_team_players(self):
        """Load players for each team from the database."""
        if not self.db_handler or not self.collection_name:
            return
            
        try:
            # Get all player stats
            player_stats = self.db_handler.get_player_stats(self.collection_name)
            
            # Group players by team
            for player in player_stats:
                # Both FEB and FBCYL pipelines return: player_id, player_name, team_name
                team_name = player.get('team_name', '')
                player_name = player.get('player_name', '')
                player_id = player.get('player_id', '')
                
                if team_name and player_name and player_id:
                    if team_name not in self.team_players:
                        self.team_players[team_name] = []
                    self.team_players[team_name].append((player_name, player_id))
            
            # Sort players alphabetically within each team
            for team_name in self.team_players:
                self.team_players[team_name].sort(key=lambda x: x[0])
                
            # Initialize first team's players
            if self.team_combo.count() > 0:
                self._on_team_changed()
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al cargar jugadores: {e}")
            
    def _filter_players_combo(self, search_text: str, combo):
        """Filter combo box items by player name substring (case-insensitive)."""
        team_name = self.team_combo.currentText()
        players = self.team_players.get(team_name, [])
        search_lower = search_text.lower().strip()

        combo.blockSignals(True)
        combo.clear()
        for player_name, player_id in players:
            if not search_lower or search_lower in player_name.lower():
                combo.addItem(player_name, player_id)
        combo.blockSignals(False)

    def _on_team_changed(self):
        """Handle team selection change."""
        team_name = self.team_combo.currentText()
        if not team_name:
            return
            
        # Clear all search inputs and player combos
        for search in (self.inout_search, self.invin_search1, self.invin_search2,
                       self.main_search, self.teammate_a_search, self.teammate_b_search):
            search.blockSignals(True)
            search.clear()
            search.blockSignals(False)

        # Clear all player combos
        self.inout_player_combo.clear()
        self.invin_player1_combo.clear()
        self.invin_player2_combo.clear()
        self.main_player_combo.clear()
        self.teammate_a_combo.clear()
        self.teammate_b_combo.clear()
        
        # Load players for this team
        players = self.team_players.get(team_name, [])
        
        for player_name, player_id in players:
            self.inout_player_combo.addItem(player_name, player_id)
            self.invin_player1_combo.addItem(player_name, player_id)
            self.invin_player2_combo.addItem(player_name, player_id)
            self.main_player_combo.addItem(player_name, player_id)
            self.teammate_a_combo.addItem(player_name, player_id)
            self.teammate_b_combo.addItem(player_name, player_id)
    
    def _get_current_date_filter(self):
        """
        Get the current date filter based on selected period.
        
        Returns:
            MongoDB date filter dict or None
        """
        period_type = self.period_combo.currentData()
        
        if not period_type or period_type == "general":
            # No filter - all season
            return None
        
        if period_type.startswith("comparative"):
            # Extract days for temporal filter (últimos N días)
            days = self._extract_days_from_period_type(period_type)
            now = datetime.now()
            period_start = now - timedelta(days=days)
            # For IN/OUT analysis, apply the temporal filter to match the selected period
            return {"$gte": period_start}
        
        return None
    
    @staticmethod
    def _extract_days_from_period_type(period_type: str) -> int:
        """
        Extract number of days from period type string.
        
        Args:
            period_type: Period type (e.g., "comparative_30")
        
        Returns:
            Number of days (defaults to 30 if not parseable)
        """
        days = 30  # default
        if "_" in period_type:
            try:
                days = int(period_type.split("_")[1])
            except (ValueError, IndexError):
                days = 30
        return days
            
    def _on_inout_calculate(self):
        """Calculate traditional IN/OUT stats for selected player."""
        team_name = self.team_combo.currentText()
        player_index = self.inout_player_combo.currentIndex()
        
        if player_index < 0:
            QMessageBox.warning(self, "Selecciona jugador", 
                              "Seleccione un jugador válido para calcular IN/OUT")
            return
            
        player_id = self.inout_player_combo.currentData()
        player_name = self.inout_player_combo.currentText()
        
        if not player_id:
            QMessageBox.warning(self, "Selecciona jugador", "Jugador sin id disponible")
            return
            
        if not self.db_handler or not self.collection_name:
            QMessageBox.warning(self, "Error", 
                              "Se requiere conexión a la base de datos para calcular IN/OUT")
            return
            
        # Fetch IN/OUT stats
        try:
            # Create progress dialog
            progress = AnalysisProgressHelper.create_single_analysis_progress(
                self, "Calculando IN/OUT"
            )
            
            # Create progress callback
            update_progress = AnalysisProgressHelper.create_single_progress_callback(progress)
            
            # Get current date filter based on period selection
            date_filter = self._get_current_date_filter()
                
            inout = self.db_handler.get_player_in_out_stats(
                self.collection_name, player_id, date_filter=date_filter,
                debug=False, progress_callback=update_progress
            )
            progress.close()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al obtener datos IN/OUT: {e}")
            return
            
        if not inout or 'in' not in inout or 'out' not in inout:
            QMessageBox.warning(self, "Sin datos", "No hay datos IN/OUT para este jugador/equipo")
            return
            
        # Display results
        self._display_inout_stats(inout, team_name, player_name)
        
    def _display_inout_stats(self, inout: Dict, team_name: str, player_name: str):
        """Display IN/OUT statistics in the table."""
        stats_in = inout['in']
        stats_out = inout['out']
        
        minutes_in = float(stats_in.get('minutes', 0))
        minutes_out = float(stats_out.get('minutes', 0))
        games_in = int(stats_in.get('games', inout.get('games_analyzed', 1)))
        games_out = int(stats_out.get('games', inout.get('games_analyzed', 1)))
        
        # Calculate advanced metrics using helper
        adv_in = InOutStatsHelper.calculate_advanced_metrics(
            self.stats_calculator, stats_in, team_name
        )
        adv_out = InOutStatsHelper.calculate_advanced_metrics(
            self.stats_calculator, stats_out, team_name
        )
        
        # Get display fields
        display_fields = InOutStatsHelper.get_display_fields()
        
        # Populate table
        InOutStatsHelper.populate_comparison_table(
            self.inout_table, adv_in, adv_out, display_fields
        )
        
        # Add Min/J row
        last_row = len(display_fields)
        self.inout_table.setRowCount(last_row + 1)
        self.inout_table.setItem(last_row, 0, QTableWidgetItem("Min/J"))
        
        min_per_game_in = minutes_in / games_in if games_in > 0 else 0
        min_per_game_out = minutes_out / games_out if games_out > 0 else 0
        
        self.inout_table.setItem(last_row, 1, NumericTableWidgetItem(min_per_game_in, f"{min_per_game_in:.1f}"))
        self.inout_table.setItem(last_row, 2, NumericTableWidgetItem(min_per_game_out, f"{min_per_game_out:.1f}"))
        self.inout_table.setItem(last_row, 3, QTableWidgetItem("-"))
        
        # Update info label
        games_analyzed = inout.get('games_analyzed', 0)
        self.inout_info_label.setText(
            f"Jugador: {player_name} | Partidos analizados: {games_analyzed} | "
            f"Min IN: {minutes_in:.1f} | Min OUT: {minutes_out:.1f}"
        )
        
        # Initialize exporter for this tab
        self.inout_exporter = StatsExporter(self)
        self.inout_current_player_name = player_name
        
    def _on_invin_calculate(self):
        """Calculate and compare IN stats for two players (IN vs IN)."""
        team_name = self.team_combo.currentText()
        
        # Get selected players
        player1_id = self.invin_player1_combo.currentData()
        player1_name = self.invin_player1_combo.currentText()
        player2_id = self.invin_player2_combo.currentData()
        player2_name = self.invin_player2_combo.currentText()
        
        # Validation
        if not player1_id or not player2_id:
            QMessageBox.warning(self, "Selección incompleta", 
                              "Debe seleccionar dos jugadores")
            return
            
        if player1_id == player2_id:
            QMessageBox.warning(self, "Selección inválida", 
                              "Debe seleccionar dos jugadores diferentes")
            return
            
        if not self.db_handler or not self.collection_name:
            QMessageBox.warning(self, "Error", 
                              "Se requiere conexión a la base de datos")
            return
            
        # Calculate IN stats for both players
        try:
            # Create progress dialog
            progress = AnalysisProgressHelper.create_dual_analysis_progress(
                self, "Comparando IN vs IN", player1_name, player2_name
            )
            
            # Get current date filter based on period selection
            date_filter = self._get_current_date_filter()
            
            # Player 1
            AnalysisProgressHelper.update_progress_for_entity(progress, player1_name, 10)
            update_progress_p1 = AnalysisProgressHelper.create_progress_callback(progress, 10, 40)
                
            inout1 = self.db_handler.get_player_in_out_stats(
                self.collection_name, player1_id,
                date_filter=date_filter, debug=False, progress_callback=update_progress_p1
            )
            
            # Player 2
            AnalysisProgressHelper.update_progress_for_entity(progress, player2_name, 50)
            update_progress_p2 = AnalysisProgressHelper.create_progress_callback(progress, 50, 40)
                
            inout2 = self.db_handler.get_player_in_out_stats(
                self.collection_name, player2_id,
                date_filter=date_filter, debug=False, progress_callback=update_progress_p2
            )
            
            progress.setValue(100)
            progress.close()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al calcular estadísticas: {e}")
            return
            
        if not inout1 or 'in' not in inout1:
            QMessageBox.warning(self, "Sin datos", 
                              f"No hay datos IN para {player1_name}")
            return
            
        if not inout2 or 'in' not in inout2:
            QMessageBox.warning(self, "Sin datos", 
                              f"No hay datos IN para {player2_name}")
            return
            
        # Display comparison
        self._display_invin_stats(
            inout1['in'], inout2['in'], inout1, inout2,
            team_name, player1_name, player2_name
        )
        
    def _display_invin_stats(self, stats1: Dict, stats2: Dict, 
                            inout1: Dict, inout2: Dict,
                            team_name: str, player1: str, player2: str):
        """Display IN vs IN comparison statistics."""
        minutes1 = float(stats1.get('minutes', 0))
        minutes2 = float(stats2.get('minutes', 0))
        games1 = int(stats1.get('games', inout1.get('games_analyzed', 1)))
        games2 = int(stats2.get('games', inout2.get('games_analyzed', 1)))
        
        # Calculate advanced metrics using helper
        adv1 = InOutStatsHelper.calculate_advanced_metrics(
            self.stats_calculator, stats1, team_name
        )
        adv2 = InOutStatsHelper.calculate_advanced_metrics(
            self.stats_calculator, stats2, team_name
        )
        
        # Get display fields
        display_fields = InOutStatsHelper.get_display_fields()
        
        # Update headers with player names
        self.invin_table.setHorizontalHeaderLabels([
            "Estadística", f"{player1} IN", f"{player2} IN", "Δ %"
        ])
        
        # Populate table
        InOutStatsHelper.populate_comparison_table(
            self.invin_table, adv1, adv2, display_fields
        )
        
        # Add minutes/game row
        last_row = len(display_fields)
        self.invin_table.setRowCount(last_row + 1)
        self.invin_table.setItem(last_row, 0, QTableWidgetItem("Min/J"))
        
        min_per_game1 = minutes1 / games1 if games1 > 0 else 0
        min_per_game2 = minutes2 / games2 if games2 > 0 else 0
        
        self.invin_table.setItem(last_row, 1, NumericTableWidgetItem(min_per_game1, f"{min_per_game1:.1f}"))
        self.invin_table.setItem(last_row, 2, NumericTableWidgetItem(min_per_game2, f"{min_per_game2:.1f}"))
        diff = min_per_game1 - min_per_game2
        self.invin_table.setItem(last_row, 3, NumericTableWidgetItem(diff, f"{diff:.1f}"))
        
        # Update info label
        games1_total = inout1.get('games_analyzed', 0)
        games2_total = inout2.get('games_analyzed', 0)
        self.invin_info_label.setText(
            f"Partidos analizados: {player1}={games1_total}, {player2}={games2_total}"
        )
        
        # Initialize exporter for this tab
        self.invin_exporter = StatsExporter(self)
        self.invin_player1_name = player1
        self.invin_player2_name = player2
        
    def _on_comparison_calculate(self):
        """Calculate and compare stats with two teammates."""
        team_name = self.team_combo.currentText()
        
        # Get selected players
        main_player_id = self.main_player_combo.currentData()
        main_player_name = self.main_player_combo.currentText()
        teammate_a_id = self.teammate_a_combo.currentData()
        teammate_a_name = self.teammate_a_combo.currentText()
        teammate_b_id = self.teammate_b_combo.currentData()
        teammate_b_name = self.teammate_b_combo.currentText()
        
        # Validation
        if not main_player_id or not teammate_a_id or not teammate_b_id:
            QMessageBox.warning(self, "Selección incompleta", 
                              "Debe seleccionar un jugador principal y dos compañeros")
            return
            
        if main_player_id == teammate_a_id or main_player_id == teammate_b_id or teammate_a_id == teammate_b_id:
            QMessageBox.warning(self, "Selección inválida", 
                              "Debe seleccionar tres jugadores diferentes")
            return
            
        if not self.db_handler or not self.collection_name:
            QMessageBox.warning(self, "Error", 
                              "Se requiere conexión a la base de datos")
            return
            
        # Calculate stats with each teammate
        try:
            # Create progress dialog
            progress = AnalysisProgressHelper.create_dual_analysis_progress(
                self, "Comparando Compañeros", teammate_a_name, teammate_b_name
            )
            
            # Get current date filter based on period selection
            date_filter = self._get_current_date_filter()
            
            # Stats with teammate A
            AnalysisProgressHelper.update_progress_for_entity(progress, teammate_a_name, 10)
            update_progress_a = AnalysisProgressHelper.create_progress_callback(progress, 10, 40)
                
            stats_with_a = self.db_handler.get_player_individual_stats_with_teammate(
                self.collection_name, main_player_id, teammate_a_id,
                date_filter=date_filter, debug=False, progress_callback=update_progress_a
            )
            
            # Stats with teammate B
            AnalysisProgressHelper.update_progress_for_entity(progress, teammate_b_name, 50)
            update_progress_b = AnalysisProgressHelper.create_progress_callback(progress, 50, 40)
                
            stats_with_b = self.db_handler.get_player_individual_stats_with_teammate(
                self.collection_name, main_player_id, teammate_b_id,
                date_filter=date_filter, debug=False, progress_callback=update_progress_b
            )
            
            progress.setValue(100)
            progress.close()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al calcular estadísticas: {e}")
            return
            
        if not stats_with_a or 'raw_stats' not in stats_with_a:
            QMessageBox.warning(self, "Sin datos", 
                              f"No hay datos when {main_player_name} juega con {teammate_a_name}")
            return
            
        if not stats_with_b or 'raw_stats' not in stats_with_b:
            QMessageBox.warning(self, "Sin datos", 
                              f"No hay datos cuando {main_player_name} juega con {teammate_b_name}")
            return
            
        # Display comparison
        self._display_comparison_stats(
            stats_with_a['raw_stats'], stats_with_b['raw_stats'],
            stats_with_a, stats_with_b,
            main_player_name, teammate_a_name, teammate_b_name
        )
        
    def _display_comparison_stats(self, stats_a: Dict, stats_b: Dict,
                                  full_data_a: Dict, full_data_b: Dict,
                                  main_player: str, teammate_a: str, teammate_b: str):
        """Display teammate comparison statistics for main player (normalized per 100 possessions)."""
        # Extract normalized stats (per 100 possessions)
        norm_a = full_data_a.get('per_100_poss', {})
        norm_b = full_data_b.get('per_100_poss', {})
        
        # Extract metadata
        minutes_a = float(stats_a.get('minutes', 0))
        minutes_b = float(stats_b.get('minutes', 0))
        games_a = int(stats_a.get('games', 0))
        games_b = int(stats_b.get('games', 0))
        possessions_a = full_data_a.get('possessions', 0)
        possessions_b = full_data_b.get('possessions', 0)
        
        # Populate table using helper
        InOutStatsHelper.populate_teammate_comparison_table(
            self.comparison_table, norm_a, norm_b, teammate_a, teammate_b
        )
        
        # Add summary rows using helper
        display_fields = InOutStatsHelper.get_teammate_comparison_fields()
        InOutStatsHelper.add_summary_rows_to_comparison(
            self.comparison_table,
            minutes_a, minutes_b,
            possessions_a, possessions_b,
            games_a, games_b,
            len(display_fields)
        )
        
        # Update info label
        games_a_total = full_data_a.get('games_analyzed', 0)
        games_b_total = full_data_b.get('games_analyzed', 0)
        self.comparison_info_label.setText(
            f"{main_player}: Con {teammate_a}={games_a_total} partidos ({possessions_a:.0f} pos.), "
            f"Con {teammate_b}={games_b_total} partidos ({possessions_b:.0f} pos.)"
        )
        
        # Initialize exporter for this tab
        self.comparison_exporter = StatsExporter(self)
        self.comparison_current_player_name = main_player
        self.comparison_teammate_a_name = teammate_a
        self.comparison_teammate_b_name = teammate_b
    
    def _export_inout_stats(self):
        """Export IN/OUT statistics table."""
        player_name = getattr(self, 'inout_current_player_name', 'Jugador')
        table_name = f"InOut_{player_name.replace(' ', '_')}"
        subtitle = f"Análisis IN/OUT - {player_name}"
        
        ExportMenuHelper.show_export_menu(
            self, self.inout_export_button, self.inout_exporter,
            self.inout_table, table_name, subtitle
        )
    
    def _export_invin_stats(self):
        """Export IN vs IN comparison table."""
        player1 = getattr(self, 'invin_player1_name', 'Jugador1')
        player2 = getattr(self, 'invin_player2_name', 'Jugador2')
        table_name = f"InVsIn_{player1.replace(' ', '_')}_vs_{player2.replace(' ', '_')}"
        subtitle = f"Comparación IN - {player1} vs {player2}"
        
        ExportMenuHelper.show_export_menu(
            self, self.invin_export_button, self.invin_exporter,
            self.invin_table, table_name, subtitle
        )
    
    def _export_comparison_stats(self):
        """Export teammate comparison table."""
        player = getattr(self, 'comparison_current_player_name', 'Jugador')
        teammate_a = getattr(self, 'comparison_teammate_a_name', 'CompañeroA')
        teammate_b = getattr(self, 'comparison_teammate_b_name', 'CompañeroB')
        table_name = f"Comparacion_{player.replace(' ', '_')}"
        subtitle = f"Comparación - {player} con {teammate_a} vs {teammate_b}"
        
        ExportMenuHelper.show_export_menu(
            self, self.comparison_export_button, self.comparison_exporter,
            self.comparison_table, table_name, subtitle
        )