"""Team statistics display window."""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QTableWidget, QHeaderView, QTabWidget, QPushButton,
                              QFileDialog, QMessageBox, QMenu, QTableWidgetItem, QLabel,
                              QRadioButton, QButtonGroup, QComboBox, QFrame)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QPageLayout, QPageSize, QAction, QColor
from PyQt6.QtPrintSupport import QPrinter
from typing import List, Dict, Callable
import csv
from datetime import datetime, timedelta

from .table_items import NumericTableWidgetItem, process_numeric_value
from .stats_config import (
    BASIC_COLUMNS, ADVANCED_COLUMNS,
    PERCENTAGE_FIELDS, ADVANCED_PERCENTAGE_FIELDS, NON_PERCENTAGE_FIELDS,
    get_basic_stats_config, get_advanced_stats_config,
    get_basic_numeric_data, get_advanced_numeric_data,
    calculate_quartiles, get_quartile_color
)
from .trend_calculator import TrendCalculator
from .ui_utils import set_app_icon


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

    def __init__(self, team_stats: List[Dict], opponent_stats: List[Dict] = None,
                 collection_name: str = None, reload_callback: Callable = None, parent=None):
        """
        Initialize the team stats window.

        Args:
            team_stats: List of team statistics dictionaries
            opponent_stats: List of opponent statistics dictionaries (optional)
            collection_name: Name of the collection for reloading data
            reload_callback: Callback function to reload data with date filter
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
        self.opponent_stats = opponent_stats or []

        # Initialize trend calculator
        self.trend_calculator = TrendCalculator()

        # Cache for loaded data to avoid reloading when switching tabs
        self._data_cache = {
            'general': None,
            'monthly': None,
            'rest': None
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
        controls_layout.addWidget(period_label)

        self.period_combo = QComboBox()
        self.period_combo.addItem("General (toda la temporada)", "general")
        self.period_combo.addItem("Mensual (comparativa último mes)", "comparative")
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
            self._populate_basic_stats_row(row, team, basic_numeric_data, basic_quartiles)
            # Populate advanced stats table
            self._populate_advanced_stats_row(row, team, advanced_numeric_data, advanced_quartiles)

        # Populate opponent stats table if available
        if self.opponent_table and self.opponent_stats:
            for row, opp_team in enumerate(self.opponent_stats):
                self._populate_advanced_stats_row(row, opp_team, opponent_numeric_data, opponent_quartiles, self.opponent_table)

        # Configure scrollbars for all tables
        tables_to_configure = [self.basic_table, self.advanced_table]
        if self.opponent_table:
            tables_to_configure.append(self.opponent_table)

        for table in tables_to_configure:
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

    def _populate_advanced_stats_row(self, row: int, team: Dict, numeric_data: Dict, quartiles: Dict, table=None):
        """Populate a row in the advanced stats table (or opponent stats table)."""
        # Use provided table or default to advanced_table
        target_table = table if table is not None else self.advanced_table

        # Determine if we're populating the opponent table (colors should be inverted)
        is_opponent_table = target_table is self.opponent_table

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
        target_table.setItem(row, 0, NumericTableWidgetItem(team["team_name"], team["team_name"], False))
        target_table.setItem(row, 1, NumericTableWidgetItem(team["total_games"], str(team["total_games"])))

        for col_idx, key, value, value_str in numeric_cols:
            item = NumericTableWidgetItem(value, value_str)
            # For opponent stats, invert the color logic
            reverse_flag = numeric_data[key][1]
            if is_opponent_table:
                reverse_flag = not reverse_flag  # Invert for opponent stats

            color = get_quartile_color(
                float(value),
                quartiles[key],
                reverse_flag
            )
            item.setBackground(color)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            target_table.setItem(row, col_idx, item)

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

        # Add legend title
        title_label = QLabel("Tendencia (último mes vs resto temporada):")
        title_label.setStyleSheet("font-weight: bold;")
        legend_layout.addWidget(title_label)

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
        try:
            table = self._get_current_table()
            table_name = self._get_current_table_name()

            # Generate default filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"{table_name}_{timestamp}.csv"

            # Open file dialog
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar CSV",
                default_filename,
                "CSV Files (*.csv);;All Files (*)"
            )

            if not filename:
                return

            # Write CSV file
            with open(filename, 'w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file, delimiter=';')

                # Write headers
                headers = []
                for col in range(table.columnCount()):
                    headers.append(table.horizontalHeaderItem(col).text())
                writer.writerow(headers)

                # Write data rows
                for row in range(table.rowCount()):
                    row_data = []
                    for col in range(table.columnCount()):
                        item = table.item(row, col)
                        if item:
                            row_data.append(item.text())
                        else:
                            row_data.append('')
                    writer.writerow(row_data)

            QMessageBox.information(
                self,
                "Exportación exitosa",
                f"Tabla exportada correctamente a:\n{filename}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error al exportar",
                f"No se pudo exportar la tabla a CSV:\n{str(e)}"
            )

    def _export_png(self):
        """Export current table to PNG image."""
        try:
            table = self._get_current_table()
            table_name = self._get_current_table_name()

            # Generate default filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"{table_name}_{timestamp}.png"

            # Open file dialog
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar PNG",
                default_filename,
                "PNG Files (*.png);;All Files (*)"
            )

            if not filename:
                return

            # Capture table as image
            pixmap = table.grab()
            pixmap.save(filename, 'PNG')

            QMessageBox.information(
                self,
                "Exportación exitosa",
                f"Tabla exportada correctamente a:\n{filename}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error al exportar",
                f"No se pudo exportar la tabla a PNG:\n{str(e)}"
            )

    def _export_pdf(self):
        """Export current table to PDF format."""
        try:
            table = self._get_current_table()
            table_name = self._get_current_table_name()

            # Generate default filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"{table_name}_{timestamp}.pdf"

            # Open file dialog
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar PDF",
                default_filename,
                "PDF Files (*.pdf);;All Files (*)"
            )

            if not filename:
                return

            # Create printer and configure for PDF
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(filename)

            # Set page to landscape for better table fit
            page_layout = QPageLayout()
            page_layout.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            page_layout.setOrientation(QPageLayout.Orientation.Landscape)
            printer.setPageLayout(page_layout)

            # Create painter and render table
            painter = QPainter()
            painter.begin(printer)

            # Calculate scaling to fit table in page
            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            table_rect = table.rect()

            scale_x = page_rect.width() / table_rect.width()
            scale_y = page_rect.height() / table_rect.height()
            scale = min(scale_x, scale_y) * 0.95  # 95% to add margins

            painter.scale(scale, scale)

            # Render the table
            table.render(painter)

            painter.end()

            QMessageBox.information(
                self,
                "Exportación exitosa",
                f"Tabla exportada correctamente a:\n{filename}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error al exportar",
                f"No se pudo exportar la tabla a PDF:\n{str(e)}"
            )

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
            'general': None,
            'monthly': None,
            'rest': None
        }

    def _on_period_changed(self, index: int):
        """Handle period selection change."""
        if not self.reload_callback or not self.collection_name:
            QMessageBox.warning(self, "Error", "No se puede recargar datos sin callback o nombre de colección")
            return

        period_type = self.period_combo.itemData(index)

        try:
            if period_type == "comparative":
                # Load both monthly and rest-of-season data for comparison
                now = datetime.now()
                one_month_ago = now - timedelta(days=30)

                # Check cache first
                if self._data_cache['monthly'] is None or self._data_cache['rest'] is None:
                    # Get monthly data
                    monthly_filter = {"$gte": one_month_ago}
                    monthly_team_stats, monthly_opponent_stats = self.reload_callback(self.collection_name, monthly_filter)

                    # Get rest of season data (before last month)
                    rest_filter = {"$lt": one_month_ago}
                    rest_team_stats, rest_opponent_stats = self.reload_callback(self.collection_name, rest_filter)

                    # Cache the loaded data
                    self._data_cache['monthly'] = (monthly_team_stats, monthly_opponent_stats)
                    self._data_cache['rest'] = (rest_team_stats, rest_opponent_stats)
                else:
                    # Use cached data
                    monthly_team_stats, monthly_opponent_stats = self._data_cache['monthly']
                    rest_team_stats, rest_opponent_stats = self._data_cache['rest']

                if not monthly_team_stats or not rest_team_stats:
                    QMessageBox.information(self, "Sin datos", "No hay suficientes datos para comparar")
                    return

                # Update stored data with monthly stats
                self.opponent_stats = monthly_opponent_stats or []

                # Show comparative tables
                self._show_comparative_tables(monthly_team_stats, rest_team_stats,
                                             monthly_opponent_stats, rest_opponent_stats)

            else:
                # General mode - all data
                # Check cache first
                if self._data_cache['general'] is None:
                    team_stats, opponent_stats = self.reload_callback(self.collection_name, None)
                    # Cache the loaded data
                    self._data_cache['general'] = (team_stats, opponent_stats)
                else:
                    # Use cached data
                    team_stats, opponent_stats = self._data_cache['general']

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
                comp_stat = self._create_comparative_stat(monthly, rest)
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
            self._populate_comparative_basic_row(row, stats, basic_numeric_data, basic_quartiles)

        self.basic_table.setSortingEnabled(True)

        # For advanced table, show monthly data with trend indicators
        self.advanced_table.setRowCount(0)
        self.advanced_table.setRowCount(len(comparative_stats))
        self.advanced_table.setSortingEnabled(False)

        for row, stats in enumerate(comparative_stats):
            self._populate_comparative_advanced_row(row, stats, advanced_numeric_data, advanced_quartiles, self.advanced_table)

        self.advanced_table.setSortingEnabled(True)

        # Handle opponent table if available
        if self.opponent_table and monthly_opponent_stats and rest_opponent_stats:
            monthly_opp_dict = {str(team["_id"]): team for team in monthly_opponent_stats}
            rest_opp_dict = {str(team["_id"]): team for team in rest_opponent_stats}

            comparative_opp_stats = []
            for team_id in all_team_ids:
                if team_id in monthly_opp_dict and team_id in rest_opp_dict:
                    comp_stat = self._create_comparative_stat(monthly_opp_dict[team_id], rest_opp_dict[team_id])
                    comparative_opp_stats.append(comp_stat)

            if comparative_opp_stats:
                opp_numeric_data = get_advanced_numeric_data(monthly_opponent_stats)
                opp_quartiles = {key: calculate_quartiles(values) for key, (values, _) in opp_numeric_data.items()}

                self.opponent_table.setRowCount(0)
                self.opponent_table.setRowCount(len(comparative_opp_stats))
                self.opponent_table.setSortingEnabled(False)

                for row, stats in enumerate(comparative_opp_stats):
                    self._populate_comparative_advanced_row(row, stats, opp_numeric_data, opp_quartiles, self.opponent_table)

                self.opponent_table.setSortingEnabled(True)

    def _create_comparative_stat(self, monthly: Dict, rest: Dict) -> Dict:
        """Create a comparative statistic entry with monthly, rest, and delta values."""
        comp = {
            "_id": monthly["_id"],
            "team_name": monthly["team_name"],
            "monthly": monthly,
            "rest": rest,
            "deltas": {}
        }

        # Define numeric fields to calculate deltas for
        numeric_fields = [
            "total_games", "points_scored", "points_received", "points_per_game", "points_against_per_game",
            "fg2_percentage", "fg3_percentage", "ft_percentage", "total_rebounds", "rebounds_def", "rebounds_off",
            "assists", "assists_per_game", "steals", "steals_per_game", "turnovers", "turnovers_per_game",
            "blocks", "blocks_per_game",
            "possessions_per_game", "offensive_rating", "defensive_rating", "net_rating",
            "efg_percentage", "turnover_rate", "offensive_rebound_rate", "free_throw_rate", "three_point_rate",
            "true_shooting", "assist_fg_rate", "assist_rate", "steal_rate", "block_rate",
            "defensive_rebound_rate"
        ]

        # Use TrendCalculator to compute deltas
        comp["deltas"] = self.trend_calculator.calculate_deltas(monthly, rest, numeric_fields)

        return comp

    def _populate_comparative_basic_row(self, row: int, comp_stat: Dict, numeric_data: Dict, quartiles: Dict):
        """Populate basic stats row with comparative data showing trends."""
        monthly = comp_stat["monthly"]
        rest = comp_stat["rest"]
        deltas = comp_stat["deltas"]

        # Team name
        self.basic_table.setItem(row, 0, NumericTableWidgetItem(monthly["team_name"], monthly["team_name"], False))

        # Total games (show monthly + rest)
        total_games = monthly.get("total_games", 0) + rest.get("total_games", 0)
        games_text = f"{monthly.get('total_games', 0)} + {rest.get('total_games', 0)}"
        self.basic_table.setItem(row, 1, NumericTableWidgetItem(total_games, games_text))

        # Local games (monthly + rest)
        local_games = monthly.get("games_home", 0) + rest.get("games_home", 0)
        local_text = f"{monthly.get('games_home', 0)} + {rest.get('games_home', 0)}"
        self.basic_table.setItem(row, 2, NumericTableWidgetItem(local_games, local_text))

        # Away games (monthly + rest)
        away_games = monthly.get("games_away", 0) + rest.get("games_away", 0)
        away_text = f"{monthly.get('games_away', 0)} + {rest.get('games_away', 0)}"
        self.basic_table.setItem(row, 3, NumericTableWidgetItem(away_games, away_text))

        # For other numeric columns, show monthly value with trend indicator
        basic_stats_config = get_basic_stats_config(monthly)

        for idx, key, raw_value in basic_stats_config:
            if idx < 2:  # Skip team_name and total_games
                continue

            num_value, display_value = process_numeric_value(raw_value, key)

            # Add percentage symbol first if needed
            if key in PERCENTAGE_FIELDS:
                display_value = f"{display_value}%"

            # Add trend indicator with color
            if key in deltas:
                delta = deltas[key]
                trend_symbol, trend_color = self.trend_calculator.get_trend_indicator(delta, key)

                cell_label, item = self._create_trend_cell_widget(
                    display_value, trend_symbol, trend_color, num_value,
                    key, numeric_data, quartiles
                )
                self.basic_table.setCellWidget(row, idx, cell_label)
                self.basic_table.setItem(row, idx, item)
            else:
                # No trend data available - show "—" indicator
                trend_symbol, trend_color = self.trend_calculator.get_no_data_indicator()
                cell_label, item = self._create_trend_cell_widget(
                    display_value, trend_symbol, trend_color, num_value,
                    key, numeric_data, quartiles
                )
                cell_label.setProperty("title", "Sin datos para comparar")
                self.basic_table.setCellWidget(row, idx, cell_label)
                self.basic_table.setItem(row, idx, item)

    def _create_trend_cell_widget(self, display_value: str, trend_symbol: str, trend_color: str,
                                   num_value: float, key: str, numeric_data: Dict, quartiles: Dict,
                                   reverse_flag: bool = None) -> tuple:
        """
        Create a QLabel widget with trend indicator and background color.

        Args:
            display_value: Formatted value to display
            trend_symbol: Trend symbol (↑, ↓, ≈, ⇈, ⇊, or —)
            trend_color: HTML color code for the trend symbol
            num_value: Numeric value for quartile color calculation
            key: Field key for quartile lookup
            numeric_data: Dictionary of numeric data
            quartiles: Dictionary of quartiles
            reverse_flag: Optional reverse flag override (for opponent stats)

        Returns:
            Tuple of (cell_label, table_item) ready to be set in table
        """
        cell_label = QLabel()
        cell_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Apply quartile background color if available
        bg_color = "transparent"
        if key in numeric_data and key in quartiles:
            flag = reverse_flag if reverse_flag is not None else numeric_data[key][1]
            color = get_quartile_color(float(num_value), quartiles[key], flag)
            bg_color = color.name()

        cell_label.setStyleSheet(f"background-color: {bg_color};")
        cell_label.setText(f'{display_value} <span style="color: {trend_color}; font-weight: bold;">{trend_symbol}</span>')

        # Create item for sorting purposes
        item = NumericTableWidgetItem(num_value, "")

        return cell_label, item

    def _populate_comparative_advanced_row(self, row: int, comp_stat: Dict, numeric_data: Dict,
                                          quartiles: Dict, table: QTableWidget):
        """Populate advanced stats row with comparative data showing trends."""
        monthly = comp_stat["monthly"]
        deltas = comp_stat["deltas"]

        # Determine if this is the opponent table
        is_opponent_table = table is self.opponent_table

        # Team name and games
        total_games = monthly.get("total_games", 0) + comp_stat["rest"].get("total_games", 0)
        games_text = f"{monthly.get('total_games', 0)} + {comp_stat['rest'].get('total_games', 0)}"

        table.setItem(row, 0, NumericTableWidgetItem(monthly["team_name"], monthly["team_name"], False))
        table.setItem(row, 1, NumericTableWidgetItem(total_games, games_text))

        # Get advanced stats configuration
        advanced_stats_config = get_advanced_stats_config(monthly)

        for idx, key, raw_value in advanced_stats_config:
            num_value, display_value = process_numeric_value(raw_value, key)

            # Add percentage symbol first if needed
            if key not in NON_PERCENTAGE_FIELDS:
                display_value = f"{display_value}%"

            # Add trend indicator with color
            if key in deltas:
                delta = deltas[key]
                trend_symbol, trend_color = self.trend_calculator.get_trend_indicator(delta, key, is_opponent=is_opponent_table)

                # Calculate reverse flag for opponent table
                reverse_flag = numeric_data[key][1] if key in numeric_data else None
                if is_opponent_table and reverse_flag is not None:
                    reverse_flag = not reverse_flag

                cell_label, item = self._create_trend_cell_widget(
                    display_value, trend_symbol, trend_color, num_value,
                    key, numeric_data, quartiles, reverse_flag
                )
                table.setCellWidget(row, idx, cell_label)
                table.setItem(row, idx, item)
            else:
                # No trend data available - show "—" indicator
                trend_symbol, trend_color = self.trend_calculator.get_no_data_indicator()
                reverse_flag = numeric_data[key][1] if key in numeric_data else None
                if is_opponent_table and reverse_flag is not None:
                    reverse_flag = not reverse_flag

                cell_label, item = self._create_trend_cell_widget(
                    display_value, trend_symbol, trend_color, num_value,
                    key, numeric_data, quartiles, reverse_flag
                )
                cell_label.setProperty("title", "Sin datos para comparar")
                table.setCellWidget(row, idx, cell_label)
                table.setItem(row, idx, item)


