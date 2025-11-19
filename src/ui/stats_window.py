"""Team statistics display window."""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QTableWidget, QHeaderView, QTabWidget, QPushButton,
                              QFileDialog, QMessageBox, QMenu, QTableWidgetItem, QLabel,
                              QRadioButton, QButtonGroup, QComboBox, QFrame, QDialog)
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

    # Filter constants
    RESULT_WON = 'won'
    RESULT_LOST = 'lost'
    VENUE_HOME = True
    VENUE_AWAY = False

    # Cache keys
    CACHE_GENERAL = 'general'
    CACHE_MONTHLY = 'monthly'
    CACHE_REST = 'rest'
    CACHE_HOME = 'home'
    CACHE_AWAY = 'away'
    CACHE_WON = 'won'
    CACHE_LOST = 'lost'

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

        # List to store references to trend legend titles
        self.trend_legend_titles = []

        # Cache for loaded data to avoid reloading when switching tabs
        # Keys: 'general', 'monthly', 'rest', 'home', 'away', 'won', 'lost'
        # Values: Tuple (team_stats, opponent_stats) or None
        self._data_cache = {
            self.CACHE_GENERAL: None,   # All season data
            self.CACHE_MONTHLY: None,   # Last month data
            self.CACHE_REST: None,      # Rest of season data (excluding last month)
            self.CACHE_HOME: None,      # Home games only
            self.CACHE_AWAY: None,      # Away games only
            self.CACHE_WON: None,       # Won games only
            self.CACHE_LOST: None       # Lost games only
        }

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
        self.basic_trend_legend = self._create_trend_legend()
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
        self.trend_legend = self._create_trend_legend()
        self.trend_legend.setVisible(False)
        advanced_layout.addWidget(self.trend_legend)

        self.tab_widget.addTab(advanced_tab, "Estadísticas Avanzadas")

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

    def _create_trend_legend(self) -> QWidget:
        """Create a trend indicator legend widget for comparative mode."""
        from PyQt6.QtWidgets import QFrame, QLabel, QHBoxLayout

        legend_frame = QFrame()
        legend_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        legend_frame.setMaximumHeight(40)

        legend_layout = QHBoxLayout(legend_frame)
        legend_layout.setContentsMargins(10, 5, 10, 5)
        legend_layout.setSpacing(15)

        # Add legend title (store reference for later updates)
        title_label = QLabel("Tendencia:")
        title_label.setStyleSheet("font-weight: bold;")
        legend_layout.addWidget(title_label)

        # Store reference to this title
        self.trend_legend_titles.append(title_label)

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
        for title_label in self.trend_legend_titles:
            title_label.setText(f"Tendencia ({comparison_text}):")

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
        return "estadisticas_avanzadas"  # fallback

    def _export_csv(self):
        """Export current table to CSV format."""
        table = self._get_current_table()
        table_name = self._get_current_table_name()
        self.stats_exporter.export_to_csv(table, table_name)

    def _export_png(self):
        """Export current table to PNG image."""
        table = self._get_current_table()
        table_name = self._get_current_table_name()
        self.stats_exporter.export_to_png(table, table_name)

    def _export_pdf(self):
        """Export current table to PDF format."""
        table = self._get_current_table()
        table_name = self._get_current_table_name()
        window_title = self.windowTitle()
        self.stats_exporter.export_to_pdf(table, table_name, window_title)

    def _on_view_mode_changed(self):
        """Handle view mode change between Teams and Opponents."""
        if not self.opponent_table:
            return

        # Toggle visibility of tables
        is_opponent_view = self.opponents_radio.isChecked()
        self.advanced_table.setVisible(not is_opponent_view)
        self.opponent_table.setVisible(is_opponent_view)

        # Adjust window size for the new view
        QTimer.singleShot(50, self._adjust_window_size_for_current_tab)

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
        self._data_cache = {
            self.CACHE_GENERAL: None,
            self.CACHE_MONTHLY: None,
            self.CACHE_REST: None,
            self.CACHE_HOME: None,
            self.CACHE_AWAY: None,
            self.CACHE_WON: None,
            self.CACHE_LOST: None
        }

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
                cache_key_recent = f"{self.CACHE_MONTHLY}_{days}"
                cache_key_rest = f"{self.CACHE_REST}_{days}"

                # Check cache first
                if cache_key_recent not in self._data_cache or cache_key_rest not in self._data_cache or \
                   self._data_cache.get(cache_key_recent) is None or self._data_cache.get(cache_key_rest) is None:
                    # Get recent period data
                    recent_filter = {"$gte": period_start}
                    recent_team_stats, recent_opponent_stats = self.reload_callback(
                        self.collection_name, date_filter=recent_filter, venue_filter=None, result_filter=None
                    )

                    # Get rest of season data (before recent period)
                    rest_filter = {"$lt": period_start}
                    rest_team_stats, rest_opponent_stats = self.reload_callback(
                        self.collection_name, date_filter=rest_filter, venue_filter=None, result_filter=None
                    )

                    # Cache the loaded data
                    self._data_cache[cache_key_recent] = (recent_team_stats, recent_opponent_stats)
                    self._data_cache[cache_key_rest] = (rest_team_stats, rest_opponent_stats)
                else:
                    # Use cached data
                    recent_team_stats, recent_opponent_stats = self._data_cache[cache_key_recent]
                    rest_team_stats, rest_opponent_stats = self._data_cache[cache_key_rest]

                if not recent_team_stats or not rest_team_stats:
                    QMessageBox.information(self, "Sin datos", "No hay suficientes datos para comparar")
                    return

                # Update stored data with recent stats
                self.opponent_stats = recent_opponent_stats or []

                # Update legend title with selected period
                period_label = f"últimos {days} días" if days != 30 else "último mes"
                self._update_trend_legend_title(f"{period_label} vs resto temporada")

                # Show comparative tables
                self._show_comparative_tables(recent_team_stats, rest_team_stats,
                                             recent_opponent_stats, rest_opponent_stats)

            elif period_type == "venue_comparative":
                # Load both home and away data for comparison
                # Check cache first
                if self._data_cache[self.CACHE_HOME] is None or self._data_cache[self.CACHE_AWAY] is None:
                    # Get home data (venue_filter=True means local/home)
                    home_team_stats, home_opponent_stats = self.reload_callback(
                        self.collection_name, date_filter=None, venue_filter=self.VENUE_HOME, result_filter=None
                    )

                    # Get away data (venue_filter=False means visitante/away)
                    away_team_stats, away_opponent_stats = self.reload_callback(
                        self.collection_name, date_filter=None, venue_filter=self.VENUE_AWAY, result_filter=None
                    )

                    # Cache the loaded data
                    self._data_cache[self.CACHE_HOME] = (home_team_stats, home_opponent_stats)
                    self._data_cache[self.CACHE_AWAY] = (away_team_stats, away_opponent_stats)
                else:
                    # Use cached data
                    home_team_stats, home_opponent_stats = self._data_cache[self.CACHE_HOME]
                    away_team_stats, away_opponent_stats = self._data_cache[self.CACHE_AWAY]

                if not home_team_stats or not away_team_stats:
                    QMessageBox.information(self, "Sin datos", "No hay suficientes datos para comparar")
                    return

                # Update stored data with home stats
                self.opponent_stats = home_opponent_stats or []

                # Update legend title
                self._update_trend_legend_title("local vs visitante")

                # Show comparative tables
                self._show_comparative_tables(home_team_stats, away_team_stats,
                                             home_opponent_stats, away_opponent_stats)

            elif period_type == "result_comparative":
                # Load both won and lost games data for comparison
                # Check cache first
                if self._data_cache[self.CACHE_WON] is None or self._data_cache[self.CACHE_LOST] is None:
                    # Get won games data (result_filter='won')
                    won_team_stats, won_opponent_stats = self.reload_callback(
                        self.collection_name, date_filter=None, venue_filter=None, result_filter=self.RESULT_WON
                    )

                    # Get lost games data (result_filter='lost')
                    lost_team_stats, lost_opponent_stats = self.reload_callback(
                        self.collection_name, date_filter=None, venue_filter=None, result_filter=self.RESULT_LOST
                    )

                    # Cache the loaded data
                    self._data_cache[self.CACHE_WON] = (won_team_stats, won_opponent_stats)
                    self._data_cache[self.CACHE_LOST] = (lost_team_stats, lost_opponent_stats)
                else:
                    # Use cached data
                    won_team_stats, won_opponent_stats = self._data_cache[self.CACHE_WON]
                    lost_team_stats, lost_opponent_stats = self._data_cache[self.CACHE_LOST]

                if not won_team_stats or not lost_team_stats:
                    QMessageBox.information(self, "Sin datos", "No hay suficientes datos para comparar")
                    return

                # Update stored data with won stats
                self.opponent_stats = won_opponent_stats or []

                # Update legend title
                self._update_trend_legend_title("ganados vs perdidos")

                # Show comparative tables
                self._show_comparative_tables(won_team_stats, lost_team_stats,
                                             won_opponent_stats, lost_opponent_stats)

            elif period_type == "last_match":
                # Show last match comparison for selected team
                self._show_last_match_selection()

            else:
                # General mode - all data
                # Check cache first
                if self._data_cache[self.CACHE_GENERAL] is None:
                    team_stats, opponent_stats = self.reload_callback(
                        self.collection_name, date_filter=None, venue_filter=None, result_filter=None
                    )
                    # Cache the loaded data
                    self._data_cache[self.CACHE_GENERAL] = (team_stats, opponent_stats)
                else:
                    # Use cached data
                    team_stats, opponent_stats = self._data_cache[self.CACHE_GENERAL]

                if not team_stats:
                    QMessageBox.information(self, "Sin datos", "No hay datos para el período seleccionado")
                    return

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
            self._populate_basic_stats_row(row, stats, basic_numeric_data, basic_quartiles)
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

            # Find which team is the selected one
            team1_data = teams_data[0].get("TOTAL", {})
            team2_data = teams_data[1].get("TOTAL", {})

            team1_name = team1_data.get("name", "")
            team2_name = team2_data.get("name", "")

            if selected_team == team1_name:
                selected_team_data = team1_data
                opponent_team_data = team2_data
                selected_is_home = True
            elif selected_team == team2_name:
                selected_team_data = team2_data
                opponent_team_data = team1_data
                selected_is_home = False
            else:
                QMessageBox.warning(self, "Error", "No se encontró el equipo seleccionado en el partido")
                return

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

    def _populate_last_match_row(self, row: int, team_stats: Dict, opponent_stats: Dict,
                                  season_stats: Dict, is_selected_team: bool, table: QTableWidget,
                                  is_basic: bool = False):
        """
        Populate a row in the table for last match comparison.

        Args:
            row: Row index
            team_stats: Match stats for this team
            opponent_stats: Match stats for the opponent
            season_stats: Season stats for trend calculation
            is_selected_team: Whether this is the selected team row
            table: The table to populate (basic or advanced)
            is_basic: Whether this is the basic stats table
        """
        # Team name
        team_name = team_stats["team_name"]
        table.setItem(row, 0, NumericTableWidgetItem(team_name, team_name, False))

        # Get stats configuration based on table type
        if is_basic:
            # For basic table: team name, games, games home, games away, then stats
            table.setItem(row, 1, NumericTableWidgetItem(1, "1"))  # Total games
            table.setItem(row, 2, NumericTableWidgetItem(1 if is_selected_team else 0, "1" if is_selected_team else "0"))  # Games home
            table.setItem(row, 3, NumericTableWidgetItem(0 if is_selected_team else 1, "0" if is_selected_team else "1"))  # Games away
            stats_config = get_basic_stats_config(team_stats)
        else:
            # For advanced table: team name, games, then stats
            table.setItem(row, 1, NumericTableWidgetItem(1, "1"))
            stats_config = get_advanced_stats_config(team_stats)

        # Define which stats are "higher is better"
        higher_is_better = {
            "points_per_game", "fg2_percentage", "fg3_percentage", "ft_percentage",
            "fg_percentage", "efg_percentage", "true_shooting", "assists_per_game",
            "steals_per_game", "blocks_per_game", "offensive_rating", "net_rating",
            "rebounds_per_game", "oreb_percentage", "possessions_per_game",
            "offensive_rebound_rate", "three_point_rate", "free_throw_rate",
            "assist_fg_rate", "assist_rate", "steal_rate", "block_rate",
            "points_scored", "total_rebounds", "rebounds_def", "rebounds_off",
            "assists", "steals", "blocks"
        }

        # Define which stats are "lower is better"
        lower_is_better = {
            "defensive_rating", "turnover_rate", "turnovers_per_game",
            "points_against_per_game", "points_received", "turnovers"
        }

        # Process each stat
        for idx, key, raw_value in stats_config:
            if is_basic and idx < 4:  # Skip team name and games columns in basic
                continue
            elif not is_basic and idx < 2:  # Skip team name and games in advanced
                continue

            num_value, display_value = process_numeric_value(raw_value, key)

            # Add percentage symbol if needed
            if is_basic:
                if key in PERCENTAGE_FIELDS:
                    display_value = f"{display_value}%"
            else:
                if key not in NON_PERCENTAGE_FIELDS:
                    display_value = f"{display_value}%"

            # Get opponent value for comparison
            opponent_value = opponent_stats.get(key, 0)

            # Determine comparison color
            if abs(num_value - opponent_value) < 0.01:  # Essentially equal
                bg_color = "#D3D3D3"  # Gray
            elif key in higher_is_better:
                bg_color = "#90EE90" if num_value > opponent_value else "#FFB6C1"  # Green or light red
            elif key in lower_is_better:
                bg_color = "#90EE90" if num_value < opponent_value else "#FFB6C1"  # Green or light red
            else:  # Default: higher is better
                bg_color = "#90EE90" if num_value > opponent_value else "#FFB6C1"  # Green or light red

            # Calculate trend vs season average
            trend_symbol = ""
            trend_color = "gray"

            if season_stats and key in season_stats:
                season_value = season_stats.get(key, 0)

                # Calculate delta
                if isinstance(season_value, (int, float)) and season_value != 0:
                    delta = ((num_value - season_value) / abs(season_value)) * 100

                    # Use trend calculator to get symbol
                    trend_symbol, trend_color = self.trend_calculator.get_trend_indicator(delta, key, is_opponent=False)

            # Create cell widget with color and trend
            cell_label = QLabel()
            cell_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            cell_label.setStyleSheet(f"background-color: {bg_color}; padding: 4px;")

            if trend_symbol:
                cell_label.setText(f'{display_value} <span style="color: {trend_color}; font-weight: bold;">{trend_symbol}</span>')
            else:
                cell_label.setText(display_value)

            # Create item for sorting
            item = NumericTableWidgetItem(num_value, "")

            table.setCellWidget(row, idx, cell_label)
            table.setItem(row, idx, item)




