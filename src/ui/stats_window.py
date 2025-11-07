"""Team statistics display window."""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QTableWidget, QHeaderView, QTabWidget, QPushButton,
                              QFileDialog, QMessageBox, QMenu, QTableWidgetItem, QLabel)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QPageLayout, QPageSize, QAction, QColor
from PyQt6.QtPrintSupport import QPrinter
from typing import List, Dict
import csv
from datetime import datetime

from .table_items import NumericTableWidgetItem, process_numeric_value
from .stats_config import (
    BASIC_COLUMNS, ADVANCED_COLUMNS,
    PERCENTAGE_FIELDS, ADVANCED_PERCENTAGE_FIELDS, NON_PERCENTAGE_FIELDS,
    get_basic_stats_config, get_advanced_stats_config,
    get_basic_numeric_data, get_advanced_numeric_data,
    calculate_quartiles, get_quartile_color
)
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

    def __init__(self, team_stats: List[Dict], parent=None):
        """
        Initialize the team stats window.

        Args:
            team_stats: List of team statistics dictionaries
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("MfA - Estadísticas de Equipo")
        # Set a reasonable minimum window size considering all columns
        self.setMinimumSize(1200, 600)

        # Set application icon
        set_app_icon(self)

        self.setup_ui(team_stats)

    def setup_ui(self, team_stats: List[Dict]):
        """Set up the UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create export button container
        export_layout = QHBoxLayout()
        layout.addLayout(export_layout)

        # Add single export button with menu
        self.export_button = QPushButton("� Exportar")
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
        export_layout.addWidget(self.export_button)

        # Add stretch to push button to the left
        export_layout.addStretch()

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
        advanced_layout.setSpacing(0)
        advanced_layout.setContentsMargins(0, 0, 0, 0)

        self.advanced_table = QTableWidget()
        advanced_layout.addWidget(self.advanced_table)

        # Add color legend
        legend_widget = self._create_color_legend()
        advanced_layout.addWidget(legend_widget)

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

        # Apply colors to header based on column groups
        self._apply_header_colors()

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

    def _apply_header_colors(self):
        """Apply background colors to column headers based on their groups."""
        # Apply colors to header sections using class constant
        for start_col, end_col, _, color in self.COLUMN_GROUPS:
            for col in range(start_col, end_col + 1):
                self.advanced_table.horizontalHeaderItem(col).setBackground(QColor(color))

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
        """Get the currently active table based on selected tab."""
        current_index = self.tab_widget.currentIndex()
        return self.basic_table if current_index == 0 else self.advanced_table

    def _get_current_table_name(self) -> str:
        """Get the name of the currently active table."""
        current_index = self.tab_widget.currentIndex()
        return "estadisticas_basicas" if current_index == 0 else "estadisticas_avanzadas"

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
