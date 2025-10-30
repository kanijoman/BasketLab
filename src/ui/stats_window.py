"""Team statistics display window."""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QTableWidget,
                              QHeaderView, QTabWidget)
from PyQt6.QtCore import Qt, QTimer
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
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Create basic stats tab
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        self.basic_table = QTableWidget()
        basic_layout.addWidget(self.basic_table)
        self.tab_widget.addTab(basic_tab, "Estadísticas Básicas")

        # Create advanced stats tab
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout(advanced_tab)
        self.advanced_table = QTableWidget()
        advanced_layout.addWidget(self.advanced_table)
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

    def _on_tab_changed(self, index: int):
        """
        Handle tab change event to adjust window size.

        Args:
            index: Index of the newly selected tab
        """
        # Use QTimer to delay resize until the tab is fully rendered
        QTimer.singleShot(50, self._adjust_window_size_for_current_tab)

    def _adjust_window_size_for_current_tab(self):
        """Adjust window size based on the currently active tab."""
        current_index = self.tab_widget.currentIndex()

        # Select the appropriate table
        if current_index == 0:
            active_table = self.basic_table
        else:
            active_table = self.advanced_table

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

        # Use QTimer to ensure tables are fully rendered before resizing
        QTimer.singleShot(100, self._adjust_window_size_for_current_tab)
