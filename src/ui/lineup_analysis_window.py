"""Lineup Analysis Window - Analyze best and worst lineups/combinations."""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
                              QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                              QMessageBox, QProgressDialog, QHeaderView, QSplitter,
                              QProgressBar, QMenu)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QAction
from typing import Dict, Optional, List
from datetime import datetime, timedelta

from .stats_exporter import StatsExporter
from .table_items import NumericTableWidgetItem
from .ui_utils import set_app_icon
from .stats_table_manager import StatsTableManager

# Statistics where LOWER values are BETTER (reverse sorting)
REVERSE_STATS = {'drtg', 'tov_pct'}


class LineupAnalysisWorker(QThread):
    """Worker thread for lineup analysis calculations."""
    
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, int)
    
    def __init__(self, db_handler, collection_name, team_id, team_name,
                 combination_size, date_filter, is_fbcyl):
        super().__init__()
        self.db_handler = db_handler
        self.collection_name = collection_name
        self.team_id = team_id
        self.team_name = team_name
        self.combination_size = combination_size
        self.date_filter = date_filter
        self.is_fbcyl = is_fbcyl
    
    def run(self):
        """Execute lineup analysis in background thread."""
        try:
            lineup_data = self.db_handler.get_lineup_analysis(
                self.collection_name,
                self.team_id,
                self.team_name,
                combination_size=self.combination_size,
                date_filter=self.date_filter,
                is_fbcyl=self.is_fbcyl,
                progress_callback=self.progress.emit
            )
            self.finished.emit(lineup_data)
        except Exception as e:
            self.error.emit(str(e))


