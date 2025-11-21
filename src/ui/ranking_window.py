"""Player ranking window for competition-wide statistics."""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QTableWidget, QHeaderView, QLabel, QComboBox,
                              QLineEdit, QPushButton, QMessageBox, QFrame,
                              QTableWidgetItem, QMenu)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QAction
from typing import List, Dict, Optional, Any
import statistics

from .table_items import NumericTableWidgetItem
from .ui_utils import set_app_icon
from .stats_exporter import StatsExporter
from .advanced_stats_calculator import AdvancedStatsCalculator


class PlayerRankingWindow(QMainWindow):
    """Window to display player rankings by selected statistic."""

    # Basic statistics available for ranking
    BASIC_STATS = {
        "Pts": ("total_pts", "Puntos totales", False),
        "Pts/PJ": ("ppg", "Puntos por partido", False),
        "Min": ("total_minutes", "Minutos totales", False),
        "Min/PJ": ("mpg", "Minutos por partido", False),
        "RO": ("total_ro", "Rebotes ofensivos", False),
        "RD": ("total_rd", "Rebotes defensivos", False),
        "Reb": ("total_rb", "Rebotes totales", False),
        "Reb/PJ": ("reb_pg", "Rebotes por partido", False),
        "Ast": ("total_as", "Asistencias", False),
        "Ast/PJ": ("ast_pg", "Asistencias por partido", False),
        "Rob": ("total_st", "Robos", False),
        "Rob/PJ": ("stl_pg", "Robos por partido", False),
        "BP": ("total_to", "Pérdidas", True),  # True = lower is better
        "BP/PJ": ("tov_pg", "Pérdidas por partido", True),
        "Tap": ("total_bl", "Tapones", False),
        "Tap/PJ": ("blk_pg", "Tapones por partido", False),
        "Val": ("total_val", "Valoración total", False),
        "Val/PJ": ("val_pg", "Valoración por partido", False),
        "%TL": ("ft_percentage", "Porcentaje de tiros libres", False),
        "%T2": ("fg2_percentage", "Porcentaje de tiros de 2", False),
        "%T3": ("fg3_percentage", "Porcentaje de tiros de 3", False),
    }

    # Advanced statistics available for ranking
    ADVANCED_STATS = {
        "Usg%": ("usage", "Porcentaje de uso", False),
        "ORtg": ("orating", "Rating ofensivo", False),
        "DRtg": ("drating", "Rating defensivo", True),  # Lower is better
        "eFG%": ("efg", "Porcentaje de tiro efectivo", False),
        "TS%": ("ts", "Porcentaje de tiro verdadero", False),
        "FTr": ("ftr", "Tasa de tiros libres", False),
        "3Pr": ("three_pr", "Tasa de triples", False),
        "%AST": ("ast_pct", "Porcentaje de asistencias", False),
        "%TO": ("tov_pct", "Porcentaje de pérdidas", True),  # Lower is better
        "%ROB": ("stl_pct", "Porcentaje de robos", False),
        "%TAP": ("blk_pct", "Porcentaje de tapones", False),
        "%RD": ("drb_pct", "Porcentaje de rebotes defensivos", False),
        "%RO": ("orb_pct", "Porcentaje de rebotes ofensivos", False),
    }

    # Table columns
    COLUMNS = [
        "Pos.", "Jugador", "Equipo", "PJ", "Valor", "Dif. 1º", "Dif. Promedio"
    ]

    def __init__(self, player_stats: List[Dict], collection_name: str,
                 db_handler: Any, parent: Optional[QWidget] = None):
        """
        Initialize the player ranking window.

        Args:
            player_stats: List of all player statistics dictionaries
            collection_name: Name of the collection
            db_handler: Database handler for accessing MongoDB
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("MfA - Rankings de Jugadores")
        self.setMinimumSize(1200, 700)

        # Set application icon
        set_app_icon(self)

        self.collection_name = collection_name
        self.db_handler = db_handler
        self.all_player_stats = player_stats
        self.filtered_stats = player_stats.copy()
        self.current_ranking = []  # Store current ranking data with positions
        self.advanced_stats_calculated = False

        # Initialize helper classes
        self.stats_exporter = StatsExporter(self)

        # Get unique teams for filter
        self.teams = sorted(set(p['team_name'] for p in player_stats))

        # Current selection
        self.current_stat = None
        self.current_stat_key = None
        self.current_is_reverse = False
        self.current_is_advanced = False

        self.setup_ui()

        # Pre-calculate advanced stats
        self._calculate_advanced_stats()

    def setup_ui(self):
        """Set up the UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Title
        title_label = QLabel("Rankings de Jugadores")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # Controls section
        controls_frame = QFrame()
        controls_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        controls_layout = QHBoxLayout(controls_frame)

        # Statistic selector
        stat_label = QLabel("Estadística:")
        stat_label.setStyleSheet("font-weight: bold;")
        controls_layout.addWidget(stat_label)

        self.stat_combo = QComboBox()
        self.stat_combo.addItem("-- Seleccionar estadística --", None)

        # Add basic stats
        self.stat_combo.addItem("═══ Estadísticas Básicas ═══", None)
        for display_name in sorted(self.BASIC_STATS.keys()):
            self.stat_combo.addItem(f"  {display_name}", ("basic", display_name))

        # Add advanced stats
        self.stat_combo.addItem("═══ Estadísticas Avanzadas ═══", None)
        for display_name in sorted(self.ADVANCED_STATS.keys()):
            self.stat_combo.addItem(f"  {display_name}", ("advanced", display_name))

        self.stat_combo.currentIndexChanged.connect(self.on_stat_changed)
        controls_layout.addWidget(self.stat_combo)

        controls_layout.addSpacing(20)

        # Team filter
        team_label = QLabel("Equipo:")
        controls_layout.addWidget(team_label)

        self.team_combo = QComboBox()
        self.team_combo.addItem("Todos los equipos")
        self.team_combo.addItems(self.teams)
        self.team_combo.currentTextChanged.connect(self.apply_filters)
        controls_layout.addWidget(self.team_combo)

        # Player search
        search_label = QLabel("Buscar jugador:")
        controls_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Nombre del jugador...")
        self.search_input.textChanged.connect(self.apply_filters)
        controls_layout.addWidget(self.search_input)

        # Clear filters button
        clear_btn = QPushButton("Limpiar filtros")
        clear_btn.clicked.connect(self.clear_filters)
        controls_layout.addWidget(clear_btn)

        controls_layout.addSpacing(20)

        # Export button
        self.export_button = QPushButton("📤 Exportar")
        self.export_button.setToolTip("Exportar ranking en diferentes formatos")

        export_menu = QMenu(self)

        csv_action = QAction("📊 Exportar como CSV", self)
        csv_action.triggered.connect(self._export_csv)
        export_menu.addAction(csv_action)

        png_action = QAction("🖼️ Exportar como PNG", self)
        png_action.triggered.connect(self._export_png)
        export_menu.addAction(png_action)

        pdf_action = QAction("📄 Exportar como PDF", self)
        pdf_action.triggered.connect(self._export_pdf)
        export_menu.addAction(pdf_action)

        self.export_button.setMenu(export_menu)
        controls_layout.addWidget(self.export_button)

        controls_layout.addStretch()
        main_layout.addWidget(controls_frame)

        # Info label
        self.info_label = QLabel("Seleccione una estadística para ver el ranking")
        self.info_label.setStyleSheet("font-style: italic; padding: 5px;")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.info_label)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSortingEnabled(False)  # Disable sorting to maintain ranking order

        # Configure column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Pos
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)           # Player
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Team
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Games
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Value
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Diff 1st
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Diff Avg

        main_layout.addWidget(self.table)

        # Style
        self.setStyleSheet("""
            QComboBox, QLineEdit {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            QPushButton {
                padding: 5px 10px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QTableWidget {
                gridline-color: #d0d0d0;
                selection-background-color: #4CAF50;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 5px;
                border: 1px solid #d0d0d0;
                font-weight: bold;
            }
        """)

    def _calculate_advanced_stats(self):
        """Calculate advanced statistics for all players."""
        try:
            # Get team stats for advanced calculations
            team_stats = self.db_handler.get_team_stats(self.collection_name)
            team_stats_dict = {team['team_name']: team for team in team_stats}

            # Get opponent stats for advanced calculations
            opp_stats = self.db_handler.get_opponent_stats(self.collection_name)
            opp_stats_dict = {team['team_name']: team for team in opp_stats}

            calculator = AdvancedStatsCalculator()

            for player in self.all_player_stats:
                team_name = player.get('team_name')
                team_data = team_stats_dict.get(team_name, {})
                opp_data = opp_stats_dict.get(team_name, {})

                # Calculate minutes per game and other per-game stats
                games = player.get('games_played', 0)
                player['mpg'] = (player.get('total_minutes', 0) / 60 / games) if games > 0 else 0
                player['ppg'] = player.get('total_pts', 0) / games if games > 0 else 0
                player['reb_pg'] = player.get('total_rb', 0) / games if games > 0 else 0
                player['ast_pg'] = player.get('total_as', 0) / games if games > 0 else 0
                player['stl_pg'] = player.get('total_st', 0) / games if games > 0 else 0
                player['tov_pg'] = player.get('total_to', 0) / games if games > 0 else 0
                player['blk_pg'] = player.get('total_bl', 0) / games if games > 0 else 0
                player['val_pg'] = player.get('total_val', 0) / games if games > 0 else 0

                # Calculate shooting percentages
                fg2a = player.get('total_p2a', 0)
                fg2m = player.get('total_p2m', 0)
                fg3a = player.get('total_p3a', 0)
                fg3m = player.get('total_p3m', 0)
                fta = player.get('total_p1a', 0)
                ftm = player.get('total_p1m', 0)

                player['fg2_percentage'] = (fg2m / fg2a * 100) if fg2a > 0 else 0
                player['fg3_percentage'] = (fg3m / fg3a * 100) if fg3a > 0 else 0
                player['ft_percentage'] = (ftm / fta * 100) if fta > 0 else 0

                # Calculate all advanced stats at once
                if team_data and opp_data:
                    advanced_stats = calculator.calculate_all_advanced_stats(player, team_data, opp_data)
                    player.update(advanced_stats)
                else:
                    # Set default values if stats are not available
                    player.update({
                        'usage': 0.0,
                        'orating': 0.0,
                        'drating': 0.0,
                        'ftr': 0.0,
                        'three_pr': 0.0,
                        'efg': 0.0,
                        'ts': 0.0,
                        'ast_pct': 0.0,
                        'tov_pct': 0.0,
                        'stl_pct': 0.0,
                        'blk_pct': 0.0,
                        'drb_pct': 0.0,
                        'orb_pct': 0.0
                    })

            self.advanced_stats_calculated = True

        except Exception as e:
            print(f"[RankingWindow] Error calculating advanced stats: {e}")
            QMessageBox.warning(self, "Advertencia",
                              f"No se pudieron calcular algunas estadísticas avanzadas: {str(e)}")

    def on_stat_changed(self):
        """Handle statistic selection change."""
        data = self.stat_combo.currentData()

        if data is None:
            self.current_stat = None
            self.current_stat_key = None
            self.table.setRowCount(0)
            self.info_label.setText("Seleccione una estadística para ver el ranking")
            return

        stat_type, stat_name = data

        if stat_type == "basic":
            stat_info = self.BASIC_STATS.get(stat_name)
            self.current_is_advanced = False
        else:
            stat_info = self.ADVANCED_STATS.get(stat_name)
            self.current_is_advanced = True

        if stat_info:
            self.current_stat = stat_name
            self.current_stat_key, stat_description, self.current_is_reverse = stat_info
            self.info_label.setText(f"Ranking: {stat_description}")
            self.populate_table()

    def apply_filters(self):
        """Apply team and player name filters."""
        if not self.current_stat:
            return

        team_filter = self.team_combo.currentText()
        search_text = self.search_input.text().lower().strip()

        # Start with all players
        self.filtered_stats = self.all_player_stats.copy()

        # Apply team filter
        if team_filter != "Todos los equipos":
            self.filtered_stats = [p for p in self.filtered_stats if p['team_name'] == team_filter]

        # Apply player search
        if search_text:
            self.filtered_stats = [p for p in self.filtered_stats
                                  if search_text in p['player_name'].lower()]

        self.populate_table()

    def clear_filters(self):
        """Clear all filters."""
        self.team_combo.setCurrentIndex(0)
        self.search_input.clear()
        self.filtered_stats = self.all_player_stats.copy()
        if self.current_stat:
            self.populate_table()

    def populate_table(self):
        """Populate the ranking table."""
        if not self.current_stat_key:
            self.table.setRowCount(0)
            return

        # Calculate ranking for ALL players (not just filtered)
        valid_players = []
        for player in self.all_player_stats:
            value = player.get(self.current_stat_key, 0)

            # Filter out players with no data or insufficient games for per-game stats
            games = player.get('games_played', 0)
            if games == 0:
                continue

            # For percentage stats, require minimum attempts
            if self.current_stat_key in ['fg2_percentage', 'fg3_percentage', 'ft_percentage']:
                if self.current_stat_key == 'fg2_percentage' and player.get('total_p2a', 0) < 10:
                    continue
                elif self.current_stat_key == 'fg3_percentage' and player.get('total_p3a', 0) < 10:
                    continue
                elif self.current_stat_key == 'ft_percentage' and player.get('total_p1a', 0) < 10:
                    continue

            valid_players.append({
                'player': player,
                'value': value
            })

        if not valid_players:
            self.table.setRowCount(0)
            self.info_label.setText(f"No hay datos suficientes para: {self.current_stat}")
            return

        # Sort by value (reverse if lower is better)
        valid_players.sort(key=lambda x: x['value'], reverse=not self.current_is_reverse)

        # Calculate statistics
        values = [p['value'] for p in valid_players]
        first_value = values[0]
        avg_value = statistics.mean(values) if values else 0

        # Assign positions (handling ties)
        current_position = 1
        for i, item in enumerate(valid_players):
            if i > 0 and item['value'] != valid_players[i-1]['value']:
                current_position = i + 1
            item['position'] = current_position

        # Store ranking data
        self.current_ranking = valid_players

        # Filter for display
        filtered_ranking = [item for item in valid_players
                           if item['player'] in self.filtered_stats]

        # Populate table with filtered data
        self.table.setRowCount(len(filtered_ranking))
        self.table.setSortingEnabled(False)

        for row, item in enumerate(filtered_ranking):
            player = item['player']
            position = item['position']
            value = item['value']

            # Position
            pos_item = QTableWidgetItem(str(position))
            pos_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if position <= 3:
                # Highlight top 3
                if position == 1:
                    pos_item.setBackground(QColor("#FFD700"))  # Gold
                elif position == 2:
                    pos_item.setBackground(QColor("#C0C0C0"))  # Silver
                elif position == 3:
                    pos_item.setBackground(QColor("#CD7F32"))  # Bronze
            self.table.setItem(row, 0, pos_item)

            # Player name
            name_item = QTableWidgetItem(player['player_name'])
            self.table.setItem(row, 1, name_item)

            # Team
            team_item = QTableWidgetItem(player['team_name'])
            self.table.setItem(row, 2, team_item)

            # Games played
            games_played = player.get('games_played', 0)
            games_item = NumericTableWidgetItem(games_played, str(games_played))
            games_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, games_item)

            # Value
            if self.current_stat_key in ['fg2_percentage', 'fg3_percentage', 'ft_percentage'] or \
               self.current_is_advanced:
                value_str = f"{value:.1f}"
            else:
                value_str = f"{value:.1f}"
            value_item = NumericTableWidgetItem(value, value_str)
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 4, value_item)

            # Difference from first
            diff_first = value - first_value
            if abs(diff_first) < 0.05:
                diff_first_str = "-"
                diff_first_val = 0
            else:
                sign = "+" if diff_first > 0 else ""
                diff_first_str = f"{sign}{diff_first:.1f}"
                diff_first_val = diff_first
            diff_first_item = NumericTableWidgetItem(diff_first_val, diff_first_str)
            diff_first_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Color code difference
            if diff_first_str != "-":
                if (diff_first > 0 and not self.current_is_reverse) or (diff_first < 0 and self.current_is_reverse):
                    diff_first_item.setForeground(QColor("#2E7D32"))  # Green (good)
                else:
                    diff_first_item.setForeground(QColor("#C62828"))  # Red (bad)

            self.table.setItem(row, 5, diff_first_item)

            # Difference from average
            diff_avg = value - avg_value
            if abs(diff_avg) < 0.05:
                diff_avg_str = "-"
                diff_avg_val = 0
            else:
                sign = "+" if diff_avg > 0 else ""
                diff_avg_str = f"{sign}{diff_avg:.1f}"
                diff_avg_val = diff_avg
            diff_avg_item = NumericTableWidgetItem(diff_avg_val, diff_avg_str)
            diff_avg_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Color code difference
            if diff_avg_str != "-":
                if (diff_avg > 0 and not self.current_is_reverse) or (diff_avg < 0 and self.current_is_reverse):
                    diff_avg_item.setForeground(QColor("#2E7D32"))  # Green (above avg)
                else:
                    diff_avg_item.setForeground(QColor("#C62828"))  # Red (below avg)

            self.table.setItem(row, 6, diff_avg_item)

        # Update info label
        total_players = len(valid_players)
        filtered_count = len(filtered_ranking)
        if filtered_count < total_players:
            self.info_label.setText(
                f"Ranking: {self.current_stat} - Mostrando {filtered_count} de {total_players} jugadores"
            )
        else:
            self.info_label.setText(
                f"Ranking: {self.current_stat} - {total_players} jugadores"
            )

    def _get_export_context(self):
        """Get context information for exports (filters applied)."""
        context_parts = []

        # Add statistic info
        if self.current_stat:
            stat_type = "Básica" if not self.current_is_advanced else "Avanzada"
            context_parts.append(f"Estadística {stat_type}: {self.current_stat}")

        # Add team filter if applied
        team_filter = self.team_combo.currentText()
        if team_filter != "Todos los equipos":
            context_parts.append(f"Equipo: {team_filter}")

        # Add player filter if applied
        player_filter = self.search_input.text().strip()
        if player_filter:
            context_parts.append(f"Jugador: {player_filter}")

        return " | ".join(context_parts) if context_parts else ""

    def _export_csv(self):
        """Export table to CSV format with context information."""
        # Build filename with context
        filename_parts = [f"ranking_{self.current_stat}"]

        team_filter = self.team_combo.currentText()
        if team_filter != "Todos los equipos":
            filename_parts.append(team_filter.replace(" ", "_"))

        player_filter = self.search_input.text().strip()
        if player_filter:
            filename_parts.append(player_filter.replace(" ", "_"))

        filename_parts.append(self.collection_name)
        filename = "_".join(filename_parts)

        # Get file path
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar CSV",
            f"{filename}.csv",
            "CSV Files (*.csv)"
        )

        if not file_path:
            return

        try:
            import csv
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile, delimiter=';')

                # Write context information as header comments
                writer.writerow([f"Ranking: {self.current_stat}"])
                writer.writerow([f"Competición: {self.collection_name}"])

                if team_filter != "Todos los equipos":
                    writer.writerow([f"Filtro de Equipo: {team_filter}"])

                if player_filter:
                    writer.writerow([f"Filtro de Jugador: {player_filter}"])

                writer.writerow([])  # Empty row separator

                # Write table headers
                headers = []
                for col in range(self.table.columnCount()):
                    headers.append(self.table.horizontalHeaderItem(col).text())
                writer.writerow(headers)

                # Write data rows
                for row in range(self.table.rowCount()):
                    row_data = []
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        if item:
                            row_data.append(item.text())
                        else:
                            row_data.append("")
                    writer.writerow(row_data)

            QMessageBox.information(
                self,
                "Exportación exitosa",
                f"Tabla exportada correctamente a:\n{file_path}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error de exportación",
                f"Error al exportar CSV: {str(e)}"
            )

    def _export_png(self):
        """Export table as PNG image with context information."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget, QVBoxLayout, QLabel
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QPixmap, QPainter

        # Build filename with context
        filename_parts = [f"ranking_{self.current_stat}"]

        team_filter = self.team_combo.currentText()
        if team_filter != "Todos los equipos":
            filename_parts.append(team_filter.replace(" ", "_"))

        player_filter = self.search_input.text().strip()
        if player_filter:
            filename_parts.append(player_filter.replace(" ", "_"))

        filename_parts.append(self.collection_name)
        filename = "_".join(filename_parts)

        # Get file path
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar PNG",
            f"{filename}.png",
            "PNG Files (*.png)"
        )

        if not file_path:
            return

        try:
            # Create a temporary widget to hold header + table
            temp_widget = QWidget()
            temp_layout = QVBoxLayout(temp_widget)
            temp_layout.setContentsMargins(20, 20, 20, 20)
            temp_layout.setSpacing(10)

            # Add header labels with context information
            title_label = QLabel(f"<h2>Ranking: {self.current_stat}</h2>")
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            temp_layout.addWidget(title_label)

            info_parts = [f"<b>Competición:</b> {self.collection_name}"]
            if team_filter != "Todos los equipos":
                info_parts.append(f"<b>Equipo:</b> {team_filter}")
            if player_filter:
                info_parts.append(f"<b>Jugador:</b> {player_filter}")

            info_label = QLabel(" | ".join(info_parts))
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info_label.setStyleSheet("font-size: 11pt; padding: 5px;")
            temp_layout.addWidget(info_label)

            # Add the table
            temp_layout.addWidget(self.table)

            # Set size and render
            temp_widget.resize(self.table.width() + 40, self.table.height() + 150)
            temp_widget.show()  # Need to show for proper rendering

            # Grab the widget as pixmap
            pixmap = temp_widget.grab()

            # Remove table from temp layout and restore it
            temp_layout.removeWidget(self.table)
            self.centralWidget().layout().addWidget(self.table)
            temp_widget.close()

            # Save pixmap
            if pixmap.save(file_path, "PNG"):
                QMessageBox.information(
                    self,
                    "Exportación exitosa",
                    f"Imagen exportada correctamente a:\n{file_path}"
                )
            else:
                raise Exception("No se pudo guardar la imagen")

        except Exception as e:
            # Ensure table is restored in case of error
            try:
                self.centralWidget().layout().addWidget(self.table)
            except:
                pass
            QMessageBox.critical(
                self,
                "Error de exportación",
                f"Error al exportar PNG: {str(e)}"
            )

    def _export_pdf(self):
        """Export table to PDF format."""
        # Build title with all context
        title = f"Ranking: {self.current_stat}"

        # Build subtitle with filters
        subtitle_parts = [f"Competición: {self.collection_name}"]

        team_filter = self.team_combo.currentText()
        if team_filter != "Todos los equipos":
            subtitle_parts.append(f"Equipo: {team_filter}")

        player_filter = self.search_input.text().strip()
        if player_filter:
            subtitle_parts.append(f"Jugador: {player_filter}")

        subtitle = " | ".join(subtitle_parts)

        # Build filename with context
        filename_parts = [f"ranking_{self.current_stat}"]
        if team_filter != "Todos los equipos":
            filename_parts.append(team_filter.replace(" ", "_"))
        if player_filter:
            filename_parts.append(player_filter.replace(" ", "_"))
        filename_parts.append(self.collection_name)
        filename = "_".join(filename_parts)

        self.stats_exporter.export_to_pdf(
            self.table,
            filename,
            title,
            subtitle
        )
