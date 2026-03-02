"""IN/OUT Analysis Window - Player impact and teammate comparison analysis."""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
                              QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
                              QMessageBox, QProgressDialog, QHeaderView, QApplication)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from typing import Dict, Optional, List

from .stats_calculator import StatsCalculator
from .stats_exporter import StatsExporter
from .table_items import NumericTableWidgetItem
from .ui_utils import set_app_icon
from .inout_stats_helper import InOutStatsHelper
from .inout_ui_builder import InOutUIBuilder


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
        
        # Team selector
        team_selector_layout = QHBoxLayout()
        team_label = QLabel("Equipo:")
        team_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        team_selector_layout.addWidget(team_label)
        
        self.team_combo = QComboBox()
        teams_list = [t.get('team_name') or t.get('name') for t in self.team_stats]
        seen = set()
        for name in teams_list:
            if name and name not in seen:
                seen.add(name)
                self.team_combo.addItem(name)
        self.team_combo.currentIndexChanged.connect(self._on_team_changed)
        team_selector_layout.addWidget(self.team_combo)
        team_selector_layout.addStretch()
        layout.addLayout(team_selector_layout)
        
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
        (tab, self.inout_player_combo, self.inout_calc_button,
         self.inout_table, self.inout_info_label, self.inout_export_button) = InOutUIBuilder.create_inout_tab_ui(self)
        self.inout_export_button.clicked.connect(self._export_inout_stats)
        return tab
        
    def _create_invin_tab(self) -> QWidget:
        """Create the IN vs IN comparison tab."""
        (tab, self.invin_player1_combo, self.invin_player2_combo, self.invin_calc_button,
         self.invin_table, self.invin_info_label, self.invin_export_button) = InOutUIBuilder.create_invin_tab_ui(self)
        self.invin_export_button.clicked.connect(self._export_invin_stats)
        return tab
        
    def _create_comparison_tab(self) -> QWidget:
        """Create the teammate comparison tab."""
        (tab, self.main_player_combo, self.teammate_a_combo, self.teammate_b_combo,
         self.comparison_calc_button, self.comparison_table,
         self.comparison_info_label, self.comparison_export_button) = InOutUIBuilder.create_comparison_tab_ui(self)
        self.comparison_export_button.clicked.connect(self._export_comparison_stats)
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
            
    def _on_team_changed(self):
        """Handle team selection change."""
        team_name = self.team_combo.currentText()
        if not team_name:
            return
            
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
            progress = QProgressDialog("Cargando partidos desde base de datos...", None, 0, 0, self)
            progress.setWindowTitle("Calculando IN/OUT")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setCancelButton(None)
            progress.show()
            QApplication.processEvents()
            
            def update_progress(current, total):
                if current == 1 and total > 1:
                    progress.setMaximum(100)
                    progress.setLabelText(f"Analizando partidos... (0/{total})")
                    progress.setValue(0)
                elif total > 1:
                    percent = int(current * 100 / total)
                    progress.setValue(percent)
                    progress.setLabelText(f"Analizando partidos... ({current}/{total})")
                QApplication.processEvents()
                
            inout = self.db_handler.get_player_in_out_stats(
                self.collection_name, player_id, date_filter=None,
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
            progress = QProgressDialog("Cargando partidos...", None, 0, 100, self)
            progress.setWindowTitle("Comparando IN vs IN")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setCancelButton(None)
            progress.show()
            
            # Player 1
            progress.setLabelText(f"Analizando {player1_name}...")
            progress.setValue(10)
            QApplication.processEvents()
            
            def update_progress_p1(current, total):
                if total > 1:
                    percent = 10 + int(current * 40 / total)
                    progress.setValue(percent)
                QApplication.processEvents()
                
            inout1 = self.db_handler.get_player_in_out_stats(
                self.collection_name, player1_id,
                date_filter=None, debug=False, progress_callback=update_progress_p1
            )
            
            # Player 2
            progress.setLabelText(f"Analizando {player2_name}...")
            progress.setValue(50)
            QApplication.processEvents()
            
            def update_progress_p2(current, total):
                if total > 1:
                    percent = 50 + int(current * 40 / total)
                    progress.setValue(percent)
                QApplication.processEvents()
                
            inout2 = self.db_handler.get_player_in_out_stats(
                self.collection_name, player2_id,
                date_filter=None, debug=False, progress_callback=update_progress_p2
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
            progress = QProgressDialog("Calculando estadísticas...", None, 0, 100, self)
            progress.setWindowTitle("Comparando Compañeros")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setCancelButton(None)
            progress.show()
            
            # Stats with teammate A
            progress.setLabelText(f"Analizando con {teammate_a_name}...")
            progress.setValue(10)
            QApplication.processEvents()
            
            def update_progress_a(current, total):
                if total > 1:
                    percent = 10 + int(current * 40 / total)
                    progress.setValue(percent)
                QApplication.processEvents()
                
            stats_with_a = self.db_handler.get_player_individual_stats_with_teammate(
                self.collection_name, main_player_id, teammate_a_id,
                date_filter=None, debug=False, progress_callback=update_progress_a
            )
            
            # Stats with teammate B
            progress.setLabelText(f"Analizando con {teammate_b_name}...")
            progress.setValue(50)
            QApplication.processEvents()
            
            def update_progress_b(current, total):
                if total > 1:
                    percent = 50 + int(current * 40 / total)
                    progress.setValue(percent)
                QApplication.processEvents()
                
            stats_with_b = self.db_handler.get_player_individual_stats_with_teammate(
                self.collection_name, main_player_id, teammate_b_id,
                date_filter=None, debug=False, progress_callback=update_progress_b
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
        
        minutes_a = float(stats_a.get('minutes', 0))
        minutes_b = float(stats_b.get('minutes', 0))
        games_a = int(stats_a.get('games', 0))
        games_b = int(stats_b.get('games', 0))
        possessions_a = full_data_a.get('possessions', 0)
        possessions_b = full_data_b.get('possessions', 0)
        
        # Display fields: individual player stats normalized per 100 possessions
        display_fields = [
            ("Puntos/100", "points", False),
            ("T2/100", "fga_2", False),
            ("T3/100", "fga_3", False),
            ("TL/100", "fta", False),
            ("eFG%", "efg_pct", False),
            ("TS%", "ts_pct", False),
            ("REB-O/100", "orb", False),
            ("REB-D/100", "drb", False),
            ("Asist./100", "ast", False),
            ("Robos/100", "stl", False),
            ("Tapones/100", "blk", False),
            ("Pérdidas/100", "tov", True),  # reverse=True, less is better
            ("Faltas/100", "pf", True)
        ]
        
        # Update headers
        self.comparison_table.setHorizontalHeaderLabels([
            "Estadística", f"Con {teammate_a}", f"Con {teammate_b}", "Δ %"
        ])
        
        # Populate table
        self.comparison_table.setRowCount(len(display_fields))
        
        for row, (label, key, reverse) in enumerate(display_fields):
            # Stat name
            self.comparison_table.setItem(row, 0, QTableWidgetItem(label))
            
            # Value A (normalized per 100 possessions)
            val_a = norm_a.get(key, 0)
            self.comparison_table.setItem(row, 1, NumericTableWidgetItem(val_a, f"{val_a:.2f}"))
            
            # Value B (normalized per 100 possessions)
            val_b = norm_b.get(key, 0)
            self.comparison_table.setItem(row, 2, NumericTableWidgetItem(val_b, f"{val_b:.2f}"))
            
            # Delta %
            if val_b != 0:
                delta_pct = ((val_a - val_b) / abs(val_b)) * 100
            else:
                delta_pct = 0.0
            
            delta_item = NumericTableWidgetItem(delta_pct, f"{delta_pct:.1f}%")
            
            # Color coding (green = A better, red = B better)
            DELTA_THRESHOLD = 0.5
            if abs(delta_pct) > DELTA_THRESHOLD:
                if (delta_pct > 0 and not reverse) or (delta_pct < 0 and reverse):
                    delta_item.setBackground(QColor("#c8e6c9"))  # Green
                else:
                    delta_item.setBackground(QColor("#ffcdd2"))  # Red
            
            self.comparison_table.setItem(row, 3, delta_item)
        
        # Add summary rows
        last_row = len(display_fields)
        self.comparison_table.setRowCount(last_row + 3)
        
        # Minutes row
        self.comparison_table.setItem(last_row, 0, QTableWidgetItem("Min Juntos"))
        self.comparison_table.setItem(last_row, 1, NumericTableWidgetItem(minutes_a, f"{minutes_a:.1f}"))
        self.comparison_table.setItem(last_row, 2, NumericTableWidgetItem(minutes_b, f"{minutes_b:.1f}"))
        diff = minutes_a - minutes_b
        self.comparison_table.setItem(last_row, 3, NumericTableWidgetItem(diff, f"{diff:.1f}"))
        
        # Possessions row
        self.comparison_table.setItem(last_row + 1, 0, QTableWidgetItem("Posesiones"))
        self.comparison_table.setItem(last_row + 1, 1, NumericTableWidgetItem(possessions_a, f"{possessions_a:.1f}"))
        self.comparison_table.setItem(last_row + 1, 2, NumericTableWidgetItem(possessions_b, f"{possessions_b:.1f}"))
        poss_diff = possessions_a - possessions_b
        self.comparison_table.setItem(last_row + 1, 3, NumericTableWidgetItem(poss_diff, f"{poss_diff:.1f}"))
        
        # Games row
        self.comparison_table.setItem(last_row + 2, 0, QTableWidgetItem("Partidos"))
        self.comparison_table.setItem(last_row + 2, 1, NumericTableWidgetItem(games_a, f"{games_a}"))
        self.comparison_table.setItem(last_row + 2, 2, NumericTableWidgetItem(games_b, f"{games_b}"))
        games_diff = games_a - games_b
        self.comparison_table.setItem(last_row + 2, 3, NumericTableWidgetItem(games_diff, f"{games_diff}"))
        
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
        if not self.inout_exporter:
            QMessageBox.warning(self, "Sin datos", "No hay datos para exportar. Ejecuta el cálculo primero.")
            return
        
        player_name = getattr(self, 'inout_current_player_name', 'Jugador')
        table_name = f"InOut_{player_name.replace(' ', '_')}"
        subtitle = f"Análisis IN/OUT - {player_name}"
        
        # Show export menu
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        csv_action = menu.addAction("💾 Exportar a CSV")
        png_action = menu.addAction("🖼️ Exportar a PNG")
        pdf_action = menu.addAction("📄 Exportar a PDF")
        
        action = menu.exec(self.inout_export_button.mapToGlobal(self.inout_export_button.rect().bottomLeft()))
        
        if action == csv_action:
            self.inout_exporter.export_to_csv(self.inout_table, table_name, subtitle)
        elif action == png_action:
            self.inout_exporter.export_to_png(self.inout_table, table_name, subtitle)
        elif action == pdf_action:
            self.inout_exporter.export_to_pdf(self.inout_table, table_name, subtitle)
    
    def _export_invin_stats(self):
        """Export IN vs IN comparison table."""
        if not self.invin_exporter:
            QMessageBox.warning(self, "Sin datos", "No hay datos para exportar. Ejecuta el cálculo primero.")
            return
        
        player1 = getattr(self, 'invin_player1_name', 'Jugador1')
        player2 = getattr(self, 'invin_player2_name', 'Jugador2')
        table_name = f"InVsIn_{player1.replace(' ', '_')}_vs_{player2.replace(' ', '_')}"
        subtitle = f"Comparación IN - {player1} vs {player2}"
        
        # Show export menu
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        csv_action = menu.addAction("💾 Exportar a CSV")
        png_action = menu.addAction("🖼️ Exportar a PNG")
        pdf_action = menu.addAction("📄 Exportar a PDF")
        
        action = menu.exec(self.invin_export_button.mapToGlobal(self.invin_export_button.rect().bottomLeft()))
        
        if action == csv_action:
            self.invin_exporter.export_to_csv(self.invin_table, table_name, subtitle)
        elif action == png_action:
            self.invin_exporter.export_to_png(self.invin_table, table_name, subtitle)
        elif action == pdf_action:
            self.invin_exporter.export_to_pdf(self.invin_table, table_name, subtitle)
    
    def _export_comparison_stats(self):
        """Export teammate comparison table."""
        if not self.comparison_exporter:
            QMessageBox.warning(self, "Sin datos", "No hay datos para exportar. Ejecuta el cálculo primero.")
            return
        
        player = getattr(self, 'comparison_current_player_name', 'Jugador')
        teammate_a = getattr(self, 'comparison_teammate_a_name', 'CompañeroA')
        teammate_b = getattr(self, 'comparison_teammate_b_name', 'CompañeroB')
        table_name = f"Comparacion_{player.replace(' ', '_')}"
        subtitle = f"Comparación - {player} con {teammate_a} vs {teammate_b}"
        
        # Show export menu
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        csv_action = menu.addAction("💾 Exportar a CSV")
        png_action = menu.addAction("🖼️ Exportar a PNG")
        pdf_action = menu.addAction("📄 Exportar a PDF")
        
        action = menu.exec(self.comparison_export_button.mapToGlobal(self.comparison_export_button.rect().bottomLeft()))
        
        if action == csv_action:
            self.comparison_exporter.export_to_csv(self.comparison_table, table_name, subtitle)
        elif action == png_action:
            self.comparison_exporter.export_to_png(self.comparison_table, table_name, subtitle)
        elif action == pdf_action:
            self.comparison_exporter.export_to_pdf(self.comparison_table, table_name, subtitle)