class LineupAnalysisWindow(QMainWindow):
    """Window for analyzing lineup combinations (quintets, quartets, trios)."""

    def __init__(self, db_handler, collection_name: str, scope: str, season: str,
                 group: str, competition: str, team_stats: List[Dict]):
        """
        Initialize lineup analysis window.

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
        
        # Worker thread for calculations
        self.worker = None
        self.progress_dialog = None
        
        # Current lineup data
        self.current_lineup_data = []
        self.current_stat_key = 'net_rating'
        
        self.setWindowTitle(f"Análisis de Quintetos - {competition} {season}")
        self.setMinimumSize(1200, 800)
        set_app_icon(self)
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Controls section
        controls_layout = QHBoxLayout()
        
        # Team selector
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
        controls_layout.addWidget(self.team_combo)
        
        controls_layout.addSpacing(20)
        
        # Combination size selector
        size_label = QLabel("Tamaño:")
        size_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        controls_layout.addWidget(size_label)
        
        self.size_combo = QComboBox()
        self.size_combo.addItem("Quintetos (5 jugadoras)", 5)
        self.size_combo.addItem("Cuartetos (4 jugadoras)", 4)
        self.size_combo.addItem("Tríos (3 jugadoras)", 3)
        controls_layout.addWidget(self.size_combo)
        
        controls_layout.addSpacing(20)
        
        # Period selector
        period_label = QLabel("Período:")
        period_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        controls_layout.addWidget(period_label)
        
        self.period_combo = QComboBox()
        self.period_combo.addItem("General (toda la temporada)", "general")
        self.period_combo.addItem("Últimos 7 días", "comparative_7")
        self.period_combo.addItem("Últimos 15 días", "comparative_15")
        self.period_combo.addItem("Últimos 30 días", "comparative_30")
        self.period_combo.addItem("Últimos 60 días", "comparative_60")
        controls_layout.addWidget(self.period_combo)
        
        controls_layout.addSpacing(20)
        
        # Statistic selector
        stat_label = QLabel("Estadística:")
        stat_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        controls_layout.addWidget(stat_label)
        
        self.stat_combo = QComboBox()
        # Basic stats
        self.stat_combo.addItem("--- Básicas ---", None)
        self.stat_combo.addItem("Net Rating (ORtg - DRtg)", "net_rating")
        self.stat_combo.addItem("+/- (Diferencial de Puntos)", "plus_minus")
        self.stat_combo.addItem("Puntos a Favor", "points_for")
        self.stat_combo.addItem("Asistencias", "ast")
        self.stat_combo.addItem("Rebotes Totales", "trb")
        # Advanced stats
        self.stat_combo.addItem("--- Avanzadas ---", None)
        self.stat_combo.addItem("Offensive Rating (ORtg)", "ortg")
        self.stat_combo.addItem("Defensive Rating (DRtg)", "drtg")
        self.stat_combo.addItem("eFG% (Effective FG%)", "efg_pct")
        self.stat_combo.addItem("TOV% (Turnover %)", "tov_pct")
        self.stat_combo.addItem("ORB% (Off. Rebound %)", "orb_pct")
        self.stat_combo.addItem("FTr (Free Throw Rate)", "ftr")
        self.stat_combo.currentIndexChanged.connect(self._on_stat_changed)
        controls_layout.addWidget(self.stat_combo)
        
        controls_layout.addSpacing(20)
        
        # Calculate button
        self.calc_button = QPushButton("Calcular Análisis")
        self.calc_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.calc_button.clicked.connect(self._calculate_lineups)
        controls_layout.addWidget(self.calc_button)
        
        # Export button with menu
        self.export_button = QPushButton("📤 Exportar")
        self.export_button.setToolTip("Exportar tablas en diferentes formatos")
        self.export_button.setEnabled(False)  # Disabled until data is loaded
        
        export_menu = QMenu(self)
        
        csv_action = QAction("📊 Exportar como CSV", self)
        csv_action.triggered.connect(self._export_csv)
        csv_action.setToolTip("Exportar a formato CSV (separado por punto y coma)")
        export_menu.addAction(csv_action)
        
        png_action = QAction("🖼️ Exportar como PNG", self)
        png_action.triggered.connect(self._export_png)
        png_action.setToolTip("Exportar como imagen PNG")
        export_menu.addAction(png_action)
        
        pdf_action = QAction("📄 Exportar como PDF", self)
        pdf_action.triggered.connect(self._export_pdf)
        pdf_action.setToolTip("Exportar a documento PDF")
        export_menu.addAction(pdf_action)
        
        self.export_button.setMenu(export_menu)
        controls_layout.addWidget(self.export_button)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Main content with splitter (lineups table + frequency table)
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Top section: Lineups table
        lineups_widget = QWidget()
        lineups_layout = QVBoxLayout(lineups_widget)
        lineups_layout.setContentsMargins(0, 0, 0, 0)
        
        lineups_header = QLabel("Mejores y Peores Quintetos")
        lineups_header.setStyleSheet("font-weight: bold; font-size: 12pt;")
        lineups_layout.addWidget(lineups_header)
        
        self.lineups_table = QTableWidget()
        self.lineups_table.setColumnCount(7)
        self.lineups_table.setHorizontalHeaderLabels([
            "Jugadoras", "Minutos", "Partidos", "Min/Partido", "Segmentos",
            "Estadística", "Diferencial"
        ])
        self.lineups_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 7):
            self.lineups_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        
        # Set tooltips for column headers
        self.lineups_table.horizontalHeaderItem(0).setToolTip("Nombres de las jugadoras del quinteto")
        self.lineups_table.horizontalHeaderItem(1).setToolTip("Minutos totales jugados juntas (suma de todos los partidos)")
        self.lineups_table.horizontalHeaderItem(2).setToolTip("Número de partidos donde apareció este quinteto")
        self.lineups_table.horizontalHeaderItem(3).setToolTip("Minutos promedio por partido")
        self.lineups_table.horizontalHeaderItem(4).setToolTip("Número de segmentos (veces que entraron juntas en pista)")
        self.lineups_table.horizontalHeaderItem(5).setToolTip("Valor de la estadística seleccionada")
        self.lineups_table.horizontalHeaderItem(6).setToolTip("Diferencial contra el mejor/peor quinteto según el grupo")
        
        self.lineups_table.setAlternatingRowColors(True)
        self.lineups_table.setSortingEnabled(True)
        lineups_layout.addWidget(self.lineups_table)
        
        splitter.addWidget(lineups_widget)
        
        # Bottom section: Player frequency table
        frequency_widget = QWidget()
        frequency_layout = QVBoxLayout(frequency_widget)
        frequency_layout.setContentsMargins(0, 0, 0, 0)
        
        frequency_header = QLabel("Frecuencia de Aparición por Jugadora")
        frequency_header.setStyleSheet("font-weight: bold; font-size: 12pt;")
        frequency_layout.addWidget(frequency_header)
        
        self.frequency_table = QTableWidget()
        self.frequency_table.setColumnCount(5)
        self.frequency_table.setHorizontalHeaderLabels([
            "Jugadora", "En Mejores", "Barra Mejores",
            "En Peores", "Barra Peores"
        ])
        self.frequency_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for i in range(1, 5):
            self.frequency_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        self.frequency_table.setAlternatingRowColors(True)
        self.frequency_table.setSortingEnabled(True)
        frequency_layout.addWidget(self.frequency_table)
        
        splitter.addWidget(frequency_widget)
        
        # Set initial splitter sizes (60% lineups, 40% frequency)
        splitter.setSizes([600, 400])
        layout.addWidget(splitter)
    
    def _export_csv(self):
        """Export both lineups and frequency tables to CSV."""
        if not hasattr(self, 'lineup_exporter'):
            return
        
        team_name = self.team_combo.currentText()
        stat_name = self.stat_combo.currentText()
        table_name = f"analisis_quintetos_{team_name}_{stat_name}".replace(" ", "_")
        subtitle = f"Equipo: {team_name} | Estadística: {stat_name}"
        
        tables_with_titles = [
            (f"Mejores y Peores Quintetos - {stat_name}", self.lineups_table),
            (f"Frecuencia de Aparición por Jugadora - {stat_name}", self.frequency_table)
        ]
        self.lineup_exporter.export_multiple_to_csv(tables_with_titles, table_name, subtitle)
    
    def _export_png(self):
        """Export both lineups and frequency tables to PNG."""
        if not hasattr(self, 'lineup_exporter'):
            return
        
        team_name = self.team_combo.currentText()
        stat_name = self.stat_combo.currentText()
        table_name = f"analisis_quintetos_{team_name}_{stat_name}".replace(" ", "_")
        subtitle = f"Equipo: {team_name} | Estadística: {stat_name}"
        
        tables_with_titles = [
            (f"Mejores y Peores Quintetos - {stat_name}", self.lineups_table),
            (f"Frecuencia de Aparición por Jugadora - {stat_name}", self.frequency_table)
        ]
        self.lineup_exporter.export_multiple_to_png(tables_with_titles, table_name, subtitle)
    
    def _export_pdf(self):
        """Export both lineups and frequency tables to PDF."""
        if not hasattr(self, 'lineup_exporter'):
            return
        
        team_name = self.team_combo.currentText()
        stat_name = self.stat_combo.currentText()
        table_name = f"analisis_quintetos_{team_name}_{stat_name}".replace(" ", "_")
        window_title = self.windowTitle()
        subtitle = f"Equipo: {team_name} | Estadística: {stat_name}"
        
        tables_with_titles = [
            (f"Mejores y Peores Quintetos - {stat_name}", self.lineups_table),
            (f"Frecuencia de Aparición por Jugadora - {stat_name}", self.frequency_table)
        ]
        self.lineup_exporter.export_multiple_to_pdf(tables_with_titles, table_name, window_title, subtitle)
    
    def _setup_export_menu(self):
        """Setup export menu actions."""
        # Export menu is now created in setup_ui
        pass
    
    def _on_stat_changed(self):
        """Handle statistic selection change."""
        current_data = self.stat_combo.currentData()
        if current_data is None:
            # This is a separator, don't allow selection
            # Find next valid item
            for i in range(self.stat_combo.currentIndex() + 1, self.stat_combo.count()):
                if self.stat_combo.itemData(i) is not None:
                    self.stat_combo.setCurrentIndex(i)
                    break
    
    def _calculate_lineups(self):
        """Start lineup calculation in background thread."""
        team_name = self.team_combo.currentText()
        if not team_name:
            QMessageBox.warning(self, "Error", "Seleccione un equipo")
            return
        
        # Get team ID (comes from aggregation pipeline as _id)
        team_id = None
        for team in self.team_stats:
            if (team.get('team_name') == team_name or team.get('name') == team_name):
                team_id = team.get('_id')
                break
        
        if not team_id:
            QMessageBox.warning(self, "Error", "No se pudo encontrar el ID del equipo")
            return
        
        # Get parameters
        combination_size = self.size_combo.currentData()
        self.current_stat_key = self.stat_combo.currentData()
        
        if self.current_stat_key is None:
            QMessageBox.warning(self, "Error", "Seleccione una estadística válida")
            return
        
        # Get date filter
        period = self.period_combo.currentData()
        date_filter = None
        
        if period != "general":
            days = int(period.split('_')[1])
            cutoff_date = datetime.now() - timedelta(days=days)
            date_filter = {"$gte": cutoff_date.strftime("%Y-%m-%d")}
        
        # Show progress dialog
        self.progress_dialog = QProgressDialog(
            "Analizando quintetos...",
            "Cancelar",
            0, 100,
            self
        )
        self.progress_dialog.setWindowTitle("Calculando")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.canceled.connect(self._cancel_calculation)
        
        # Start worker thread
        self.worker = LineupAnalysisWorker(
            self.db_handler,
            self.collection_name,
            team_id,
            team_name,
            combination_size,
            date_filter,
            self.is_fbcyl
        )
        self.worker.finished.connect(self._on_calculation_finished)
        self.worker.error.connect(self._on_calculation_error)
        self.worker.progress.connect(self._on_calculation_progress)
        self.worker.start()
        
        # Disable calculate button
        self.calc_button.setEnabled(False)
    
    def _cancel_calculation(self):
        """Cancel ongoing calculation."""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        self.calc_button.setEnabled(True)
    
    def _on_calculation_progress(self, current, total):
        """Update progress dialog."""
        if self.progress_dialog:
            self.progress_dialog.setMaximum(total)
            self.progress_dialog.setValue(current)
            self.progress_dialog.setLabelText(f"Procesando partido {current} de {total}...")
    
    def _on_calculation_finished(self, lineup_data: List[Dict]):
        """Handle calculation completion."""
        if self.progress_dialog:
            self.progress_dialog.close()
        
        self.calc_button.setEnabled(True)
        self.current_lineup_data = lineup_data
        
        if not lineup_data:
            QMessageBox.information(
                self,
                "Sin datos",
                "No se encontraron quintetos válidos para el período seleccionado.\n"
                "Los quintetos deben aparecer en al menos 5 partidos y tener 15+ minutos totales juntas."
            )
            return
        
        self._populate_tables()
    
    def _on_calculation_error(self, error_msg: str):
        """Handle calculation error."""
        if self.progress_dialog:
            self.progress_dialog.close()
        
        self.calc_button.setEnabled(True)
        QMessageBox.critical(
            self,
            "Error",
            f"Error al calcular quintetos:\n{error_msg}"
        )
    
    def _populate_tables(self):
        """Populate lineups and frequency tables with calculated data."""
        if not self.current_lineup_data:
            return
        
        # Determine sort direction based on statistic type
        # For DRtg and TOV%, lower is better, so reverse=False (ascending)
        # For all others, higher is better, so reverse=True (descending)
        is_reverse_stat = self.current_stat_key in REVERSE_STATS
        sort_reverse = not is_reverse_stat  # If lower is better, sort ascending (reverse=False)
        
        # Sort by selected statistic
        sorted_data = sorted(
            self.current_lineup_data,
            key=lambda x: x.get(self.current_stat_key, 0),
            reverse=sort_reverse
        )
        
        # Get top 5 and bottom 5
        top_5 = sorted_data[:5]
        bottom_5 = sorted_data[-5:] if len(sorted_data) > 5 else []
        
        # Populate lineups table
        self._populate_lineups_table(top_5, bottom_5)
        
        # Calculate and populate frequency table
        self._populate_frequency_table(top_5, bottom_5)
        
        # Setup exporters with correct API
        self.lineup_exporter = StatsExporter(self)
        self.frequency_exporter = StatsExporter(self)
        
        # Enable export button now that data is loaded
        self.export_button.setEnabled(True)
    
    def _populate_lineups_table(self, top_5: List[Dict], bottom_5: List[Dict]):
        """Populate lineups table with top and bottom lineups."""
        self.lineups_table.setSortingEnabled(False)
        self.lineups_table.setRowCount(0)
        
        # Get reference values for differentials
        best_value = top_5[0].get(self.current_stat_key, 0) if top_5 else 0
        worst_value = bottom_5[-1].get(self.current_stat_key, 0) if bottom_5 else 0
        
        # Add top 5 (compare against best)
        for lineup in top_5:
            self._add_lineup_row(lineup, is_top=True, reference_value=best_value)
        
        # Add separator if we have both top and bottom
        if top_5 and bottom_5:
            row = self.lineups_table.rowCount()
            self.lineups_table.insertRow(row)
            separator = QTableWidgetItem("─" * 50)
            separator.setBackground(QColor("#555555"))
            separator.setForeground(QColor("#FFFFFF"))
            self.lineups_table.setItem(row, 0, separator)
            for col in range(1, 7):
                item = QTableWidgetItem("")
                item.setBackground(QColor("#555555"))
                self.lineups_table.setItem(row, col, item)
        
        # Add bottom 5 (compare against worst)
        for lineup in bottom_5:
            self._add_lineup_row(lineup, is_top=False, reference_value=worst_value)
        
        self.lineups_table.setSortingEnabled(True)
    
    def _add_lineup_row(self, lineup: Dict, is_top: bool, reference_value: float):
        """Add a single lineup row to the table."""
        row = self.lineups_table.rowCount()
        self.lineups_table.insertRow(row)
        
        # Player names (joined with " | ")
        player_names = " | ".join(lineup.get('player_names', []))
        self.lineups_table.setItem(row, 0, QTableWidgetItem(player_names))
        
        # Minutes (total)
        minutes = lineup.get('minutes', 0)
        self.lineups_table.setItem(row, 1, NumericTableWidgetItem(minutes, f"{minutes:.1f}"))
        
        # Games played
        games = lineup.get('games_played', 0)
        self.lineups_table.setItem(row, 2, NumericTableWidgetItem(games, str(games)))
        
        # Average minutes per game
        avg_min = lineup.get('avg_minutes_per_game', 0)
        self.lineups_table.setItem(row, 3, NumericTableWidgetItem(avg_min, f"{avg_min:.1f}"))
        
        # Segments count
        segments = lineup.get('segments_count', 0)
        self.lineups_table.setItem(row, 4, NumericTableWidgetItem(segments, str(segments)))
        
        # Selected statistic
        stat_value = lineup.get(self.current_stat_key, 0)
        self.lineups_table.setItem(row, 5, NumericTableWidgetItem(stat_value, f"{stat_value:.1f}"))
        
        # Differential against reference (best for top group, worst for bottom group)
        differential = stat_value - reference_value
        self.lineups_table.setItem(row, 6, NumericTableWidgetItem(differential, f"{differential:+.1f}"))
        
        # Color code based on whether it's top or bottom
        # For reverse stats (DRtg, TOV%), invert colors (low values are good)
        is_reverse_stat = self.current_stat_key in REVERSE_STATS
        
        if is_reverse_stat:
            # For DRtg/TOV%: top 5 have LOWEST values (best) → green
            #                bottom 5 have HIGHEST values (worst) → red
            if is_top:
                color = QColor("#d4edda")  # Light green (low values are good)
            else:
                color = QColor("#f8d7da")  # Light red (high values are bad)
        else:
            # For normal stats: top 5 have HIGHEST values (best) → green
            #                   bottom 5 have LOWEST values (worst) → red
            if is_top:
                color = QColor("#d4edda")  # Light green
            else:
                color = QColor("#f8d7da")  # Light red
        
        for col in range(self.lineups_table.columnCount()):
            item = self.lineups_table.item(row, col)
            if item:
                item.setBackground(color)
    
    def _populate_frequency_table(self, top_5: List[Dict], bottom_5: List[Dict]):
        """Populate frequency table showing player appearances."""
        # Count appearances for each player
        player_counts = {}  # player_name -> {'best': count, 'worst': count}
        
        for lineup in top_5:
            for player_name in lineup.get('player_names', []):
                if player_name not in player_counts:
                    player_counts[player_name] = {'best': 0, 'worst': 0}
                player_counts[player_name]['best'] += 1
        
        for lineup in bottom_5:
            for player_name in lineup.get('player_names', []):
                if player_name not in player_counts:
                    player_counts[player_name] = {'best': 0, 'worst': 0}
                player_counts[player_name]['worst'] += 1
        
        # Sort by best count (descending), then by worst count (ascending)
        sorted_players = sorted(
            player_counts.items(),
            key=lambda x: (-x[1]['best'], x[1]['worst'])
        )
        
        # Populate table
        self.frequency_table.setSortingEnabled(False)
        self.frequency_table.setRowCount(len(sorted_players))
        
        max_best = max((counts['best'] for _, counts in sorted_players), default=1)
        max_worst = max((counts['worst'] for _, counts in sorted_players), default=1)
        
        for row, (player_name, counts) in enumerate(sorted_players):
            # Player name
            self.frequency_table.setItem(row, 0, QTableWidgetItem(player_name))
            
            # Best count (number + text)
            best_count = counts['best']
            best_item = QTableWidgetItem(f"{best_count} de {len(top_5)}")
            self.frequency_table.setItem(row, 1, best_item)
            
            # Best progress bar
            best_bar = QProgressBar()
            best_bar.setMinimum(0)
            best_bar.setMaximum(max_best)
            best_bar.setValue(best_count)
            best_bar.setFormat(f"{best_count}")
            # Gradient green
            intensity = int((best_count / max_best) * 100) if max_best > 0 else 0
            green_val = 100 + int(155 * (intensity / 100))
            best_bar.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid #aaa;
                    border-radius: 3px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background-color: rgb(0, {green_val}, 0);
                }}
            """)
            self.frequency_table.setCellWidget(row, 2, best_bar)
            
            # Worst count (number + text)
            worst_count = counts['worst']
            worst_item = QTableWidgetItem(f"{worst_count} de {len(bottom_5)}")
            self.frequency_table.setItem(row, 3, worst_item)
            
            # Worst progress bar
            worst_bar = QProgressBar()
            worst_bar.setMinimum(0)
            worst_bar.setMaximum(max_worst)
            worst_bar.setValue(worst_count)
            worst_bar.setFormat(f"{worst_count}")
            # Gradient red-orange
            intensity = int((worst_count / max_worst) * 100) if max_worst > 0 else 0
            red_val = 200 + int(55 * (intensity / 100))
            worst_bar.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid #aaa;
                    border-radius: 3px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background-color: rgb({red_val}, 100, 100);
                }}
            """)
            self.frequency_table.setCellWidget(row, 4, worst_bar)
        
        self.frequency_table.setSortingEnabled(True)
