"""Individual player statistics display window."""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QTableWidget, QHeaderView, QLabel, QComboBox,
                              QLineEdit, QPushButton, QMessageBox, QFrame,
                              QTableWidgetItem, QDialog, QTextEdit, QDialogButtonBox,
                              QMenu)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QAction
from typing import List, Dict, Optional, Any

from .table_items import NumericTableWidgetItem
from .ui_utils import set_app_icon
from .stats_exporter import StatsExporter
from .player_stats_table_populator import PlayerStatsTablePopulator


class PlayerStatsWindow(QMainWindow):
    """Window to display individual player statistics."""

    # Column definitions for player stats (shooting percentages moved after Pts)
    PLAYER_COLUMNS = [
        "Jugador", "Equipo", "PJ", "Min", "Pts", "%TL", "%T2", "%T3",
        "RO", "RD", "Reb", "Ast", "Rob", "BP", "Tap", "FP", "FR", "+/-", "Val"
    ]

    def __init__(self, player_stats: List[Dict], collection_name: Optional[str] = None,
                 db_handler: Optional[Any] = None, parent: Optional[QWidget] = None):
        """
        Initialize the player stats window.

        Args:
            player_stats: List of player statistics dictionaries
            collection_name: Name of the collection for reloading data
            db_handler: Database handler for accessing MongoDB (optional)
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("MfA - Estadísticas Individuales")
        self.setMinimumSize(1400, 700)

        # Set application icon
        set_app_icon(self)

        self.collection_name = collection_name
        self.db_handler = db_handler
        self.all_player_stats = player_stats
        self.filtered_stats = player_stats.copy()
        self.view_mode = "average"  # Default view mode: average, total, or projection

        # Initialize stats exporter
        self.stats_exporter = StatsExporter(self)

        # Get unique teams for filter
        self.teams = sorted(set(p['team_name'] for p in player_stats))

        self.setup_ui()
        self.populate_table()

    def setup_ui(self):
        """Set up the UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Title
        title_label = QLabel("Estadísticas Individuales por Jugador")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # Filters section
        filters_frame = QFrame()
        filters_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        filters_layout = QHBoxLayout(filters_frame)

        # View mode selector
        view_label = QLabel("Visualización:")
        filters_layout.addWidget(view_label)

        self.view_mode_combo = QComboBox()
        self.view_mode_combo.addItem("Promedios por partido", "average")
        self.view_mode_combo.addItem("Totales acumulados", "total")
        self.view_mode_combo.addItem("Proyección 30 minutos", "projection")
        self.view_mode_combo.currentIndexChanged.connect(self.change_view_mode)
        filters_layout.addWidget(self.view_mode_combo)

        filters_layout.addWidget(QLabel("  "))  # Spacer

        # Team filter
        team_label = QLabel("Equipo:")
        filters_layout.addWidget(team_label)

        self.team_combo = QComboBox()
        self.team_combo.addItem("Todos los equipos")
        self.team_combo.addItems(self.teams)
        self.team_combo.currentTextChanged.connect(self.apply_filters)
        filters_layout.addWidget(self.team_combo)

        # Player search
        search_label = QLabel("Buscar jugador:")
        filters_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Nombre del jugador...")
        self.search_input.textChanged.connect(self.apply_filters)
        filters_layout.addWidget(self.search_input)

        # Clear filters button
        clear_btn = QPushButton("Limpiar filtros")
        clear_btn.clicked.connect(self.clear_filters)
        filters_layout.addWidget(clear_btn)

        filters_layout.addSpacing(20)

        # Add export button with menu
        export_button = QPushButton("📤 Exportar")
        export_button.setToolTip("Exportar tabla actual en diferentes formatos")

        # Create menu for export options
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

        export_button.setMenu(export_menu)
        filters_layout.addWidget(export_button)

        filters_layout.addStretch()
        main_layout.addWidget(filters_frame)

        # Info label
        self.info_label = QLabel(f"Mostrando {len(self.filtered_stats)} jugadores")
        self.info_label.setStyleSheet("padding: 5px; color: #555;")
        main_layout.addWidget(self.info_label)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.PLAYER_COLUMNS))
        self.table.setHorizontalHeaderLabels(self.PLAYER_COLUMNS)

        # Configure table
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)

        # Set column widths
        self.table.horizontalHeader().resizeSection(0, 180)  # Player name
        self.table.horizontalHeader().resizeSection(1, 150)  # Team name
        for i in range(2, len(self.PLAYER_COLUMNS)):
            self.table.horizontalHeader().resizeSection(i, 60)

        main_layout.addWidget(self.table)

        # Style
        self.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: white;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 8px;
                border: 1px solid #d0d0d0;
                font-weight: bold;
            }
            QLineEdit, QComboBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
        """)

    def populate_table(self):
        """Populate the table with player statistics based on current view mode."""
        # Calculate quartiles based on ALL players (not just filtered)
        quartiles = PlayerStatsTablePopulator.calculate_quartiles(
            self.all_player_stats, self.view_mode
        )

        # Populate the table with filtered players
        PlayerStatsTablePopulator.populate_table(
            self.table, self.filtered_stats, self.view_mode, quartiles
        )

        self.update_info_label()

    def apply_filters(self):
        """Apply team and player name filters."""
        selected_team = self.team_combo.currentText()
        search_text = self.search_input.text().lower()

        self.filtered_stats = []
        for player in self.all_player_stats:
            # Team filter
            if selected_team != "Todos los equipos" and player['team_name'] != selected_team:
                continue

            # Name filter
            if search_text and search_text not in player['player_name'].lower():
                continue

            self.filtered_stats.append(player)

        self.populate_table()

    def change_view_mode(self):
        """Change the view mode (average, total, or projection)."""
        self.view_mode = self.view_mode_combo.currentData()
        self.populate_table()

    def clear_filters(self):
        """Clear all filters."""
        self.team_combo.setCurrentIndex(0)
        self.search_input.clear()

    def update_info_label(self):
        """Update the info label with current filter results."""
        self.info_label.setText(f"Mostrando {len(self.filtered_stats)} jugadores")

    def show_projection(self):
        """Show 30-minute projection dialog for selected player."""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "Información", "Por favor, seleccione un jugador de la tabla.")
            return

        row = selected_rows[0].row()
        if row >= len(self.filtered_stats):
            return

        player = self.filtered_stats[row]

        # Calculate 30-minute projection
        minutes_per_game = player.get('minutes_per_game', 0)
        if minutes_per_game == 0:
            QMessageBox.warning(self, "Advertencia", "Este jugador no tiene minutos jugados.")
            return

        projection = self.calculate_30min_projection(player)

        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Proyección 30 Minutos - {player['player_name']}")
        dialog.setMinimumSize(500, 600)

        layout = QVBoxLayout(dialog)

        # Title
        title = QLabel(f"<h2>{player['player_name']}</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Team and current stats
        info = QLabel(f"<b>Equipo:</b> {player['team_name']}<br>"
                     f"<b>Partidos jugados:</b> {player['games_played']}<br>"
                     f"<b>Minutos por partido:</b> {minutes_per_game:.1f}")
        info.setStyleSheet("padding: 10px; background-color: #f5f5f5; border-radius: 5px;")
        layout.addWidget(info)

        # Projection text
        projection_text = QTextEdit()
        projection_text.setReadOnly(True)
        projection_text.setHtml(self._format_projection_html(player, projection))
        layout.addWidget(projection_text)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)

        dialog.exec()

    def calculate_30min_projection(self, player: Dict) -> Dict:
        """
        Calculate 30-minute projection for a player.

        Args:
            player: Player statistics dictionary

        Returns:
            Dictionary with projected statistics
        """
        minutes_per_game = player.get('minutes_per_game', 0)
        if minutes_per_game == 0:
            return {}

        # Calculate multiplier to project to 30 minutes
        multiplier = 30.0 / minutes_per_game

        projection = {
            'points': player.get('points_per_game', 0) * multiplier,
            'assists': player.get('assists_per_game', 0) * multiplier,
            'rebounds': player.get('rebounds_per_game', 0) * multiplier,
            'offensive_rebounds': (player.get('total_ro', 0) / player['games_played']) * multiplier if player['games_played'] > 0 else 0,
            'defensive_rebounds': (player.get('total_rd', 0) / player['games_played']) * multiplier if player['games_played'] > 0 else 0,
            'steals': player.get('steals_per_game', 0) * multiplier,
            'blocks': player.get('blocks_per_game', 0) * multiplier,
            'turnovers': player.get('turnovers_per_game', 0) * multiplier,
            'personal_fouls': (player.get('total_pf', 0) / player['games_played']) * multiplier if player['games_played'] > 0 else 0,
            'fouls_received': (player.get('total_rf', 0) / player['games_played']) * multiplier if player['games_played'] > 0 else 0,
            'valoracion': player.get('valoracion_per_game', 0) * multiplier,
            'p1m': (player.get('total_p1m', 0) / player['games_played']) * multiplier if player['games_played'] > 0 else 0,
            'p1a': (player.get('total_p1a', 0) / player['games_played']) * multiplier if player['games_played'] > 0 else 0,
            'p2m': (player.get('total_p2m', 0) / player['games_played']) * multiplier if player['games_played'] > 0 else 0,
            'p2a': (player.get('total_p2a', 0) / player['games_played']) * multiplier if player['games_played'] > 0 else 0,
            'p3m': (player.get('total_p3m', 0) / player['games_played']) * multiplier if player['games_played'] > 0 else 0,
            'p3a': (player.get('total_p3a', 0) / player['games_played']) * multiplier if player['games_played'] > 0 else 0,
        }

        return projection

    def _format_projection_html(self, player: Dict, projection: Dict) -> str:
        """
        Format projection data as HTML.

        Args:
            player: Original player statistics
            projection: Projected statistics for 30 minutes

        Returns:
            HTML formatted string
        """
        html = "<h3 style='color: #2196F3;'>Proyección a 30 Minutos de Juego</h3>"
        html += "<p style='color: #666;'>Estas estadísticas representan lo que el jugador produciría en promedio si jugara 30 minutos por partido.</p>"
        html += "<hr>"

        html += "<h4>📊 Estadísticas Principales</h4>"
        html += "<table style='width: 100%; border-collapse: collapse;'>"
        html += "<tr style='background-color: #f0f0f0;'><th style='padding: 8px; text-align: left;'>Categoría</th><th style='padding: 8px; text-align: center;'>Actual (por partido)</th><th style='padding: 8px; text-align: center;'>Proyección 30 min</th></tr>"

        stats_to_show = [
            ("Puntos", player.get('points_per_game', 0), projection.get('points', 0)),
            ("Asistencias", player.get('assists_per_game', 0), projection.get('assists', 0)),
            ("Rebotes", player.get('rebounds_per_game', 0), projection.get('rebounds', 0)),
            ("Rebotes Ofensivos", player.get('total_ro', 0) / player['games_played'] if player['games_played'] > 0 else 0, projection.get('offensive_rebounds', 0)),
            ("Rebotes Defensivos", player.get('total_rd', 0) / player['games_played'] if player['games_played'] > 0 else 0, projection.get('defensive_rebounds', 0)),
            ("Robos", player.get('steals_per_game', 0), projection.get('steals', 0)),
            ("Tapones", player.get('blocks_per_game', 0), projection.get('blocks', 0)),
            ("Pérdidas", player.get('turnovers_per_game', 0), projection.get('turnovers', 0)),
            ("Valoración", player.get('valoracion_per_game', 0), projection.get('valoracion', 0)),
        ]

        for i, (label, current, projected) in enumerate(stats_to_show):
            bg_color = "#ffffff" if i % 2 == 0 else "#f9f9f9"
            html += f"<tr style='background-color: {bg_color};'>"
            html += f"<td style='padding: 8px;'><b>{label}</b></td>"
            html += f"<td style='padding: 8px; text-align: center;'>{current:.1f}</td>"
            html += f"<td style='padding: 8px; text-align: center; font-weight: bold; color: #2196F3;'>{projected:.1f}</td>"
            html += "</tr>"

        html += "</table>"

        html += "<br><h4>🎯 Tiros Proyectados</h4>"
        html += "<table style='width: 100%; border-collapse: collapse;'>"
        html += "<tr style='background-color: #f0f0f0;'><th style='padding: 8px; text-align: left;'>Tipo de Tiro</th><th style='padding: 8px; text-align: center;'>Anotados</th><th style='padding: 8px; text-align: center;'>Intentados</th><th style='padding: 8px; text-align: center;'>%</th></tr>"

        shooting_stats = [
            ("Tiros Libres", projection.get('p1m', 0), projection.get('p1a', 0), player.get('fg1_percentage', 0)),
            ("Tiros de 2", projection.get('p2m', 0), projection.get('p2a', 0), player.get('fg2_percentage', 0)),
            ("Tiros de 3", projection.get('p3m', 0), projection.get('p3a', 0), player.get('fg3_percentage', 0)),
        ]

        for i, (label, made, attempted, percentage) in enumerate(shooting_stats):
            bg_color = "#ffffff" if i % 2 == 0 else "#f9f9f9"
            html += f"<tr style='background-color: {bg_color};'>"
            html += f"<td style='padding: 8px;'><b>{label}</b></td>"
            html += f"<td style='padding: 8px; text-align: center;'>{made:.1f}</td>"
            html += f"<td style='padding: 8px; text-align: center;'>{attempted:.1f}</td>"
            html += f"<td style='padding: 8px; text-align: center;'>{percentage:.1f}%</td>"
            html += "</tr>"

        html += "</table>"

        return html

    def _export_csv(self):
        """Export current table to CSV format."""
        self.stats_exporter.export_to_csv(self.table, "Estadisticas_Individuales")

    def _export_png(self):
        """Export current table to PNG image."""
        self.stats_exporter.export_to_png(self.table, "Estadisticas_Individuales")

    def _export_pdf(self):
        """Export current table to PDF format."""
        window_title = self.windowTitle()
        self.stats_exporter.export_to_pdf(self.table, "Estadisticas_Individuales", window_title)
