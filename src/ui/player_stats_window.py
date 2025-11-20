"""Individual player statistics display window."""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QTableWidget, QHeaderView, QLabel, QComboBox,
                              QLineEdit, QPushButton, QMessageBox, QFrame,
                              QTableWidgetItem, QDialog, QTextEdit, QDialogButtonBox,
                              QMenu)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QAction
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime, timedelta

from .table_items import NumericTableWidgetItem
from .ui_utils import set_app_icon
from .stats_exporter import StatsExporter
from .player_stats_table_populator import PlayerStatsTablePopulator
from .advanced_stats_calculator import AdvancedStatsCalculator
from .stats_config import calculate_quartiles, get_quartile_color
from .trend_calculator import TrendCalculator


class PlayerStatsWindow(QMainWindow):
    """Window to display individual player statistics."""

    # Column definitions for player stats (shooting percentages moved after Pts)
    PLAYER_COLUMNS = [
        "Jugador", "Equipo", "PJ", "Min", "Pts", "%TL", "%T2", "%T3",
        "RO", "RD", "Reb", "Ast", "Rob", "BP", "Tap", "FP", "FR", "+/-", "Val"
    ]

    # Column definitions for advanced stats
    ADVANCED_COLUMNS = [
        "Jugador", "Equipo", "PJ", "Min/PJ", "Pts/PJ",
        "Usg%", "ORtg", "DRtg", "FTr", "3Pr", "eFG%", "TS%",
        "%AST", "%TO", "%ROB", "%TAP", "%RD", "%RO", "Val/PJ"
    ]

    # Field definitions for quartile calculation and coloring (advanced stats)
    ADVANCED_STAT_FIELDS = {
        3: ('mpg', False),          # Min/PJ
        4: ('ppg', False),          # Pts/PJ
        5: ('usage', False),        # Usg%
        6: ('orating', False),      # ORtg
        7: ('drating', True),       # DRtg (reverse - lower is better)
        8: ('ftr', False),          # FTr
        9: ('three_pr', False),     # 3Pr
        10: ('efg', False),         # eFG%
        11: ('ts', False),          # TS%
        12: ('ast_pct', False),     # %AST
        13: ('tov_pct', True),      # %TO (reverse)
        14: ('stl_pct', False),     # %ROB
        15: ('blk_pct', False),     # %TAP
        16: ('drb_pct', False),     # %RD
        17: ('orb_pct', False),     # %RO
        18: ('val_pg', False),      # Val/PJ
    }

    # Filter constants
    RESULT_WON = 'won'
    RESULT_LOST = 'lost'
    VENUE_HOME = True
    VENUE_AWAY = False

    # Cache keys
    CACHE_GENERAL = 'general'
    CACHE_HOME = 'home'
    CACHE_AWAY = 'away'
    CACHE_WON = 'won'
    CACHE_LOST = 'lost'

    def __init__(self, player_stats: List[Dict], collection_name: Optional[str] = None,
                 reload_callback: Optional[Callable] = None, db_handler: Optional[Any] = None,
                 parent: Optional[QWidget] = None):
        """
        Initialize the player stats window.

        Args:
            player_stats: List of player statistics dictionaries
            collection_name: Name of the collection for reloading data
            reload_callback: Callback function to reload data with date filter
            db_handler: Database handler for accessing MongoDB (optional)
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("MfA - Estadísticas Individuales")
        self.setMinimumSize(1600, 700)

        # Set application icon
        set_app_icon(self)

        self.collection_name = collection_name
        self.reload_callback = reload_callback
        self.db_handler = db_handler
        self.all_player_stats = player_stats
        self.filtered_stats = player_stats.copy()
        self.view_mode = "average"  # Default view mode: average, total, or projection
        self.show_advanced = False  # Toggle between basic and advanced stats
        self.advanced_stats_calculated = False

        # Initialize helper classes
        self.trend_calculator = TrendCalculator()
        self.stats_exporter = StatsExporter(self)

        # Comparative mode tracking
        self.is_comparative_mode = False
        self.comparison_data = None  # Will store the "rest" data for comparison

        # Cache for loaded data to avoid reloading when switching periods
        self._data_cache = {
            self.CACHE_GENERAL: None,
            self.CACHE_HOME: None,
            self.CACHE_AWAY: None,
            self.CACHE_WON: None,
            self.CACHE_LOST: None
        }

        # Get unique teams for filter
        self.teams = sorted(set(p['team_name'] for p in player_stats))

        self.setup_ui()

        # Pre-calculate advanced stats if database is available
        if self.db_handler and self.collection_name:
            try:
                self._calculate_advanced_stats()
                self.advanced_stats_calculated = True
            except Exception as e:
                print(f"[PlayerStatsWindow] Could not pre-calculate advanced stats: {e}")
                self.advanced_stats_calculated = False

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

        # Period selector section (new)
        period_frame = QFrame()
        period_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        period_layout = QHBoxLayout(period_frame)

        # Add period selector ComboBox
        period_label = QLabel("Período:")
        period_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        period_layout.addWidget(period_label)

        self.period_combo = QComboBox()
        self.period_combo.addItem("General (toda la temporada)", "general")
        self.period_combo.addItem("Últimos 7 días vs resto", "comparative_7")
        self.period_combo.addItem("Últimos 15 días vs resto", "comparative_15")
        self.period_combo.addItem("Últimos 30 días vs resto", "comparative_30")
        self.period_combo.addItem("Últimos 60 días vs resto", "comparative_60")
        self.period_combo.addItem("Local vs Visitante", "venue_comparative")
        self.period_combo.addItem("Ganados vs Perdidos", "result_comparative")
        self.period_combo.setToolTip("Seleccionar período de estadísticas")
        self.period_combo.currentIndexChanged.connect(self._on_period_changed)
        period_layout.addWidget(self.period_combo)

        period_layout.addStretch()
        main_layout.addWidget(period_frame)

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
        self.view_mode_combo.addItem("Estadísticas Avanzadas", "advanced")
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

        # Add trend legend (hidden by default, shown in comparative mode)
        self.trend_legend = self._create_trend_legend()
        self.trend_legend.setVisible(False)
        main_layout.addWidget(self.trend_legend)

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
        if self.show_advanced:
            self._populate_advanced_table()
        else:
            # Calculate quartiles based on ALL players (not just filtered)
            quartiles = PlayerStatsTablePopulator.calculate_quartiles(
                self.all_player_stats, self.view_mode
            )

            # Check if we're in comparative mode
            if self.is_comparative_mode and self.comparison_data:
                # Populate with comparative data showing trends
                self._populate_comparative_table(quartiles)
            else:
                # Populate the table with filtered players (normal mode)
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
        """Change the view mode (average, total, projection, or advanced)."""
        new_mode = self.view_mode_combo.currentData()

        # Check if switching to/from advanced mode
        if new_mode == "advanced" and not self.show_advanced:
            # Switching to advanced stats
            if not self.advanced_stats_calculated:
                # Stats should have been pre-calculated, but try again if not
                if self.db_handler and self.collection_name:
                    try:
                        self._calculate_advanced_stats()
                        self.advanced_stats_calculated = True
                    except Exception as e:
                        QMessageBox.warning(
                            self,
                            "Error",
                            f"No se pudieron calcular las estadísticas avanzadas:\n{str(e)}"
                        )
                        # Revert to previous mode
                        self.view_mode_combo.setCurrentIndex(0)
                        return
                else:
                    QMessageBox.warning(
                        self,
                        "Error",
                        "No hay conexión a la base de datos para calcular estadísticas avanzadas."
                    )
                    # Revert to previous mode
                    self.view_mode_combo.setCurrentIndex(0)
                    return

            # Switch to advanced view
            self.show_advanced = True
            self.view_mode = "advanced"

            # Update table structure for advanced stats
            self.table.setColumnCount(len(self.ADVANCED_COLUMNS))
            self.update_column_headers()

            # Set column widths for advanced stats
            self.table.horizontalHeader().resizeSection(0, 160)  # Player name (reduced from 180)
            self.table.horizontalHeader().resizeSection(1, 130)  # Team name (reduced from 150)
            self.table.horizontalHeader().resizeSection(2, 50)   # PJ (games played)
            # Other columns: Min/PJ through Val/PJ
            for i in range(3, len(self.ADVANCED_COLUMNS)):
                self.table.horizontalHeader().resizeSection(i, 75)  # Reduced from 80

        elif new_mode != "advanced" and self.show_advanced:
            # Switching from advanced to basic mode
            self.show_advanced = False
            self.view_mode = new_mode

            # Update table structure for basic stats
            self.table.setColumnCount(len(self.PLAYER_COLUMNS))
            self.update_column_headers()

            # Set column widths for basic stats
            self.table.horizontalHeader().resizeSection(0, 180)  # Player name
            self.table.horizontalHeader().resizeSection(1, 150)  # Team name
            for i in range(2, len(self.PLAYER_COLUMNS)):
                self.table.horizontalHeader().resizeSection(i, 60)
        else:
            # Normal view mode change (within basic stats)
            self.view_mode = new_mode
            self.update_column_headers()

        self.populate_table()

    def update_column_headers(self):
        """Update column headers based on view mode."""
        if self.show_advanced:
            headers = self.ADVANCED_COLUMNS.copy()
        elif self.view_mode == "total":
            # For totals, remove % from percentage columns
            headers = [
                "Jugador", "Equipo", "PJ", "Min", "Pts", "TL", "T2", "T3",
                "RO", "RD", "Reb", "Ast", "Rob", "BP", "Tap", "FP", "FR", "+/-", "Val"
            ]
        else:
            # For average and projection, keep % in headers
            headers = self.PLAYER_COLUMNS.copy()

        self.table.setHorizontalHeaderLabels(headers)

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

    def _calculate_advanced_stats(self):
        """Calculate advanced statistics for all players."""
        self._calculate_advanced_stats_for_dataset(self.all_player_stats)

    def _calculate_advanced_stats_for_dataset(self, player_stats: List[Dict]):
        """
        Calculate advanced statistics for a specific dataset of players.

        Args:
            player_stats: List of player statistics to calculate advanced stats for
        """
        # Group players by team to get team and opponent stats
        teams = {}
        for player in player_stats:
            team_name = player['team_name']
            if team_name not in teams:
                teams[team_name] = {
                    'team_stats': self.db_handler.get_aggregated_team_stats(
                        self.collection_name, team_name
                    ),
                    'opp_stats': self.db_handler.get_aggregated_opponent_stats(
                        self.collection_name, team_name
                    )
                }

        # Calculate advanced stats for each player
        for player in player_stats:
            team_name = player['team_name']
            team_data = teams.get(team_name, {})
            team_stats = team_data.get('team_stats', {})
            opp_stats = team_data.get('opp_stats', {})

            if team_stats and opp_stats:
                advanced_stats = AdvancedStatsCalculator.calculate_all_advanced_stats(
                    player, team_stats, opp_stats
                )
                player.update(advanced_stats)
            else:
                # Set default values if stats are not available
                self._set_default_advanced_stats(player)

    def _set_default_advanced_stats(self, player: Dict):
        """Set default advanced stats values for a player."""
        player.update({
            'mpg': player.get('minutes_per_game', 0),
            'ppg': player.get('points_per_game', 0),
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
            'orb_pct': 0.0,
            'val_pg': 0.0
        })

    def _calculate_advanced_quartiles(self) -> Dict:
        """Calculate quartiles for advanced statistics fields."""
        quartiles = {}

        for col_idx, (field_name, _) in self.ADVANCED_STAT_FIELDS.items():
            values = []
            for player in self.all_player_stats:
                value = player.get(field_name, 0)
                if value != 0:  # Only include non-zero values
                    values.append(value)

            if values:
                # Calculate quartiles using numpy percentiles
                import numpy as np
                quartiles[field_name] = [np.percentile(values, q) for q in [25, 50, 75]]

        return quartiles

    def _populate_advanced_table(self):
        """Populate table with advanced statistics."""
        # Calculate quartiles for advanced stats
        quartiles = self._calculate_advanced_quartiles()

        # Clear and set up table
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.filtered_stats))

        for row, player in enumerate(self.filtered_stats):
            # Column 0: Player name
            self.table.setItem(row, 0, QTableWidgetItem(player.get('player_name', '')))

            # Column 1: Team name
            self.table.setItem(row, 1, QTableWidgetItem(player.get('team_name', '')))

            # Column 2: Games played - show comparison if in comparative mode
            games = player.get('games_played', 0)
            player_id = player.get('player_id')

            # Find comparison player if in comparative mode
            comparison_player_adv = None
            if self.is_comparative_mode and self.comparison_data and player_id:
                for comp_player in self.comparison_data:
                    if comp_player.get('player_id') == player_id:
                        comparison_player_adv = comp_player
                        break

            if comparison_player_adv:
                comp_games = comparison_player_adv.get('games_played', 0)
                games_text = f"{games} + {comp_games}"
                games_item = NumericTableWidgetItem(games + comp_games, games_text)
            else:
                games_item = NumericTableWidgetItem(games, str(games))
            self.table.setItem(row, 2, games_item)

            # Add advanced stats with quartile coloring
            self._add_advanced_stat_cells(row, player, quartiles)

        self.table.setSortingEnabled(True)

    def _add_advanced_stat_cells(self, row: int, player: Dict, quartiles: Dict):
        """Add advanced statistics cells with quartile-based coloring and trend indicators."""
        player_id = player.get('player_id')

        # Create lookup dict for comparison data if in comparative mode
        comparison_player = None
        if self.is_comparative_mode and self.comparison_data and player_id:
            for comp_player in self.comparison_data:
                if comp_player.get('player_id') == player_id:
                    comparison_player = comp_player
                    break

        for col_idx, (field_name, reverse) in self.ADVANCED_STAT_FIELDS.items():
            value = player.get(field_name, 0)

            # Format value
            if field_name in ['mpg', 'ppg', 'val_pg']:
                formatted_value = f"{value:.1f}"
            elif field_name in ['orating', 'drating']:
                formatted_value = f"{value:.1f}"
            else:
                formatted_value = f"{value:.1f}%" if value != 0 else "0.0%"

            # Create item
            item = NumericTableWidgetItem(value, formatted_value)

            # Apply quartile coloring
            if value != 0 and field_name in quartiles:
                color = get_quartile_color(value, quartiles[field_name], reverse)
                item.setBackground(color)

            # Add trend indicator if in comparative mode
            if self.is_comparative_mode and comparison_player:
                comparison_val = comparison_player.get(field_name, 0)

                # Calculate delta (percentage change)
                if comparison_val != 0:
                    delta = ((value - comparison_val) / comparison_val) * 100
                else:
                    delta = 0 if value == 0 else 100

                # Map field names for trend calculation (some need special handling)
                field_name_for_trend = field_name
                if field_name == 'drating':
                    field_name_for_trend = 'defensive_rating'
                elif field_name == 'tov_pct':
                    field_name_for_trend = 'turnovers'

                # Get trend indicator symbol and color
                trend_symbol, trend_color = self.trend_calculator.get_trend_indicator(
                    delta, field_name_for_trend, is_opponent=False
                )

                # Add symbol to the text if there's a meaningful trend
                if trend_symbol and trend_symbol != "—":
                    item.setText(f"{formatted_value} {trend_symbol}")

            self.table.setItem(row, col_idx, item)

    def _populate_comparative_table(self, quartiles: Dict):
        """Populate table with comparative statistics showing trends."""
        from .player_stats_calculator import PlayerStatsCalculator

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.filtered_stats))

        # Create lookup dict for comparison data by player_id
        comparison_dict = {}
        if self.comparison_data:
            for player in self.comparison_data:
                player_id = player.get('player_id')
                if player_id:
                    comparison_dict[player_id] = player

        for row, current_player in enumerate(self.filtered_stats):
            games_played = current_player.get('games_played', 0)
            minutes_per_game = current_player.get('minutes_per_game', 0)
            player_id = current_player.get('player_id')

            # Get comparison player if exists
            comparison_player = comparison_dict.get(player_id) if player_id else None

            # Player name (col 0)
            self.table.setItem(row, 0, QTableWidgetItem(str(current_player.get('player_name', ''))))

            # Team name (col 1)
            self.table.setItem(row, 1, QTableWidgetItem(str(current_player.get('team_name', ''))))

            # Games played (col 2) - show comparison if available
            if comparison_player:
                comp_games = comparison_player.get('games_played', 0)
                games_text = f"{games_played} + {comp_games}"
                # Use the sum for sorting purposes
                games_item = NumericTableWidgetItem(games_played + comp_games, games_text)
            else:
                games_item = NumericTableWidgetItem(games_played, str(games_played))
            self.table.setItem(row, 2, games_item)

            # Statistics columns with trend indicators
            for col_idx, (field_key, reverse) in PlayerStatsTablePopulator.STAT_FIELDS.items():
                current_val = PlayerStatsCalculator.get_stat_value(
                    current_player, field_key, self.view_mode, games_played, minutes_per_game
                )

                # Format the value
                if field_key in ['fg1_pct', 'fg2_pct', 'fg3_pct']:
                    formatted = f"{current_val:.1f}%"
                elif field_key == 'minutes' and self.view_mode == 'average':
                    formatted = f"{current_val:.1f}"
                else:
                    formatted = f"{current_val:.1f}"

                # Create base item
                item = NumericTableWidgetItem(current_val, formatted)

                # Apply quartile coloring
                if col_idx in quartiles and len(quartiles[col_idx]) == 3:
                    color = get_quartile_color(current_val, quartiles[col_idx], reverse)
                    item.setBackground(color)

                # Add trend indicator if comparison data exists
                if comparison_player:
                    comp_games = comparison_player.get('games_played', 0)
                    comp_minutes = comparison_player.get('minutes_per_game', 0)
                    comparison_val = PlayerStatsCalculator.get_stat_value(
                        comparison_player, field_key, self.view_mode, comp_games, comp_minutes
                    )

                    # Calculate delta (percentage change)
                    if comparison_val != 0:
                        delta = ((current_val - comparison_val) / comparison_val) * 100
                    else:
                        delta = 0 if current_val == 0 else 100

                    # For player stats, determine if lower is better based on field key
                    # 'to' (turnovers) and 'pf' (personal fouls) are reverse fields
                    field_name_for_trend = field_key
                    if field_key == 'to':
                        field_name_for_trend = 'turnovers'
                    elif field_key == 'pf':
                        field_name_for_trend = 'personal_fouls'

                    # Get trend indicator symbol and color
                    trend_symbol, trend_color = self.trend_calculator.get_trend_indicator(
                        delta, field_name_for_trend, is_opponent=False
                    )

                    # Add symbol to the text if there's a meaningful trend
                    if trend_symbol and trend_symbol != "—":
                        item.setText(f"{formatted} {trend_symbol}")

                self.table.setItem(row, col_idx, item)

        self.table.setSortingEnabled(True)

    def _create_trend_legend(self) -> QWidget:
        """Create a trend indicator legend widget for comparative mode."""
        legend_frame = QFrame()
        legend_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        legend_frame.setMaximumHeight(40)

        legend_layout = QHBoxLayout(legend_frame)
        legend_layout.setContentsMargins(10, 5, 10, 5)
        legend_layout.setSpacing(15)

        # Add legend title
        self.trend_legend_title = QLabel("Tendencia:")
        self.trend_legend_title.setStyleSheet("font-weight: bold;")
        legend_layout.addWidget(self.trend_legend_title)

        # Get trend indicators from calculator
        trends = self.trend_calculator.get_legend_items()

        for symbol, description, color in trends:
            # Create container for each legend item
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(5)

            # Create symbol label
            symbol_label = QLabel(symbol)
            symbol_label.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {color};")
            symbol_label.setFixedWidth(25)
            item_layout.addWidget(symbol_label)

            # Create description label
            text_label = QLabel(description)
            text_label.setStyleSheet("font-size: 9pt;")
            item_layout.addWidget(text_label)

            legend_layout.addWidget(item_widget)

        # Add stretch to push items to the left
        legend_layout.addStretch()

        return legend_frame

    def _update_trend_legend_title(self, comparison_text: str):
        """Update the trend legend title with the current comparison type."""
        if hasattr(self, 'trend_legend_title'):
            self.trend_legend_title.setText(f"Tendencia ({comparison_text}):")

    def _on_period_changed(self, index: int):
        """Handle period selection change."""
        if not self.reload_callback or not self.collection_name:
            QMessageBox.warning(self, "Error", "No se puede recargar datos sin callback o nombre de colección")
            return

        period_type = self.period_combo.itemData(index)

        try:
            if period_type and period_type.startswith("comparative"):
                # Extract days from period type (e.g., "comparative_30" -> 30)
                days = 30  # default
                if "_" in period_type:
                    try:
                        days = int(period_type.split("_")[1])
                    except (ValueError, IndexError):
                        days = 30

                # Load both recent period and rest-of-season data for comparison
                now = datetime.now()
                period_start = now - timedelta(days=days)

                # Use dynamic cache key based on days
                cache_key_recent = f"recent_{days}"
                cache_key_rest = f"rest_{days}"

                # Check cache first
                if cache_key_recent not in self._data_cache or cache_key_rest not in self._data_cache or \
                   self._data_cache.get(cache_key_recent) is None or self._data_cache.get(cache_key_rest) is None:
                    # Get recent period data
                    recent_filter = {"$gte": period_start}
                    recent_stats = self.reload_callback(
                        self.collection_name, date_filter=recent_filter, venue_filter=None, result_filter=None
                    )

                    # Get rest of season data (before recent period)
                    rest_filter = {"$lt": period_start}
                    rest_stats = self.reload_callback(
                        self.collection_name, date_filter=rest_filter, venue_filter=None, result_filter=None
                    )

                    # Cache the loaded data
                    self._data_cache[cache_key_recent] = recent_stats
                    self._data_cache[cache_key_rest] = rest_stats
                else:
                    # Use cached data
                    recent_stats = self._data_cache[cache_key_recent]
                    rest_stats = self._data_cache[cache_key_rest]

                if not recent_stats or not rest_stats:
                    QMessageBox.information(self, "Sin datos", "No hay suficientes datos para comparar")
                    return

                # ENABLE comparative mode
                self.is_comparative_mode = True
                self.comparison_data = rest_stats

                # Update stored data with recent stats
                self.all_player_stats = recent_stats
                self.filtered_stats = recent_stats.copy()
                self.teams = sorted(set(p['team_name'] for p in recent_stats))

                # Invalidate advanced stats - need to recalculate with new data
                self.advanced_stats_calculated = False
                if self.show_advanced and self.db_handler:
                    try:
                        self._calculate_advanced_stats()
                        # Also calculate for comparison data
                        if rest_stats:
                            self._calculate_advanced_stats_for_dataset(rest_stats)
                        self.advanced_stats_calculated = True
                    except Exception as e:
                        print(f"[PlayerStatsWindow] Error recalculating advanced stats: {e}")

                # Update legend title with selected period
                period_label = f"últimos {days} días" if days != 30 else "último mes"
                self._update_trend_legend_title(f"{period_label} vs resto temporada")

                # Show trend legend
                self.trend_legend.setVisible(True)

                # Reload filters and table
                self._reload_filters()
                self.populate_table()

            elif period_type == "venue_comparative":
                # Load both home and away data for comparison
                # Check cache first
                if self._data_cache[self.CACHE_HOME] is None or self._data_cache[self.CACHE_AWAY] is None:
                    # Get home data
                    home_stats = self.reload_callback(
                        self.collection_name, date_filter=None, venue_filter=self.VENUE_HOME, result_filter=None
                    )

                    # Get away data
                    away_stats = self.reload_callback(
                        self.collection_name, date_filter=None, venue_filter=self.VENUE_AWAY, result_filter=None
                    )

                    # Cache the loaded data
                    self._data_cache[self.CACHE_HOME] = home_stats
                    self._data_cache[self.CACHE_AWAY] = away_stats
                else:
                    # Use cached data
                    home_stats = self._data_cache[self.CACHE_HOME]
                    away_stats = self._data_cache[self.CACHE_AWAY]

                if not home_stats or not away_stats:
                    QMessageBox.information(self, "Sin datos", "No hay suficientes datos para comparar")
                    return

                # ENABLE comparative mode
                self.is_comparative_mode = True
                self.comparison_data = away_stats

                # Update stored data with home stats
                self.all_player_stats = home_stats
                self.filtered_stats = home_stats.copy()
                self.teams = sorted(set(p['team_name'] for p in home_stats))

                # Invalidate advanced stats - need to recalculate with new data
                self.advanced_stats_calculated = False
                if self.show_advanced and self.db_handler:
                    try:
                        self._calculate_advanced_stats()
                        # Also calculate for comparison data
                        if away_stats:
                            self._calculate_advanced_stats_for_dataset(away_stats)
                        self.advanced_stats_calculated = True
                    except Exception as e:
                        print(f"[PlayerStatsWindow] Error recalculating advanced stats: {e}")

                # Update legend title
                self._update_trend_legend_title("local vs visitante")

                # Show trend legend
                self.trend_legend.setVisible(True)

                # Reload filters and table
                self._reload_filters()
                self.populate_table()

            elif period_type == "result_comparative":
                # Load both won and lost games data for comparison
                # Check cache first
                if self._data_cache[self.CACHE_WON] is None or self._data_cache[self.CACHE_LOST] is None:
                    # Get won games data
                    won_stats = self.reload_callback(
                        self.collection_name, date_filter=None, venue_filter=None, result_filter=self.RESULT_WON
                    )

                    # Get lost games data
                    lost_stats = self.reload_callback(
                        self.collection_name, date_filter=None, venue_filter=None, result_filter=self.RESULT_LOST
                    )

                    # Cache the loaded data
                    self._data_cache[self.CACHE_WON] = won_stats
                    self._data_cache[self.CACHE_LOST] = lost_stats
                else:
                    # Use cached data
                    won_stats = self._data_cache[self.CACHE_WON]
                    lost_stats = self._data_cache[self.CACHE_LOST]

                if not won_stats or not lost_stats:
                    QMessageBox.information(self, "Sin datos", "No hay suficientes datos para comparar")
                    return

                # ENABLE comparative mode
                self.is_comparative_mode = True
                self.comparison_data = lost_stats

                # Update stored data with won stats
                self.all_player_stats = won_stats
                self.filtered_stats = won_stats.copy()
                self.teams = sorted(set(p['team_name'] for p in won_stats))

                # Invalidate advanced stats - need to recalculate with new data
                self.advanced_stats_calculated = False
                if self.show_advanced and self.db_handler:
                    try:
                        self._calculate_advanced_stats()
                        # Also calculate for comparison data
                        if lost_stats:
                            self._calculate_advanced_stats_for_dataset(lost_stats)
                        self.advanced_stats_calculated = True
                    except Exception as e:
                        print(f"[PlayerStatsWindow] Error recalculating advanced stats: {e}")

                # Update legend title
                self._update_trend_legend_title("ganados vs perdidos")

                # Show trend legend
                self.trend_legend.setVisible(True)

                # Reload filters and table
                self._reload_filters()
                self.populate_table()

            else:
                # General mode - all data
                # DISABLE comparative mode
                self.is_comparative_mode = False
                self.comparison_data = None

                # Check cache first
                if self._data_cache[self.CACHE_GENERAL] is None:
                    player_stats = self.reload_callback(
                        self.collection_name, date_filter=None, venue_filter=None, result_filter=None
                    )
                    # Cache the loaded data
                    self._data_cache[self.CACHE_GENERAL] = player_stats
                else:
                    # Use cached data
                    player_stats = self._data_cache[self.CACHE_GENERAL]

                if not player_stats:
                    QMessageBox.information(self, "Sin datos", "No hay datos para el período seleccionado")
                    return

                # Update the stored data
                self.all_player_stats = player_stats
                self.filtered_stats = player_stats.copy()
                self.teams = sorted(set(p['team_name'] for p in player_stats))

                # Invalidate advanced stats - need to recalculate with new data
                self.advanced_stats_calculated = False
                if self.show_advanced and self.db_handler:
                    try:
                        self._calculate_advanced_stats()
                        self.advanced_stats_calculated = True
                    except Exception as e:
                        print(f"[PlayerStatsWindow] Error recalculating advanced stats: {e}")

                # Hide trend legend in normal mode
                self.trend_legend.setVisible(False)

                # Reload filters and table
                self._reload_filters()
                self.populate_table()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar datos: {str(e)}")

    def _reload_filters(self):
        """Reload team filter combo with new data."""
        current_team = self.team_combo.currentText()
        self.team_combo.clear()
        self.team_combo.addItem("Todos los equipos")
        self.team_combo.addItems(self.teams)

        # Try to restore previous selection
        index = self.team_combo.findText(current_team)
        if index >= 0:
            self.team_combo.setCurrentIndex(index)

