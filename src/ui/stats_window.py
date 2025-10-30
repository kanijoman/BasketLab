"""Team statistics display window."""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QTableWidget,
                              QHeaderView, QTabWidget)
from PyQt6.QtCore import Qt
from typing import List, Dict

from .table_items import NumericTableWidgetItem, process_numeric_value
from .stats_config import (
    BASIC_COLUMNS, ADVANCED_COLUMNS,
    PERCENTAGE_FIELDS, ADVANCED_PERCENTAGE_FIELDS, NON_PERCENTAGE_FIELDS,
    get_basic_stats_config, get_advanced_stats_config,
    get_basic_numeric_data, get_advanced_numeric_data,
    calculate_quartiles, get_quartile_color
)


class TeamStatsWindow(QMainWindow):
    """Window to display team statistics."""

    def __init__(self, team_stats: List[Dict], parent=None):
        """
        Initialize the team stats window.

        Args:
            team_stats: List of team statistics dictionaries
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Estadísticas de Equipo")
        # Set a reasonable minimum window size considering all columns
        self.setMinimumSize(1200, 600)
        self.setup_ui(team_stats)

    def setup_ui(self, team_stats: List[Dict]):
        """Set up the UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create tab widget
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)

        # Create basic stats tab
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        self.basic_table = QTableWidget()
        basic_layout.addWidget(self.basic_table)
        tab_widget.addTab(basic_tab, "Estadísticas Básicas")

        # Create advanced stats tab
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout(advanced_tab)
        self.advanced_table = QTableWidget()
        advanced_layout.addWidget(self.advanced_table)
        tab_widget.addTab(advanced_tab, "Estadísticas Avanzadas")

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

        # Get numeric data and calculate quartiles
        basic_numeric_data = get_basic_numeric_data(team_stats)
        advanced_numeric_data = get_advanced_numeric_data(team_stats)

        basic_quartiles = {key: calculate_quartiles(values) for key, (values, _) in basic_numeric_data.items()}
        advanced_quartiles = {key: calculate_quartiles(values) for key, (values, _) in advanced_numeric_data.items()}

        # Populate tables
        self.basic_table.setRowCount(len(team_stats))
        self.advanced_table.setRowCount(len(team_stats))

        for row, team in enumerate(team_stats):
            # Populate basic stats table
            self._populate_basic_stats_row(row, team, basic_numeric_data, basic_quartiles)
            # Populate advanced stats table
            self._populate_advanced_stats_row(row, team, advanced_numeric_data, advanced_quartiles)

        # Configure scrollbars for both tables
        for table in [self.basic_table, self.advanced_table]:
            table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Calculate and set window size
        self._set_window_size()

    def _populate_basic_stats_row(self, row: int, team: Dict, numeric_data: Dict, quartiles: Dict):
        """Populate a row in the basic stats table."""
        numeric_cols = []

        # Get stats configuration for this team
        basic_stats_config = get_basic_stats_config(team)

        for idx, key, raw_value in basic_stats_config:
            num_value, display_value = process_numeric_value(raw_value, key)
            # Add percentage symbol for percentage stats
            if key in PERCENTAGE_FIELDS:
                display_value = f"{display_value}%"
            numeric_cols.append((idx, key, num_value, display_value))

        # Team name - no color (text sorting)
        self.basic_table.setItem(row, 0, NumericTableWidgetItem(team["team_name"], team["team_name"], False))

        # Games columns - no color (numeric sorting)
        self.basic_table.setItem(row, 1, NumericTableWidgetItem(team["total_games"], str(team["total_games"])))
        self.basic_table.setItem(row, 2, NumericTableWidgetItem(team["games_home"], str(team["games_home"])))
        self.basic_table.setItem(row, 3, NumericTableWidgetItem(team["games_away"], str(team["games_away"])))

        for col_idx, key, value, value_str in numeric_cols:
            item = NumericTableWidgetItem(value, value_str)
            color = get_quartile_color(
                float(value),
                quartiles[key],
                numeric_data[key][1]  # Get reverse flag
            )
            item.setBackground(color)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.basic_table.setItem(row, col_idx, item)

    def _populate_advanced_stats_row(self, row: int, team: Dict, numeric_data: Dict, quartiles: Dict):
        """Populate a row in the advanced stats table."""
        numeric_cols = []

        # Get advanced stats configuration for this team
        advanced_stats_config = get_advanced_stats_config(team)

        for idx, key, raw_value in advanced_stats_config:
            num_value, display_value = process_numeric_value(raw_value, key)
            # Add percentage symbol for percentage stats (exclude possessions, ratings)
            if key not in NON_PERCENTAGE_FIELDS:
                display_value = f"{display_value}%"
            numeric_cols.append((idx, key, num_value, display_value))

        # Team name and games
        self.advanced_table.setItem(row, 0, NumericTableWidgetItem(team["team_name"], team["team_name"], False))
        self.advanced_table.setItem(row, 1, NumericTableWidgetItem(team["total_games"], str(team["total_games"])))

        for col_idx, key, value, value_str in numeric_cols:
            item = NumericTableWidgetItem(value, value_str)
            color = get_quartile_color(
                float(value),
                quartiles[key],
                numeric_data[key][1]
            )
            item.setBackground(color)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.advanced_table.setItem(row, col_idx, item)

    def _set_window_size(self):
        """Calculate and set the window size based on table content."""
        # Allow table to update and calculate its dimensions
        self.basic_table.updateGeometry()
        self.advanced_table.updateGeometry()

        # Calculate total size needed (use basic table as reference)
        scrollbar_width = 30 if self.basic_table.verticalScrollBar().isVisible() else 0
        scrollbar_height = 30 if self.basic_table.horizontalScrollBar().isVisible() else 0

        # Add additional margins to ensure all content is visible
        margin = 50  # Extra margin to avoid scrolling

        table_width = self.basic_table.horizontalHeader().length() + scrollbar_width + margin
        table_height = (self.basic_table.verticalHeader().length() +
                       self.basic_table.horizontalHeader().height() +
                       scrollbar_height + margin + 50)  # Extra 50 for tabs

        # Adjust window size considering the frame
        frame_width = self.frameGeometry().width() - self.geometry().width()
        frame_height = self.frameGeometry().height() - self.geometry().height()

        # Set window size with increased maximum limits
        window_width = min(table_width + frame_width, 1800)
        window_height = min(table_height + frame_height, 1200)

        # Ensure size is not smaller than minimum
        window_width = max(window_width, self.minimumWidth())
        window_height = max(window_height, self.minimumHeight())

        self.resize(window_width, window_height)

        # Center window on screen
        self.setGeometry(
            (self.screen().availableGeometry().width() - window_width) // 2,
            (self.screen().availableGeometry().height() - window_height) // 2,
            window_width,
            window_height
        )
