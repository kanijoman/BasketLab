"""Statistics export functionality for various formats.

This module provides the StatsExporter class which handles exporting statistics
tables to multiple file formats:
- CSV: Comma/semicolon-separated values with proper encoding
- PNG: Image export of the table widget
- PDF: Professional PDF reports with landscape A4 format

The exporter integrates with PyQt6 table widgets and handles user file selection
and error reporting through dialogs.
"""

from PyQt6.QtWidgets import QTableWidget, QFileDialog, QMessageBox
from PyQt6.QtGui import QPainter, QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtCore import Qt
import csv
from typing import Optional


class StatsExporter:
    """Handle exporting statistics tables to various formats."""

    def __init__(self, parent_window):
        """
        Initialize exporter.

        Args:
            parent_window: Parent window for dialogs
        """
        self.parent = parent_window

    def export_to_csv(self, table: QTableWidget, table_name: str) -> bool:
        """
        Export table to CSV format.

        Args:
            table: Table widget to export
            table_name: Name for the file

        Returns:
            True if export successful, False otherwise
        """
        # Open file dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self.parent,
            "Exportar CSV",
            f"{table_name}.csv",
            "CSV Files (*.csv)"
        )

        if not file_path:
            return False

        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile, delimiter=';')

                # Write headers
                headers = []
                for col in range(table.columnCount()):
                    headers.append(table.horizontalHeaderItem(col).text())
                writer.writerow(headers)

                # Write data rows
                for row in range(table.rowCount()):
                    row_data = []
                    for col in range(table.columnCount()):
                        # Get cell widget if exists (for colored cells)
                        cell_widget = table.cellWidget(row, col)
                        if cell_widget:
                            # Extract text from QLabel, removing HTML tags
                            text = cell_widget.text()
                            # Remove HTML tags
                            import re
                            text = re.sub('<.*?>', '', text)
                            row_data.append(text.strip())
                        else:
                            # Get item text
                            item = table.item(row, col)
                            if item:
                                row_data.append(item.text())
                            else:
                                row_data.append("")
                    writer.writerow(row_data)

            QMessageBox.information(
                self.parent,
                "Exportación exitosa",
                f"Tabla exportada correctamente a:\n{file_path}"
            )
            return True

        except Exception as e:
            QMessageBox.critical(
                self.parent,
                "Error de exportación",
                f"Error al exportar CSV: {str(e)}"
            )
            return False

    def export_to_png(self, table: QTableWidget, table_name: str) -> bool:
        """
        Export table to PNG image.

        Args:
            table: Table widget to export
            table_name: Name for the file

        Returns:
            True if export successful, False otherwise
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self.parent,
            "Exportar PNG",
            f"{table_name}.png",
            "PNG Files (*.png)"
        )

        if not file_path:
            return False

        try:
            # Create pixmap with table size
            pixmap = table.grab()

            # Save to file
            if pixmap.save(file_path, "PNG"):
                QMessageBox.information(
                    self.parent,
                    "Exportación exitosa",
                    f"Imagen exportada correctamente a:\n{file_path}"
                )
                return True
            else:
                raise Exception("No se pudo guardar la imagen")

        except Exception as e:
            QMessageBox.critical(
                self.parent,
                "Error de exportación",
                f"Error al exportar PNG: {str(e)}"
            )
            return False

    def export_to_pdf(self, table: QTableWidget, table_name: str, window_title: str = "") -> bool:
        """
        Export table to PDF document.

        Args:
            table: Table widget to export
            table_name: Name for the file
            window_title: Optional title for the document

        Returns:
            True if export successful, False otherwise
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self.parent,
            "Exportar PDF",
            f"{table_name}.pdf",
            "PDF Files (*.pdf)"
        )

        if not file_path:
            return False

        try:
            # Create printer
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(file_path)

            # Set page to landscape for better table fit
            page_layout = QPageLayout()
            page_layout.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            page_layout.setOrientation(QPageLayout.Orientation.Landscape)
            printer.setPageLayout(page_layout)

            # Create painter
            painter = QPainter()
            if not painter.begin(printer):
                raise Exception("No se pudo inicializar el painter")

            try:
                # Calculate scaling
                table_width = table.width()
                table_height = table.height()
                page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)

                scale_x = page_rect.width() / table_width
                scale_y = page_rect.height() / table_height
                scale = min(scale_x, scale_y) * 0.95  # 95% to leave margins

                # Apply scaling and render
                painter.scale(scale, scale)

                # Add title if provided
                if window_title:
                    painter.save()
                    painter.scale(1/scale, 1/scale)  # Reset scale for title
                    font = painter.font()
                    font.setPointSize(16)
                    font.setBold(True)
                    painter.setFont(font)
                    painter.drawText(50, 50, window_title)
                    painter.restore()
                    painter.translate(0, 80 / scale)  # Move down after title

                table.render(painter)

            finally:
                painter.end()

            QMessageBox.information(
                self.parent,
                "Exportación exitosa",
                f"PDF exportado correctamente a:\n{file_path}"
            )
            return True

        except Exception as e:
            QMessageBox.critical(
                self.parent,
                "Error de exportación",
                f"Error al exportar PDF: {str(e)}"
            )
            return False
