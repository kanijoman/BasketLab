"""Team statistics display window."""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QTableWidget, QHeaderView, QTabWidget, QPushButton,
                              QFileDialog, QMessageBox, QMenu, QTableWidgetItem, QLabel,
                              QRadioButton, QButtonGroup, QComboBox, QFrame, QDialog,
                              QProgressDialog, QApplication)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QColor
from typing import List, Dict, Callable, Optional, Any
from datetime import datetime, timedelta

from .table_items import NumericTableWidgetItem
from .stats_config import (
    BASIC_COLUMNS, ADVANCED_COLUMNS,
    get_basic_numeric_data, get_advanced_numeric_data,
    calculate_quartiles
)
from .trend_calculator import TrendCalculator
from .ui_utils import set_app_icon
from .team_selector_dialog import TeamSelectorDialog
from .stats_calculator import StatsCalculator
from .stats_exporter import StatsExporter
from .stats_table_manager import StatsTableManager
from .comparative_mode_manager import ComparativeModeManager
from .trend_legend_builder import TrendLegendBuilder
from .team_utils import get_team_data_by_name
from .stats_filter_constants import RESULT_WON, RESULT_LOST, VENUE_HOME, VENUE_AWAY


class TeamStatsWindow(QMainWindow):
    """Window to display team statistics."""

    # Column group definitions: (start_col, end_col, group_name, color)
    COLUMN_GROUPS = [
        (0, 1, "Información", "#E0E0E0"),
        (2, 5, "Rendimiento", "#BBDEFB"),
        (6, 9, "Eficiencia Tiro", "#FFE0B2"),
        (10, 12, "Jugadas y Control", "#E1BEE7"),
        (13, 14, "Defensa", "#FFCDD2"),
        (15, 16, "Rebotes", "#C8E6C9")
    ]

    def __init__(self, team_stats: List[Dict], opponent_stats: Optional[List[Dict]] = None,
                 collection_name: Optional[str] = None, reload_callback: Optional[Callable] = None,
                 db_handler: Optional[Any] = None, parent: Optional[QWidget] = None):
        """
        Initialize the team stats window.

        Args:
            team_stats: List of team statistics dictionaries
            opponent_stats: List of opponent statistics dictionaries (optional)
            collection_name: Name of the collection for reloading data
            reload_callback: Callback function to reload data with date filter
            db_handler: Database handler for accessing MongoDB (optional)
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("MfA - Estadísticas de Equipo")
        # Set a reasonable minimum window size considering all columns and radio buttons
        self.setMinimumSize(1200, 700)

        # Set application icon
        set_app_icon(self)

        self.collection_name = collection_name
        self.reload_callback = reload_callback
        self.db_handler = db_handler
        self.opponent_stats = opponent_stats or []

        # Initialize helper classes
        self.trend_calculator = TrendCalculator()
        self.stats_calculator = StatsCalculator()
        self.stats_exporter = StatsExporter(self)
        self.table_manager = StatsTableManager(self.trend_calculator)

        # Initialize comparative mode manager if callback is available
        if self.reload_callback and self.collection_name:
            self.comparative_manager = ComparativeModeManager(self.reload_callback, self.collection_name)
        else:
            self.comparative_manager = None

        # List to store references to trend legend titles
        self.trend_legend_titles = []

        self.setup_ui(team_stats)

    def setup_ui(self, team_stats: List[Dict]):
        """Set up the UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create controls container
        controls_layout = QHBoxLayout()
        layout.addLayout(controls_layout)

        # Add period selector ComboBox
        period_label = QLabel("Período:")
        period_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        controls_layout.addWidget(period_label)

        self.period_combo = QComboBox()
        self.period_combo.addItem("General (toda la temporada)", "general")
        self.period_combo.addItem("Últimos 7 días vs resto", "comparative_7")
        self.period_combo.addItem("Últimos 15 días vs resto", "comparative_15")
        self.period_combo.addItem("Últimos 30 días vs resto", "comparative_30")
        self.period_combo.addItem("Últimos 60 días vs resto", "comparative_60")
        self.period_combo.addItem("Local vs Visitante", "venue_comparative")
        self.period_combo.addItem("Ganados vs Perdidos", "result_comparative")
        self.period_combo.addItem("Último Partido", "last_match")
        self.period_combo.setToolTip("Seleccionar período de estadísticas")
        self.period_combo.currentIndexChanged.connect(self._on_period_changed)
        controls_layout.addWidget(self.period_combo)

        controls_layout.addSpacing(20)

        # Add single export button with menu
        self.export_button = QPushButton("📤 Exportar")
        self.export_button.setToolTip("Exportar tabla actual en diferentes formatos")

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

        self.export_button.setMenu(export_menu)
        controls_layout.addWidget(self.export_button)

        # Add stretch to push controls to the left
        controls_layout.addStretch()

        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Create basic stats tab
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        self.basic_table = QTableWidget()
        basic_layout.addWidget(self.basic_table)

        # Add trend legend for basic stats (hidden by default)
        self.basic_trend_legend, basic_title = TrendLegendBuilder.create_legend(self.trend_calculator)
        self.trend_legend_titles.append(basic_title)
        self.basic_trend_legend.setVisible(False)
        basic_layout.addWidget(self.basic_trend_legend)

        self.tab_widget.addTab(basic_tab, "Estadísticas Básicas")

        # Create advanced stats tab
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout(advanced_tab)
        advanced_layout.setSpacing(5)
        advanced_layout.setContentsMargins(5, 5, 5, 5)

        # Add radio buttons if opponent stats are available
        if self.opponent_stats:
            radio_layout = QHBoxLayout()
            radio_layout.setSpacing(20)

            self.radio_group = QButtonGroup()

            self.teams_radio = QRadioButton("Equipos")
            self.teams_radio.setChecked(True)
            self.teams_radio.toggled.connect(self._on_view_mode_changed)
            self.radio_group.addButton(self.teams_radio)
            radio_layout.addWidget(self.teams_radio)

            self.opponents_radio = QRadioButton("Rivales")
            self.opponents_radio.toggled.connect(self._on_view_mode_changed)
            self.radio_group.addButton(self.opponents_radio)
            radio_layout.addWidget(self.opponents_radio)

            radio_layout.addStretch()
            advanced_layout.addLayout(radio_layout)

        # Create container for tables
        self.advanced_table = QTableWidget()
        advanced_layout.addWidget(self.advanced_table)

        # Create opponent table (hidden by default)
        if self.opponent_stats:
            self.opponent_table = QTableWidget()
            self.opponent_table.setVisible(False)
            advanced_layout.addWidget(self.opponent_table)
        else:
            self.opponent_table = None

        # Add color legend
        self.color_legend = self._create_color_legend()
        advanced_layout.addWidget(self.color_legend)

        # Add trend legend (hidden by default, shown in comparative mode)
        self.trend_legend, advanced_title = TrendLegendBuilder.create_legend(self.trend_calculator)
        self.trend_legend_titles.append(advanced_title)
        self.trend_legend.setVisible(False)
        advanced_layout.addWidget(self.trend_legend)

        self.tab_widget.addTab(advanced_tab, "Estadísticas Avanzadas")

        # Create IN/OUT team impact tab
        inout_tab = QWidget()
        inout_layout = QVBoxLayout(inout_tab)
        inout_layout.setSpacing(8)
        inout_layout.setContentsMargins(6, 6, 6, 6)

        # Controls: team selector and player selector
        selector_layout = QHBoxLayout()
        selector_layout.setSpacing(12)

        team_label = QLabel("Equipo:")
        team_label.setStyleSheet("font-weight: bold;")
        selector_layout.addWidget(team_label)

        self.inout_team_combo = QComboBox()
        # populate with teams from provided team_stats
        teams_list = [t.get('team_name') or t.get('name') for t in team_stats]
        seen = set()
        for name in teams_list:
            if name and name not in seen:
                seen.add(name)
                self.inout_team_combo.addItem(name)
        self.inout_team_combo.currentIndexChanged.connect(self._on_inout_team_changed)
        selector_layout.addWidget(self.inout_team_combo)

        player_label = QLabel("Jugador:")
        player_label.setStyleSheet("font-weight: bold;")
        selector_layout.addWidget(player_label)

        self.inout_player_combo = QComboBox()
        self.inout_player_combo.setToolTip("Seleccione jugador para análisis IN/OUT de equipo")
        self.inout_player_combo.setMaxVisibleItems(20)  # Enable scroll for long lists
        selector_layout.addWidget(self.inout_player_combo)

        # Second player selector for IN vs IN comparison
        player2_label = QLabel("Jugador 2:")
        player2_label.setStyleSheet("font-weight: bold;")
        selector_layout.addWidget(player2_label)

        self.inout_player2_combo = QComboBox()
        self.inout_player2_combo.setToolTip("Seleccione segundo jugador para comparar IN vs IN")
        self.inout_player2_combo.setMaxVisibleItems(20)  # Enable scroll for long lists
        selector_layout.addWidget(self.inout_player2_combo)

        self.inout_calc_button = QPushButton("Calcular IN/OUT")
        self.inout_calc_button.clicked.connect(self._on_inout_calculate)
        selector_layout.addWidget(self.inout_calc_button)

        self.inout_compare_button = QPushButton("Comparar IN vs IN")
        self.inout_compare_button.setToolTip("Comparar rendimiento del equipo cuando cada jugador está EN PISTA")
        self.inout_compare_button.clicked.connect(self._on_inout_compare_in)
        selector_layout.addWidget(self.inout_compare_button)

        selector_layout.addStretch()
        inout_layout.addLayout(selector_layout)

        # Result table: stat name | IN | OUT | Δ% (Min/J shown as a calculated row)
        self.inout_table = QTableWidget()
        self.inout_table.setColumnCount(4)
        self.inout_table.setHorizontalHeaderLabels(["Estadística", "IN (Equipo)", "OUT (Equipo)", "Δ %"])
        self.inout_table.setSortingEnabled(False)
        inout_layout.addWidget(self.inout_table)

        # Info label
        self.inout_info_label = QLabel("")
        inout_layout.addWidget(self.inout_info_label)

        self.tab_widget.addTab(inout_tab, "IN/OUT (Impacto en Equipo)")

        # Connect tab change event to adjust window size
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # Setup basic table
        self.basic_table.setColumnCount(len(BASIC_COLUMNS))
        self.basic_table.setHorizontalHeaderLabels(BASIC_COLUMNS)
        self.basic_table.setSortingEnabled(True)
        basic_header = self.basic_table.horizontalHeader()
        for i in range(len(BASIC_COLUMNS)):
            basic_header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        # Setup advanced table
        self.advanced_table.setColumnCount(len(ADVANCED_COLUMNS))
        self.advanced_table.setHorizontalHeaderLabels(ADVANCED_COLUMNS)
        self.advanced_table.setSortingEnabled(True)
        advanced_header = self.advanced_table.horizontalHeader()
        for i in range(len(ADVANCED_COLUMNS)):
            advanced_header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        # Setup opponent table if available
        if self.opponent_table:
            self.opponent_table.setColumnCount(len(ADVANCED_COLUMNS))
            self.opponent_table.setHorizontalHeaderLabels(ADVANCED_COLUMNS)
            self.opponent_table.setSortingEnabled(True)
            opponent_header = self.opponent_table.horizontalHeader()
            for i in range(len(ADVANCED_COLUMNS)):
                opponent_header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        # Apply colors to header based on column groups
        self._apply_header_colors()

        # Get numeric data and calculate quartiles
        basic_numeric_data = get_basic_numeric_data(team_stats)
        advanced_numeric_data = get_advanced_numeric_data(team_stats)

        basic_quartiles = {key: calculate_quartiles(values) for key, (values, _) in basic_numeric_data.items()}
        advanced_quartiles = {key: calculate_quartiles(values) for key, (values, _) in advanced_numeric_data.items()}

        # Get opponent numeric data and quartiles if available
        if self.opponent_stats:
            opponent_numeric_data = get_advanced_numeric_data(self.opponent_stats)
            opponent_quartiles = {key: calculate_quartiles(values) for key, (values, _) in opponent_numeric_data.items()}
        else:
            opponent_numeric_data = {}
            opponent_quartiles = {}

        # Populate tables
        self.basic_table.setRowCount(len(team_stats))
        self.advanced_table.setRowCount(len(team_stats))
        if self.opponent_table:
            self.opponent_table.setRowCount(len(self.opponent_stats))

        for row, team in enumerate(team_stats):
            # Populate basic stats table
            self.table_manager.populate_basic_stats_row(
                self.basic_table, row, team, basic_numeric_data, basic_quartiles
            )
            # Populate advanced stats table
            self.table_manager.populate_advanced_stats_row(
                self.advanced_table, row, team, advanced_numeric_data, advanced_quartiles
            )

        # Populate opponent stats table if available
        if self.opponent_table and self.opponent_stats:
            for row, opp_team in enumerate(self.opponent_stats):
                self.table_manager.populate_advanced_stats_row(
                    self.opponent_table, row, opp_team, opponent_numeric_data, opponent_quartiles
                )

        # Configure scrollbars for all tables
        tables_to_configure = [self.basic_table, self.advanced_table]
        if self.opponent_table:
            tables_to_configure.append(self.opponent_table)

        for table in tables_to_configure:
            table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Calculate and set window size
        self._set_window_size()

        # Initialize IN/OUT players list for first team (if any)
        if hasattr(self, 'inout_team_combo') and self.inout_team_combo.count() > 0:
            self._on_inout_team_changed()

    def _apply_header_colors(self):
        """Apply background colors to column headers based on their groups."""
        # Apply colors to header sections using class constant
        for start_col, end_col, _, color in self.COLUMN_GROUPS:
            for col in range(start_col, end_col + 1):
                self.advanced_table.horizontalHeaderItem(col).setBackground(QColor(color))
                # Also apply to opponent table if it exists
                if self.opponent_table:
                    self.opponent_table.horizontalHeaderItem(col).setBackground(QColor(color))

    def _create_color_legend(self) -> QWidget:
        """Create a color legend widget to identify column groups."""
        from PyQt6.QtWidgets import QFrame, QLabel, QHBoxLayout

        legend_frame = QFrame()
        legend_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        legend_frame.setMaximumHeight(40)

        legend_layout = QHBoxLayout(legend_frame)
        legend_layout.setContentsMargins(10, 5, 10, 5)
        legend_layout.setSpacing(15)

        # Add legend title
        title_label = QLabel("Leyenda:")
        title_label.setStyleSheet("font-weight: bold;")
        legend_layout.addWidget(title_label)

        # Create legend items using class constant
        for _, _, group_name, color in self.COLUMN_GROUPS:
            # Create container for each legend item
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(5)

            # Create color box
            color_box = QLabel()
            color_box.setFixedSize(20, 20)
            color_box.setStyleSheet(f"background-color: {color}; border: 1px solid #999;")
            item_layout.addWidget(color_box)

            # Create text label
            text_label = QLabel(group_name)
            text_label.setStyleSheet("font-size: 9pt;")
            item_layout.addWidget(text_label)

            legend_layout.addWidget(item_widget)

        # Add stretch to push items to the left
        legend_layout.addStretch()

        return legend_frame

    def _get_current_table(self) -> QTableWidget:
        """Get the currently active table based on selected tab and view mode."""
        current_index = self.tab_widget.currentIndex()
        if current_index == 0:
            return self.basic_table
        elif current_index == 1:
            # In advanced tab, check which radio button is selected
            if self.opponent_table and hasattr(self, 'opponents_radio') and self.opponents_radio.isChecked():
                return self.opponent_table
            return self.advanced_table
        # If IN/OUT tab (added as third tab) is selected, return the inout table
        if hasattr(self, 'inout_table') and current_index == 2:
            return self.inout_table
        return self.advanced_table  # fallback

    def _get_current_table_name(self) -> str:
        """Get the name of the currently active table."""
        current_index = self.tab_widget.currentIndex()
        if current_index == 0:
            return "estadisticas_basicas"
        elif current_index == 1:
            # In advanced tab, check which radio button is selected
            if self.opponent_table and hasattr(self, 'opponents_radio') and self.opponents_radio.isChecked():
                return "estadisticas_rivales"
            return "estadisticas_avanzadas"
        # If IN/OUT tab is active, use a distinct name
        if current_index == 2 and hasattr(self, 'inout_table'):
            return "inout_comparison"
        return "estadisticas_avanzadas"  # fallback

    def _export_csv(self):
        """Export current table to CSV format."""
        table = self._get_current_table()
        table_name = self._get_current_table_name()
        subtitle = ""
        # If exporting IN/OUT tab, include selected team and player(s) names in subtitle
        if self.tab_widget.currentIndex() == 2 and hasattr(self, 'inout_table'):
            try:
                team_name = self.inout_team_combo.currentText() if hasattr(self, 'inout_team_combo') else ''
            except Exception:
                team_name = ''
            names = []
            try:
                p1 = self.inout_player_combo.currentText() if hasattr(self, 'inout_player_combo') else ''
                p2 = self.inout_player2_combo.currentText() if hasattr(self, 'inout_player2_combo') else ''
                if p1:
                    names.append(p1)
                if p2 and p2 != p1:
                    names.append(p2)
            except Exception:
                pass

            if team_name and names:
                subtitle = f"{team_name} - {', '.join(names)}"
            elif team_name:
                subtitle = team_name
            else:
                subtitle = ", ".join(names)

            if subtitle:
                table_name = f"{table_name}_{subtitle.replace(' ', '_')[:40]}"

        self.stats_exporter.export_to_csv(table, table_name, subtitle)

    def _export_png(self):
        """Export current table to PNG image."""
        table = self._get_current_table()
        table_name = self._get_current_table_name()
        subtitle = ""
        if self.tab_widget.currentIndex() == 2 and hasattr(self, 'inout_table'):
            try:
                team_name = self.inout_team_combo.currentText() if hasattr(self, 'inout_team_combo') else ''
            except Exception:
                team_name = ''
            names = []
            try:
                p1 = self.inout_player_combo.currentText() if hasattr(self, 'inout_player_combo') else ''
                p2 = self.inout_player2_combo.currentText() if hasattr(self, 'inout_player2_combo') else ''
                if p1:
                    names.append(p1)
                if p2 and p2 != p1:
                    names.append(p2)
            except Exception:
                pass

            if team_name and names:
                subtitle = f"{team_name} - {', '.join(names)}"
            elif team_name:
                subtitle = team_name
            else:
                subtitle = ", ".join(names)

            if subtitle:
                table_name = f"{table_name}_{subtitle.replace(' ', '_')[:40]}"

        self.stats_exporter.export_to_png(table, table_name, subtitle)

    def _export_pdf(self):
        """Export current table to PDF format."""
        table = self._get_current_table()
        table_name = self._get_current_table_name()
        window_title = self.windowTitle()
        subtitle = ""
        if self.tab_widget.currentIndex() == 2 and hasattr(self, 'inout_table'):
            try:
                team_name = self.inout_team_combo.currentText() if hasattr(self, 'inout_team_combo') else ''
            except Exception:
                team_name = ''
            names = []
            try:
                p1 = self.inout_player_combo.currentText() if hasattr(self, 'inout_player_combo') else ''
                p2 = self.inout_player2_combo.currentText() if hasattr(self, 'inout_player2_combo') else ''
                if p1:
                    names.append(p1)
                if p2 and p2 != p1:
                    names.append(p2)
            except Exception:
                pass

            if team_name and names:
                subtitle = f"{team_name} - {', '.join(names)}"
            elif team_name:
                subtitle = team_name
            else:
                subtitle = ", ".join(names)

            if subtitle:
                table_name = f"{table_name}_{subtitle.replace(' ', '_')[:40]}"

        self.stats_exporter.export_to_pdf(table, table_name, window_title, subtitle)

    def _on_view_mode_changed(self):
        """Handle view mode change between Teams and Opponents."""
        if not self.opponent_table:
            return

        # Toggle visibility of tables
        is_opponent_view = self.opponents_radio.isChecked()
        self.advanced_table.setVisible(not is_opponent_view)
        self.opponent_table.setVisible(is_opponent_view)

    def _on_inout_team_changed(self):
        """Load player list for selected team into player combo."""
        team_name = self.inout_team_combo.currentText()
        self.inout_player_combo.clear()
        if hasattr(self, 'inout_player2_combo'):
            self.inout_player2_combo.clear()

        if not self.db_handler or not self.collection_name or not team_name:
            return

        try:
            # Find a recent match where this team appears and extract players
            collection = None
            if hasattr(self.db_handler, 'connection'):
                collection = self.db_handler.connection.get_collection(self.collection_name)
            elif hasattr(self.db_handler, 'db'):
                collection = self.db_handler.db[self.collection_name]

            if collection is None:
                return

            # Detect if this is a FBCYL collection
            is_fbcyl = self.collection_name.startswith('FBCYL_')

            players = []
            # Use dict to track unique players
            # For FBCYL: actorId changes per game, so group by NAME and use most recent ID
            players_dict = {}

            if is_fbcyl:
                # FBCYL structure: stats.teams[].players[]
                # Find ALL games with this team to get complete roster
                docs = collection.find({
                    "stats.teams.name": team_name
                })

                for doc in docs:
                    if doc and 'stats' in doc and 'teams' in doc['stats']:
                        for team in doc['stats']['teams']:
                            if team.get('name') == team_name and 'players' in team:
                                for p in team.get('players', []):
                                    name = p.get('name')
                                    # FBCYL: Use UUID (stable) not actorId (changes per game)
                                    uuid = p.get('uuid')
                                    if name:
                                        # Normalize name by extracting first initial + surnames
                                        words = name.split()
                                        if len(words) >= 3:
                                            # First initial + two surnames
                                            normalized_name = f"{words[0][0]} {words[-2]} {words[-1]}"
                                        elif len(words) >= 2:
                                            # First initial + one surname
                                            normalized_name = f"{words[0][0]} {words[-1]}"
                                        else:
                                            normalized_name = name

                                        # Use normalized name as key, prefer UUID if available
                                        if normalized_name not in players_dict:
                                            # Use UUID if available, otherwise use normalized surnames as ID
                                            identifier = uuid if uuid else normalized_name
                                            players_dict[normalized_name] = {
                                                'display_name': name,  # Keep full name for display
                                                'uuid': identifier
                                            }
                                        else:
                                            # If we already have this player and now find a UUID, update it
                                            existing_id = players_dict[normalized_name]['uuid']
                                            # Prefer UUID over normalized name
                                            if uuid and (existing_id == normalized_name or not existing_id):
                                                players_dict[normalized_name]['uuid'] = uuid
                                        # Always use the longest/most complete name for display
                                        if len(name) > len(players_dict[normalized_name]['display_name']):
                                            players_dict[normalized_name]['display_name'] = name
                                break

                # Convert dict to list (display name is shown, uuid is stored)
                players = [(data['display_name'], data['uuid']) for data in players_dict.values()]
            else:
                # FEB structure: BOXSCORE.TEAM[].PLAYER[]
                # Find ALL games with this team to get complete roster
                docs = collection.find({
                    "$or": [
                        {"BOXSCORE.TEAM.TOTAL.name": team_name},
                        {"HEADER.TEAM.name": team_name}
                    ]
                })

                for doc in docs:
                    if doc and 'BOXSCORE' in doc and 'TEAM' in doc['BOXSCORE']:
                        for team in doc['BOXSCORE']['TEAM']:
                            total = team.get('TOTAL') if isinstance(team.get('TOTAL'), dict) else team
                            if total.get('name') == team_name and 'PLAYER' in team:
                                for p in team.get('PLAYER', []):
                                    name = p.get('name')
                                    pid = p.get('id')
                                    if name and pid:
                                        # Store unique players by ID
                                        players_dict[pid] = name
                                break

                # Convert dict to list
                players = [(name, pid) for pid, name in players_dict.items()]

            # Sort alphabetically by player name
            players.sort(key=lambda x: x[0])

            # Populate combo
            for name, pid in players:
                self.inout_player_combo.addItem(name, pid)
                if hasattr(self, 'inout_player2_combo'):
                    self.inout_player2_combo.addItem(name, pid)

        except Exception:
            return

    def _on_inout_calculate(self):
        """Calculate IN/OUT team advanced stats for selected player."""
        team_name = self.inout_team_combo.currentText()
        player_index = self.inout_player_combo.currentIndex()
        if player_index < 0:
            QMessageBox.warning(self, "Selecciona jugador", "Seleccione un jugador válido para calcular IN/OUT")
            return

        player_id = self.inout_player_combo.currentData()
        if not player_id:
            QMessageBox.warning(self, "Selecciona jugador", "Jugador sin id disponible")
            return

        if not self.db_handler or not self.collection_name:
            QMessageBox.warning(self, "Error", "Se requiere conexión a la base de datos para calcular IN/OUT")
            return

        # Fetch IN/OUT aggregated stats from repository
        try:
            # Create progress dialog with indeterminate progress for loading
            progress = QProgressDialog("Cargando partidos desde base de datos...", None, 0, 0, self)
            progress.setWindowTitle("Calculando IN/OUT")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setCancelButton(None)  # No cancel button during loading
            progress.show()
            QApplication.processEvents()

            def update_progress(current, total):
                if current == 1 and total > 1:
                    # Just finished loading, switch to determinate progress
                    progress.setMaximum(100)
                    progress.setLabelText(f"Analizando partidos... (0/{total})")
                    progress.setValue(0)
                elif total > 1:
                    # Processing games
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

        # Delegate display to helper
        try:
            self._display_inout_stats(inout, team_name)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al mostrar datos IN/OUT: {e}")
        return

    def _display_inout_stats(self, inout: Dict, team_name: str):
        """Display IN/OUT aggregated stats (shared by DB and file-based reports)."""
        stats_in = inout['in']
        stats_out = inout['out']

        # Reset table headers for IN/OUT view
        self.inout_table.setHorizontalHeaderLabels(["Estadística", "IN (Equipo)", "OUT (Equipo)", "Δ %"])

        # Convert aggregated stats to team_data/opponent_data structures expected by StatsCalculator
        def build_team_dict(s):
            return {
                'name': team_name,
                'pts': int(s.get('points_for', 0)),
                'p2m': int(s.get('fgm_2', 0)),
                'p2a': int(s.get('fga_2', 0)),
                'p3m': int(s.get('fgm_3', 0)),
                'p3a': int(s.get('fga_3', 0)),
                'p1m': int(s.get('ftm', 0)),
                'p1a': int(s.get('fta', 0)),
                'ro': int(s.get('orb', 0)),
                'rd': int(s.get('drb', 0)),
                'assist': int(s.get('ast', 0)),
                'st': int(s.get('stl', 0)),
                'to': int(s.get('tov', 0)),
                'bs': int(s.get('blk', 0))
            }

        def build_opp_dict(s):
            return {
                'name': 'OPP',
                'pts': int(s.get('points_against', 0)),
                'p2m': int(s.get('opp_fgm_2', 0)),
                'p2a': int(s.get('opp_fga_2', 0)),
                'p3m': int(s.get('opp_fgm_3', 0)),
                'p3a': int(s.get('opp_fga_3', 0)),
                'p1m': int(s.get('opp_ftm', 0)),
                'p1a': int(s.get('opp_fta', 0)),
                'ro': int(s.get('opp_orb', 0)),
                'rd': int(s.get('opp_drb', 0)),
                'assist': int(s.get('opp_ast', 0)),
                'st': int(s.get('opp_stl', 0)),
                'to': int(s.get('opp_tov', 0)),
                'bs': int(s.get('opp_blk', 0))
            }

        team_in = build_team_dict(stats_in)
        opp_in = build_opp_dict(stats_in)
        team_out = build_team_dict(stats_out)
        opp_out = build_opp_dict(stats_out)

        # Minutes totals (aggregated across games) for normalization
        minutes_in = float(stats_in.get('minutes', 0))
        minutes_out = float(stats_out.get('minutes', 0))

        # Calculate advanced metrics
        adv_in = self.stats_calculator.calculate_single_match_stats(team_in, opp_in)
        adv_out = self.stats_calculator.calculate_single_match_stats(team_out, opp_out)

        # Normalize possessions to 40 minutes (if minutes available)
        try:
            poss_in = float(adv_in.get('possessions_per_game', 0))
        except Exception:
            poss_in = 0.0
        try:
            poss_out = float(adv_out.get('possessions_per_game', 0))
        except Exception:
            poss_out = 0.0

        if minutes_in > 0:
            adv_in['possessions_per_40'] = poss_in * (40.0 / minutes_in)
        else:
            # Fallback to per-game poss if no minutes info
            adv_in['possessions_per_40'] = poss_in

        if minutes_out > 0:
            adv_out['possessions_per_40'] = poss_out * (40.0 / minutes_out)
        else:
            adv_out['possessions_per_40'] = poss_out

        # Define display fields
        # Show Possessions normalized to 40 minutes first, remove raw points
        display_fields = [
            ("possessions_per_40", "Poss/40"),
            ("offensive_rating", "ORtg"),
            ("defensive_rating", "DRtg"),
            ("net_rating", "Net"),
            ("efg_percentage", "eFG%"),
            ("true_shooting", "TS%"),
            ("three_point_rate", "3Pr"),
            ("free_throw_rate", "FTr"),
            ("assist_rate", "%AST"),
            ("turnover_rate", "%TO"),
            ("offensive_rebound_rate", "OR%"),
            ("defensive_rebound_rate", "DR%")
        ]

        # We'll show minutes per game as the first calculated row
        display_rows = [("minutes", "Min/J")] + display_fields

        # Populate table
        self.inout_table.setRowCount(len(display_rows))
        # Fields where lower values are better (so improvement is a decrease)
        lower_is_better = {"defensive_rating", "turnover_rate", "points_against_per_game"}

        # Minutes per game for IN / OUT
        games_in = int(stats_in.get('games', inout.get('games_analyzed', 1)))
        games_out = int(stats_out.get('games', inout.get('games_analyzed', 1)))
        minutes_total_in = float(stats_in.get('minutes', 0))
        minutes_total_out = float(stats_out.get('minutes', 0))
        minutes_per_game_in = minutes_total_in / games_in if games_in > 0 else 0.0
        minutes_per_game_out = minutes_total_out / games_out if games_out > 0 else 0.0

        for row, (key, label) in enumerate(display_rows):
            self.inout_table.setItem(row, 0, QTableWidgetItem(label))

            # Minutes row is handled specially
            if key == "minutes":
                in_text = f"{minutes_per_game_in:.1f}"
                out_text = f"{minutes_per_game_out:.1f}"
                in_item = QTableWidgetItem(in_text)
                out_item = QTableWidgetItem(out_text)
                self.inout_table.setItem(row, 1, in_item)
                self.inout_table.setItem(row, 2, out_item)

                # Delta percent relative to OUT for minutes
                try:
                    base = float(minutes_per_game_out)
                    if base != 0:
                        delta = ((float(minutes_per_game_in) - base) / abs(base)) * 100
                        delta_text = f"{delta:.1f}%"
                    else:
                        delta_text = "N/A"
                except Exception:
                    delta_text = "N/A"

                delta_item = QTableWidgetItem(delta_text)
                self.inout_table.setItem(row, 3, delta_item)
                # Color the minutes row: higher minutes considered better
                try:
                    num_in_m = float(minutes_per_game_in)
                    num_out_m = float(minutes_per_game_out)
                    green = QColor(200, 255, 200)
                    red = QColor(255, 200, 200)
                    if num_in_m == num_out_m:
                        pass
                    elif num_in_m > num_out_m:
                        in_item.setBackground(green)
                        out_item.setBackground(QColor(240, 255, 240))
                        delta_item.setBackground(QColor(200, 255, 200))
                    else:
                        in_item.setBackground(red)
                        out_item.setBackground(QColor(255, 240, 240))
                        delta_item.setBackground(QColor(255, 200, 200))
                except Exception:
                    pass

                continue

            val_in = adv_in.get(key, 0)
            val_out = adv_out.get(key, 0)

            # Format as percentage for pct fields
            in_text = f"{val_in:.2f}" if isinstance(val_in, float) else str(val_in)
            out_text = f"{val_out:.2f}" if isinstance(val_out, float) else str(val_out)

            in_item = QTableWidgetItem(in_text)
            out_item = QTableWidgetItem(out_text)

            self.inout_table.setItem(row, 1, in_item)
            self.inout_table.setItem(row, 2, out_item)

            # Delta percent relative to OUT
            try:
                base = float(val_out) if val_out is not None else 0
                if base != 0:
                    delta = ((float(val_in) - base) / abs(base)) * 100
                    delta_text = f"{delta:.1f}%"
                else:
                    delta_text = "N/A"
            except Exception:
                delta_text = "N/A"

            delta_item = QTableWidgetItem(delta_text)
            self.inout_table.setItem(row, 3, delta_item)

            # Apply coloring: green if IN is better than OUT, red otherwise
            try:
                num_in = float(val_in)
                num_out = float(val_out)
                improved = False
                if key in lower_is_better:
                    # lower is better -> improvement when IN < OUT
                    improved = num_in < num_out
                else:
                    improved = num_in > num_out

                green = QColor(200, 255, 200)
                red = QColor(255, 200, 200)
                if num_in == num_out:
                    # no color when equal
                    pass
                elif improved:
                    in_item.setBackground(green)
                    out_item.setBackground(QColor(240, 255, 240))
                    # color delta cell as improvement (green)
                    delta_item.setBackground(QColor(200, 255, 200))
                else:
                    in_item.setBackground(red)
                    out_item.setBackground(QColor(255, 240, 240))
                    # color delta cell as worsening (red)
                    delta_item.setBackground(QColor(255, 200, 200))
            except Exception:
                pass

        self.inout_info_label.setText(f"Jugadores analizados (partidos): {inout.get('games_analyzed', 0)}")

        # Adjust window size for the new view
        QTimer.singleShot(50, self._adjust_window_size_for_current_tab)

    def _on_inout_compare_in(self):
        """Compare IN stats for two selected players (IN vs IN)."""
        team_name = self.inout_team_combo.currentText()
        idx1 = self.inout_player_combo.currentIndex()
        idx2 = self.inout_player2_combo.currentIndex() if hasattr(self, 'inout_player2_combo') else -1
        if idx1 < 0 or idx2 < 0:
            QMessageBox.warning(self, "Selecciona jugadores", "Seleccione dos jugadores válidos para comparar")
            return

        player1_id = self.inout_player_combo.currentData()
        player2_id = self.inout_player2_combo.currentData()
        player1_name = self.inout_player_combo.currentText()
        player2_name = self.inout_player2_combo.currentText()

        if not player1_id or not player2_id:
            QMessageBox.warning(self, "Selecciona jugadores", "Uno de los jugadores no tiene id disponible")
            return

        if not self.db_handler or not self.collection_name:
            QMessageBox.warning(self, "Error", "Se requiere conexión a la base de datos para calcular IN/IN")
            return

        try:
            # Create progress dialog with indeterminate progress for loading
            progress = QProgressDialog("Cargando partidos desde base de datos...", None, 0, 0, self)
            progress.setWindowTitle("Calculando IN/IN")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setCancelButton(None)
            progress.show()
            QApplication.processEvents()

            player1_loaded = False

            def update_progress_p1(current, total):
                nonlocal player1_loaded
                if current == 1 and total > 1 and not player1_loaded:
                    # Just finished loading player 1, switch to determinate
                    progress.setMaximum(100)
                    progress.setLabelText(f"Analizando {player1_name}... (0/{total})")
                    progress.setValue(0)
                    player1_loaded = True
                elif total > 1:
                    # Processing games for player 1 (0-50%)
                    percent = int(current * 50 / total)
                    progress.setValue(percent)
                    progress.setLabelText(f"Analizando {player1_name}... ({current}/{total})")
                QApplication.processEvents()

            inout1 = self.db_handler.get_player_in_out_stats(
                self.collection_name, player1_id, date_filter=None,
                debug=False, progress_callback=update_progress_p1
            )

            # Switch to loading player 2
            progress.setMaximum(0)  # Indeterminate again
            progress.setLabelText(f"Cargando partidos de {player2_name}...")
            QApplication.processEvents()

            def update_progress_p2(current, total):
                if current == 1 and total > 1:
                    # Just finished loading player 2
                    progress.setMaximum(100)
                    progress.setLabelText(f"Analizando {player2_name}... (0/{total})")
                    progress.setValue(50)
                elif total > 1:
                    # Processing games for player 2 (50-100%)
                    percent = 50 + int(current * 50 / total)
                    progress.setValue(percent)
                    progress.setLabelText(f"Analizando {player2_name}... ({current}/{total})")
                QApplication.processEvents()

            inout2 = self.db_handler.get_player_in_out_stats(
                self.collection_name, player2_id, date_filter=None,
                debug=False, progress_callback=update_progress_p2
            )
            progress.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al obtener datos IN/OUT: {e}")
            return

        if not inout1 or 'in' not in inout1 or not inout2 or 'in' not in inout2:
            QMessageBox.warning(self, "Sin datos", "No hay datos IN para uno o ambos jugadores")
            return

        stats1 = inout1['in']
        stats2 = inout2['in']

        def build_team_dict_from_in(s, name):
            return {
                'name': name,
                'pts': int(s.get('points_for', 0)),
                'p2m': int(s.get('fgm_2', 0)),
                'p2a': int(s.get('fga_2', 0)),
                'p3m': int(s.get('fgm_3', 0)),
                'p3a': int(s.get('fga_3', 0)),
                'p1m': int(s.get('ftm', 0)),
                'p1a': int(s.get('fta', 0)),
                'ro': int(s.get('orb', 0)),
                'rd': int(s.get('drb', 0)),
                'assist': int(s.get('ast', 0)),
                'st': int(s.get('stl', 0)),
                'to': int(s.get('tov', 0)),
                'bs': int(s.get('blk', 0))
            }

        def build_opp_from_in(s):
            return {
                'name': 'OPP',
                'pts': int(s.get('points_against', 0)),
                'p2m': int(s.get('opp_fgm_2', 0)),
                'p2a': int(s.get('opp_fga_2', 0)),
                'p3m': int(s.get('opp_fgm_3', 0)),
                'p3a': int(s.get('opp_fga_3', 0)),
                'p1m': int(s.get('opp_ftm', 0)),
                'p1a': int(s.get('opp_fta', 0)),
                'ro': int(s.get('opp_orb', 0)),
                'rd': int(s.get('opp_drb', 0)),
                'assist': int(s.get('opp_ast', 0)),
                'st': int(s.get('opp_stl', 0)),
                'to': int(s.get('opp_tov', 0)),
                'bs': int(s.get('opp_blk', 0))
            }

        team1 = build_team_dict_from_in(stats1, player1_name)
        opp1 = build_opp_from_in(stats1)
        team2 = build_team_dict_from_in(stats2, player2_name)
        opp2 = build_opp_from_in(stats2)

        minutes1 = float(stats1.get('minutes', 0))
        minutes2 = float(stats2.get('minutes', 0))

        adv1 = self.stats_calculator.calculate_single_match_stats(team1, opp1)
        adv2 = self.stats_calculator.calculate_single_match_stats(team2, opp2)

        # Normalize possessions to Poss/40
        poss1 = float(adv1.get('possessions_per_game', 0))
        poss2 = float(adv2.get('possessions_per_game', 0))
        adv1['possessions_per_40'] = poss1 * (40.0 / minutes1) if minutes1 > 0 else poss1
        adv2['possessions_per_40'] = poss2 * (40.0 / minutes2) if minutes2 > 0 else poss2

        # Display fields (same as IN/OUT view)
        display_fields = [
            ("possessions_per_40", "Poss/40"),
            ("offensive_rating", "ORtg"),
            ("defensive_rating", "DRtg"),
            ("net_rating", "Net"),
            ("efg_percentage", "eFG%"),
            ("true_shooting", "TS%"),
            ("three_point_rate", "3Pr"),
            ("free_throw_rate", "FTr"),
            ("assist_rate", "%AST"),
            ("turnover_rate", "%TO"),
            ("offensive_rebound_rate", "OR%"),
            ("defensive_rebound_rate", "DR%")
        ]

        # Include minutes per game as a top row
        display_rows = [("minutes", "Min/J")] + display_fields
        self.inout_table.setRowCount(len(display_rows))
        # Update headers to identify each player
        self.inout_table.setHorizontalHeaderLabels(["Estadística", f"{player1_name} IN", f"{player2_name} IN", "Δ %"])

        lower_is_better = {"defensive_rating", "turnover_rate", "points_against_per_game"}

        # Compute minutes per game for each player's IN minutes
        games1 = int(stats1.get('games', inout1.get('games_analyzed', 1)))
        games2 = int(stats2.get('games', inout2.get('games_analyzed', 1)))
        minutes_total1 = float(stats1.get('minutes', 0))
        minutes_total2 = float(stats2.get('minutes', 0))
        minutes_per_game1 = minutes_total1 / games1 if games1 > 0 else 0.0
        minutes_per_game2 = minutes_total2 / games2 if games2 > 0 else 0.0

        for row, (key, label) in enumerate(display_rows):
            self.inout_table.setItem(row, 0, QTableWidgetItem(label))

            # Minutes row
            if key == "minutes":
                t1 = f"{minutes_per_game1:.1f}"
                t2 = f"{minutes_per_game2:.1f}"
                item1 = QTableWidgetItem(t1)
                item2 = QTableWidgetItem(t2)
                self.inout_table.setItem(row, 1, item1)
                self.inout_table.setItem(row, 2, item2)

                try:
                    base = float(minutes_per_game2)
                    if base != 0:
                        delta = ((float(minutes_per_game1) - base) / abs(base)) * 100
                        delta_text = f"{delta:.1f}%"
                    else:
                        delta_text = "N/A"
                except Exception:
                    delta_text = "N/A"

                delta_item = QTableWidgetItem(delta_text)
                self.inout_table.setItem(row, 3, delta_item)
                # Color the minutes row: more minutes is considered better
                try:
                    num1_m = float(minutes_per_game1)
                    num2_m = float(minutes_per_game2)
                    green = QColor(200, 255, 200)
                    red = QColor(255, 200, 200)
                    if num1_m == num2_m:
                        pass
                    elif num1_m > num2_m:
                        item1.setBackground(green)
                        item2.setBackground(QColor(240, 255, 240))
                        delta_item.setBackground(QColor(200, 255, 200))
                    else:
                        item1.setBackground(red)
                        item2.setBackground(QColor(255, 240, 240))
                        delta_item.setBackground(QColor(255, 200, 200))
                except Exception:
                    pass

                continue

            v1 = adv1.get(key, 0)
            v2 = adv2.get(key, 0)

            t1 = f"{v1:.2f}" if isinstance(v1, float) else str(v1)
            t2 = f"{v2:.2f}" if isinstance(v2, float) else str(v2)

            item1 = QTableWidgetItem(t1)
            item2 = QTableWidgetItem(t2)
            self.inout_table.setItem(row, 1, item1)
            self.inout_table.setItem(row, 2, item2)

            try:
                base = float(v2) if v2 is not None else 0
                if base != 0:
                    delta = ((float(v1) - base) / abs(base)) * 100
                    delta_text = f"{delta:.1f}%"
                else:
                    delta_text = "N/A"
            except Exception:
                delta_text = "N/A"

            delta_item = QTableWidgetItem(delta_text)
            self.inout_table.setItem(row, 3, delta_item)

            try:
                num1 = float(v1)
                num2 = float(v2)
                if key in lower_is_better:
                    improved = num1 < num2
                else:
                    improved = num1 > num2

                green = QColor(200, 255, 200)
                red = QColor(255, 200, 200)
                if num1 == num2:
                    pass
                elif improved:
                    item1.setBackground(green)
                    item2.setBackground(QColor(240, 255, 240))
                    delta_item.setBackground(QColor(200, 255, 200))
                else:
                    item1.setBackground(red)
                    item2.setBackground(QColor(255, 240, 240))
                    delta_item.setBackground(QColor(255, 200, 200))
            except Exception:
                pass

        # Info label: show games analyzed for both players
        games1 = inout1.get('games_analyzed', 0)
        games2 = inout2.get('games_analyzed', 0)
        self.inout_info_label.setText(f"Partidos analizados: {player1_name}={games1}, {player2_name}={games2}")

        QTimer.singleShot(50, self._adjust_window_size_for_current_tab)

        # Ensure headers show player labels are reset after calculation
        self.inout_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.inout_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.inout_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.inout_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

    def _on_tab_changed(self, index: int):
        """
        Handle tab change event to adjust window size.

        Args:
            index: Index of the newly selected tab
        """
        # Use QTimer to delay resize until the tab is fully rendered
        QTimer.singleShot(50, self._adjust_window_size_for_current_tab)

    def _adjust_window_size_for_current_tab(self):
        """Adjust window size based on the currently active tab and view mode."""
        current_index = self.tab_widget.currentIndex()

        # Select the appropriate table
        if current_index == 0:
            active_table = self.basic_table
        else:
            # In advanced tab, use the currently visible table
            active_table = self._get_current_table()

        self._resize_to_fit_table(active_table)

    def _resize_to_fit_table(self, table: QTableWidget):
        """
        Resize window to fit the given table optimally.

        Args:
            table: QTableWidget to fit
        """
        # Force table to update its geometry
        table.updateGeometry()
        self.tab_widget.updateGeometry()
        self.centralWidget().updateGeometry()

        # Process pending events to ensure geometry is calculated
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        # Get screen dimensions
        screen = self.screen().availableGeometry()
        screen_width = screen.width()
        screen_height = screen.height()

        # Calculate margins and padding
        TAB_HEIGHT = 45  # Height of tab bar
        VERTICAL_MARGIN = 30  # Top and bottom margins
        HORIZONTAL_MARGIN = 50  # Left and right margins (increased for safety)
        SCROLLBAR_SIZE = 25  # Scrollbar size

        # Get the actual frame decorations size
        frame_width = self.frameGeometry().width() - self.geometry().width()
        frame_height = self.frameGeometry().height() - self.geometry().height()

        # If frame sizes aren't available yet (first time), use defaults
        if frame_width <= 0:
            frame_width = 16  # Default window border width
        if frame_height <= 0:
            frame_height = 39  # Default title bar + border height

        # Calculate content width (all columns)
        content_width = table.horizontalHeader().length()

        # Calculate content height (all rows + header)
        header_height = table.horizontalHeader().height()
        rows_height = table.verticalHeader().length()
        content_height = header_height + rows_height

        # Calculate required window size including all decorations
        # Always add scrollbar width since vertical scrollbar is often visible
        required_width = content_width + HORIZONTAL_MARGIN + frame_width + SCROLLBAR_SIZE
        required_height = content_height + TAB_HEIGHT + VERTICAL_MARGIN + frame_height

        # Check if we need scrollbars and adjust accordingly
        needs_horizontal_scroll = required_width > screen_width * 0.95
        needs_vertical_scroll = required_height > screen_height * 0.9

        if needs_horizontal_scroll:
            required_width = int(screen_width * 0.95)
            required_height += SCROLLBAR_SIZE  # Add space for horizontal scrollbar

        if needs_vertical_scroll:
            required_height = int(screen_height * 0.9)
            required_width += SCROLLBAR_SIZE  # Add space for vertical scrollbar

        # Ensure minimum size
        required_width = max(required_width, self.minimumWidth())
        required_height = max(required_height, self.minimumHeight())

        # Apply the new size
        self.resize(required_width, required_height)

        # Center the window on screen
        self._center_on_screen()

    def _center_on_screen(self):
        """Center the window on the screen."""
        screen = self.screen().availableGeometry()
        window_geometry = self.frameGeometry()

        center_point = screen.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

    def _set_window_size(self):
        """Calculate and set the window size based on table content."""
        # Force tables to update their geometry
        self.basic_table.updateGeometry()
        self.advanced_table.updateGeometry()
        if self.opponent_table:
            self.opponent_table.updateGeometry()

        # Use QTimer to ensure tables are fully rendered before resizing
        QTimer.singleShot(100, self._adjust_window_size_for_current_tab)

    def invalidate_cache(self):
        """Clear all cached data to force reload on next period change."""
        if self.comparative_manager:
            self.comparative_manager.invalidate_cache()

    def _on_period_changed(self, index: int):
        """Handle period selection change."""
        if not self.comparative_manager:
            QMessageBox.warning(self, "Error", "No se puede recargar datos sin callback o nombre de colección")
            return

        period_type = self.period_combo.itemData(index)

        try:
            if period_type and period_type.startswith("comparative"):
                # Extract days from period type
                days = ComparativeModeManager.extract_days_from_period_type(period_type)

                # Load comparative data using manager
                result = self.comparative_manager.load_comparative_period(period_type, days, self)

                if result[0] is None or result[1] is None:
                    return

                # Unpack results (handles both tuples of data or tuples of (team_stats, opponent_stats))
                if len(result[0]) == 2 and isinstance(result[0], tuple):
                    recent_team_stats, recent_opponent_stats = result[0]
                    rest_team_stats, rest_opponent_stats = result[1]
                else:
                    recent_team_stats = result[0]
                    recent_opponent_stats = []
                    rest_team_stats = result[1]
                    rest_opponent_stats = []

                comparison_label = result[2]

                # Update stored data with recent stats
                self.opponent_stats = recent_opponent_stats or []

                # Update legend title
                TrendLegendBuilder.update_legend_titles(self.trend_legend_titles, comparison_label)

                # Show comparative tables
                self._show_comparative_tables(recent_team_stats, rest_team_stats,
                                             recent_opponent_stats, rest_opponent_stats)

            elif period_type == "venue_comparative":
                # Load venue comparison data using manager
                result = self.comparative_manager.load_venue_comparison(self)

                if result[0] is None or result[1] is None:
                    return

                # Unpack results
                if len(result[0]) == 2 and isinstance(result[0], tuple):
                    home_team_stats, home_opponent_stats = result[0]
                    away_team_stats, away_opponent_stats = result[1]
                else:
                    home_team_stats = result[0]
                    home_opponent_stats = []
                    away_team_stats = result[1]
                    away_opponent_stats = []

                comparison_label = result[2]

                # Update stored data with home stats
                self.opponent_stats = home_opponent_stats or []

                # Update legend title
                TrendLegendBuilder.update_legend_titles(self.trend_legend_titles, comparison_label)

                # Show comparative tables
                self._show_comparative_tables(home_team_stats, away_team_stats,
                                             home_opponent_stats, away_opponent_stats)

            elif period_type == "result_comparative":
                # Load result comparison data using manager
                result = self.comparative_manager.load_result_comparison(self)

                if result[0] is None or result[1] is None:
                    return

                # Unpack results
                if len(result[0]) == 2 and isinstance(result[0], tuple):
                    won_team_stats, won_opponent_stats = result[0]
                    lost_team_stats, lost_opponent_stats = result[1]
                else:
                    won_team_stats = result[0]
                    won_opponent_stats = []
                    lost_team_stats = result[1]
                    lost_opponent_stats = []

                comparison_label = result[2]

                # Update stored data with won stats
                self.opponent_stats = won_opponent_stats or []

                # Update legend title
                TrendLegendBuilder.update_legend_titles(self.trend_legend_titles, comparison_label)

                # Show comparative tables
                self._show_comparative_tables(won_team_stats, lost_team_stats,
                                             won_opponent_stats, lost_opponent_stats)

            elif period_type == "last_match":
                # Show last match comparison for selected team
                self._show_last_match_selection()

            else:
                # General mode - all data
                result = self.comparative_manager.load_general_data(self)

                if result is None:
                    return

                # Unpack results
                if isinstance(result, tuple) and len(result) == 2:
                    team_stats, opponent_stats = result
                else:
                    team_stats = result
                    opponent_stats = []

                # Update the stored data
                self.opponent_stats = opponent_stats or []

                # Clear and repopulate tables
                self._reload_tables(team_stats)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar datos: {str(e)}")

    def _reload_tables(self, team_stats: List[Dict]):
        """Reload all tables with new data."""
        # Hide trend legends in normal mode
        if hasattr(self, 'trend_legend'):
            self.trend_legend.setVisible(False)
        if hasattr(self, 'basic_trend_legend'):
            self.basic_trend_legend.setVisible(False)

        # Get numeric data and calculate quartiles
        basic_numeric_data = get_basic_numeric_data(team_stats)
        advanced_numeric_data = get_advanced_numeric_data(team_stats)

        basic_quartiles = {key: calculate_quartiles(values) for key, (values, _) in basic_numeric_data.items()}
        advanced_quartiles = {key: calculate_quartiles(values) for key, (values, _) in advanced_numeric_data.items()}

        # Get opponent numeric data and quartiles if available
        if self.opponent_stats:
            opponent_numeric_data = get_advanced_numeric_data(self.opponent_stats)
            opponent_quartiles = {key: calculate_quartiles(values) for key, (values, _) in opponent_numeric_data.items()}
        else:
            opponent_numeric_data = {}
            opponent_quartiles = {}

        # Clear tables
        self.basic_table.setRowCount(0)
        self.advanced_table.setRowCount(0)
        if self.opponent_table:
            self.opponent_table.setRowCount(0)

        # Repopulate tables
        self.basic_table.setRowCount(len(team_stats))
        self.advanced_table.setRowCount(len(team_stats))
        if self.opponent_table:
            self.opponent_table.setRowCount(len(self.opponent_stats))

        # Disable sorting while populating
        self.basic_table.setSortingEnabled(False)
        self.advanced_table.setSortingEnabled(False)
        if self.opponent_table:
            self.opponent_table.setSortingEnabled(False)

        for row, stats in enumerate(team_stats):
            self.table_manager.populate_basic_stats_row(self.basic_table, row, stats, basic_numeric_data, basic_quartiles)
            self._populate_advanced_stats_row(row, stats, advanced_numeric_data, advanced_quartiles, self.advanced_table)

        if self.opponent_table:
            for row, stats in enumerate(self.opponent_stats):
                self._populate_advanced_stats_row(row, stats, opponent_numeric_data, opponent_quartiles, self.opponent_table)

        # Re-enable sorting
        self.basic_table.setSortingEnabled(True)
        self.advanced_table.setSortingEnabled(True)
        if self.opponent_table:
            self.opponent_table.setSortingEnabled(True)

    def _show_comparative_tables(self, monthly_team_stats: List[Dict], rest_team_stats: List[Dict],
                                 monthly_opponent_stats: List[Dict], rest_opponent_stats: List[Dict]):
        """Show comparative view with monthly vs rest of season statistics."""
        # Show trend legends in comparative mode
        if hasattr(self, 'trend_legend'):
            self.trend_legend.setVisible(True)
        if hasattr(self, 'basic_trend_legend'):
            self.basic_trend_legend.setVisible(True)

        # Create dictionaries for quick lookup by team_id
        monthly_dict = {str(team["_id"]): team for team in monthly_team_stats}
        rest_dict = {str(team["_id"]): team for team in rest_team_stats}

        # Get all unique team IDs
        all_team_ids = set(monthly_dict.keys()) | set(rest_dict.keys())

        # Create comparative stats for teams that have data in both periods
        comparative_stats = []
        for team_id in all_team_ids:
            if team_id in monthly_dict and team_id in rest_dict:
                monthly = monthly_dict[team_id]
                rest = rest_dict[team_id]

                # Create comparative entry with both monthly and rest data
                comp_stat = self.stats_calculator.create_comparative_stat(monthly, rest)
                comparative_stats.append(comp_stat)

        if not comparative_stats:
            QMessageBox.information(self, "Sin datos", "No hay equipos con datos en ambos períodos")
            return

        # Get numeric data for styling (use monthly data for quartiles)
        basic_numeric_data = get_basic_numeric_data(monthly_team_stats)
        advanced_numeric_data = get_advanced_numeric_data(monthly_team_stats)

        basic_quartiles = {key: calculate_quartiles(values) for key, (values, _) in basic_numeric_data.items()}
        advanced_quartiles = {key: calculate_quartiles(values) for key, (values, _) in advanced_numeric_data.items()}

        # Clear and repopulate basic table with comparative data
        self.basic_table.setRowCount(0)
        self.basic_table.setRowCount(len(comparative_stats))
        self.basic_table.setSortingEnabled(False)

        for row, stats in enumerate(comparative_stats):
            self.table_manager.populate_comparative_basic_row(
                self.basic_table, row, stats, basic_numeric_data, basic_quartiles
            )

        self.basic_table.setSortingEnabled(True)

        # For advanced table, show monthly data with trend indicators
        self.advanced_table.setRowCount(0)
        self.advanced_table.setRowCount(len(comparative_stats))
        self.advanced_table.setSortingEnabled(False)

        for row, stats in enumerate(comparative_stats):
            self.table_manager.populate_comparative_advanced_row(
                self.advanced_table, row, stats, advanced_numeric_data, advanced_quartiles
            )

        self.advanced_table.setSortingEnabled(True)

        # Handle opponent table if available
        if self.opponent_table and monthly_opponent_stats and rest_opponent_stats:
            monthly_opp_dict = {str(team["_id"]): team for team in monthly_opponent_stats}
            rest_opp_dict = {str(team["_id"]): team for team in rest_opponent_stats}

            comparative_opp_stats = []
            for team_id in all_team_ids:
                if team_id in monthly_opp_dict and team_id in rest_opp_dict:
                    comp_stat = self.stats_calculator.create_comparative_stat(
                        monthly_opp_dict[team_id], rest_opp_dict[team_id]
                    )
                    comparative_opp_stats.append(comp_stat)

            if comparative_opp_stats:
                opp_numeric_data = get_advanced_numeric_data(monthly_opponent_stats)
                opp_quartiles = {key: calculate_quartiles(values) for key, (values, _) in opp_numeric_data.items()}

                self.opponent_table.setRowCount(0)
                self.opponent_table.setRowCount(len(comparative_opp_stats))
                self.opponent_table.setSortingEnabled(False)

                for row, stats in enumerate(comparative_opp_stats):
                    self.table_manager.populate_comparative_advanced_row(
                        self.opponent_table, row, stats, opp_numeric_data, opp_quartiles
                    )

                self.opponent_table.setSortingEnabled(True)

    def _show_last_match_selection(self):
        """Show team selector and then display last match comparison."""
        if not self.db_handler or not self.collection_name:
            QMessageBox.warning(self, "Error", "No hay acceso a la base de datos")
            return

        # Get all teams
        teams = self.db_handler.get_all_teams(self.collection_name)
        if not teams:
            QMessageBox.information(self, "Sin datos", "No hay equipos disponibles")
            return

        # Show team selector dialog
        dialog = TeamSelectorDialog(teams, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            # User canceled - return to general mode
            self.period_combo.setCurrentIndex(0)
            return

        selected_team = dialog.get_selected_team()
        if not selected_team:
            self.period_combo.setCurrentIndex(0)
            return

        # Get last match for selected team
        last_match = self.db_handler.get_last_match(self.collection_name, selected_team)
        if not last_match:
            QMessageBox.information(self, "Sin datos",
                                   f"No se encontró ningún partido para {selected_team}")
            self.period_combo.setCurrentIndex(0)
            return

        # Process and show last match
        self._process_and_show_last_match(last_match, selected_team)

    def _process_and_show_last_match(self, match_doc: Dict, selected_team: str):
        """
        Process last match document and show comparison.

        Args:
            match_doc: MongoDB document of the last match
            selected_team: Name of the selected team
        """
        try:
            # Extract match info
            header = match_doc.get("HEADER", {})
            boxscore = match_doc.get("BOXSCORE", {})
            teams_data = boxscore.get("TEAM", [])

            if len(teams_data) != 2:
                QMessageBox.warning(self, "Error", "Datos del partido incompletos")
                return

            # Find which team is the selected one using utility function
            selected_team_data, selected_idx = get_team_data_by_name(match_doc, selected_team)

            if selected_team_data is None:
                QMessageBox.warning(self, "Error", "No se encontró el equipo seleccionado en el partido")
                return

            # Get opponent data (the other team)
            opponent_idx = 1 - selected_idx
            opponent_team_data = teams_data[opponent_idx].get("TOTAL", {})
            selected_is_home = (selected_idx == 0)

            # Calculate match stats for both teams
            selected_stats = self.stats_calculator.calculate_single_match_stats(selected_team_data, opponent_team_data)
            opponent_stats = self.stats_calculator.calculate_single_match_stats(opponent_team_data, selected_team_data)

            # Get season stats for trends (excluding this match)
            season_team_stats, _ = self.reload_callback(
                self.collection_name, date_filter=None, venue_filter=None, result_filter=None
            )

            # Find season stats for both teams
            selected_season = next((t for t in season_team_stats if t["team_name"] == selected_team), None)
            opponent_season = next((t for t in season_team_stats if t["team_name"] == opponent_team_data.get("name", "")), None)

            # Show comparison
            self._show_last_match_comparison(
                selected_stats, opponent_stats,
                selected_season, opponent_season,
                header, selected_is_home
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al procesar el partido: {str(e)}")
            import traceback
            traceback.print_exc()

    def _show_last_match_comparison(self, selected_stats: Dict, opponent_stats: Dict,
                                     selected_season: Dict, opponent_season: Dict,
                                     header: Dict, selected_is_home: bool):
        """
        Show last match comparison with colors and trends.

        Args:
            selected_stats: Match stats for selected team
            opponent_stats: Match stats for opponent team
            selected_season: Season stats for selected team
            opponent_season: Season stats for opponent team
            header: Match header info
            selected_is_home: Whether selected team played at home
        """
        # Show trend legends in last match mode
        if hasattr(self, 'trend_legend'):
            self.trend_legend.setVisible(True)
        if hasattr(self, 'basic_trend_legend'):
            self.basic_trend_legend.setVisible(True)

        # Update legend title
        self._update_trend_legend_title("último partido vs temporada")

        # Clear tables
        for table in [self.basic_table, self.advanced_table]:
            table.setRowCount(0)
            table.setSortingEnabled(False)

        # Set up comparison for both tables
        self.basic_table.setRowCount(2)
        self.advanced_table.setRowCount(2)

        # Populate advanced table rows with colored comparison
        self.table_manager.populate_last_match_row(
            self.advanced_table, 0, selected_stats, opponent_stats, selected_season, True, is_basic=False
        )
        self.table_manager.populate_last_match_row(
            self.advanced_table, 1, opponent_stats, selected_stats, opponent_season, False, is_basic=False
        )

        # Populate basic table rows with colored comparison
        self.table_manager.populate_last_match_row(
            self.basic_table, 0, selected_stats, opponent_stats, selected_season, True, is_basic=True
        )
        self.table_manager.populate_last_match_row(
            self.basic_table, 1, opponent_stats, selected_stats, opponent_season, False, is_basic=True
        )

        # Add match info as window title update
        match_date = header.get("starttime", "")
        match_place = header.get("place", "")
        venue_text = "Local" if selected_is_home else "Visitante"
        self.setWindowTitle(f"MfA - Último Partido: {selected_stats['team_name']} ({venue_text}) - {match_date}")

        self.basic_table.setSortingEnabled(True)
        self.advanced_table.setSortingEnabled(True)


