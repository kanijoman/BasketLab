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
from PyQt6.QtGui import QPainter, QPageLayout, QPageSize, QPixmap, QFont, QFontMetrics, QColor
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

    def export_to_csv(self, table: QTableWidget, table_name: str, subtitle: str = "") -> bool:
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

                # If subtitle (e.g., selected player names) provided, write it as first line
                if subtitle:
                    # Write subtitle in a single cell, leave others blank
                    subtitle_row = [subtitle] + [""] * (table.columnCount() - 1)
                    writer.writerow(subtitle_row)
                    # Blank separator line
                    writer.writerow([""] * table.columnCount())

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

    def export_to_png(self, table: QTableWidget, table_name: str, subtitle: str = "", file_path: Optional[str] = None) -> bool:
        """
        Export table to PNG image.

        Args:
            table: Table widget to export
            table_name: Name for the file
            subtitle: Optional subtitle text
            file_path: Optional direct file path (skips dialog if provided)

        Returns:
            True if export successful, False otherwise
        """
        # Track if user selected file manually (to show confirmation dialog)
        user_selected_file = False
        
        # If no file path provided, open dialog
        if not file_path:
            user_selected_file = True
            # Include subtitle (player names) in default filename if provided
            default_name = f"{table_name}"
            if subtitle:
                # sanitize subtitle for filename: replace spaces with underscore and truncate
                safe_sub = subtitle.replace(' ', '_')[:50]
                default_name = f"{table_name}_{safe_sub}"

            file_path, _ = QFileDialog.getSaveFileName(
                self.parent,
                "Exportar PNG",
                f"{default_name}.png",
                "PNG Files (*.png)"
            )

            if not file_path:
                return False

        try:
            # For large tables, apply proper resizing before grab
            from PyQt6.QtWidgets import QHeaderView, QApplication
            from PyQt6.QtCore import QSize
            
            needs_resizing = table.rowCount() > 5 or table.columnCount() > 10
            
            if needs_resizing:
                # Save original state
                original_size = table.size()
                original_sorting = table.isSortingEnabled()
                original_h_scrollbar = table.horizontalScrollBarPolicy()
                original_v_scrollbar = table.verticalScrollBarPolicy()
                
                # Save original resize modes
                header = table.horizontalHeader()
                original_modes = []
                for i in range(table.columnCount()):
                    original_modes.append(header.sectionResizeMode(i))
                
                table.setSortingEnabled(False)
                
                # Hide scrollbars
                table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                
                # Apply ResizeToContents to all columns (same as stats_window)
                for i in range(table.columnCount()):
                    header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
                
                # Force update
                table.updateGeometry()
                QApplication.processEvents()
                
                # Calculate total width needed
                total_width = 0
                if not table.verticalHeader().isHidden():
                    total_width += table.verticalHeader().width()
                
                for i in range(table.columnCount()):
                    total_width += table.columnWidth(i)
                
                # Add minimal padding for borders and margins
                total_width += 40  # Reduced from 100
                
                # Calculate total height
                total_height = table.horizontalHeader().height()
                for i in range(table.rowCount()):
                    total_height += table.rowHeight(i)
                
                # Add minimal margin
                total_height += 40  # Reduced from 100
                
                # Only use minimum sizes if calculated size is unreasonably small
                # This handles edge cases where table hasn't fully rendered
                total_width = max(total_width, 800)  # Reasonable minimum, not excessive
                total_height = max(total_height, 300)  # Reasonable minimum, not excessive
                
                # Resize table to exact calculated size
                table.resize(QSize(total_width, total_height))
                
                # Force final update
                table.updateGeometry()
                QApplication.processEvents()
                
                # Small delay for complete rendering
                from PyQt6.QtCore import QThread
                QThread.msleep(100)
                
                # Create pixmap with exact size and render table into it
                pixmap = QPixmap(total_width, total_height)
                pixmap.fill(Qt.GlobalColor.white)
                
                painter = QPainter(pixmap)
                table.render(painter)
                painter.end()
                
                # Restore original state
                table.resize(original_size)
                table.setSortingEnabled(original_sorting)
                table.setHorizontalScrollBarPolicy(original_h_scrollbar)
                table.setVerticalScrollBarPolicy(original_v_scrollbar)
                
                # Restore original resize modes
                for i in range(min(len(original_modes), table.columnCount())):
                    header.setSectionResizeMode(i, original_modes[i])
            else:
                # Small table - just grab as is
                pixmap = table.grab()

            # If subtitle provided, create a larger pixmap and draw subtitle above the table
            if subtitle:
                # Prepare font and metrics
                font = QFont()
                font.setPointSize(12)
                metrics = QFontMetrics(font)
                padding = 12

                # Wrap subtitle into multiple lines to fit the table width (or a minimum width)
                max_text_width = max(pixmap.width() - 20, 200)

                words = subtitle.split()
                lines = []
                cur_line = ""
                for w in words:
                    test_line = (cur_line + " " + w).strip() if cur_line else w
                    if metrics.horizontalAdvance(test_line) <= max_text_width:
                        cur_line = test_line
                    else:
                        if cur_line:
                            lines.append(cur_line)
                        # If single word is longer than max, break it forcibly
                        if metrics.horizontalAdvance(w) > max_text_width:
                            # break word into chunks
                            chunk = ""
                            for ch in w:
                                if metrics.horizontalAdvance(chunk + ch) <= max_text_width:
                                    chunk += ch
                                else:
                                    if chunk:
                                        lines.append(chunk)
                                    chunk = ch
                            if chunk:
                                cur_line = chunk
                            else:
                                cur_line = ""
                        else:
                            cur_line = w

                if cur_line:
                    lines.append(cur_line)

                # Calculate text block height
                line_height = metrics.lineSpacing()
                text_block_height = line_height * len(lines) + padding

                # Determine new image dimensions
                max_line_width = max((metrics.horizontalAdvance(l) for l in lines), default=0)
                new_width = max(pixmap.width(), max_line_width + 20)
                new_height = pixmap.height() + text_block_height + padding

                new_pix = QPixmap(new_width, new_height)
                new_pix.fill(QColor(255, 255, 255))

                painter = QPainter(new_pix)
                painter.setFont(font)
                painter.setPen(QColor(0, 0, 0))

                # Draw each line
                text_x = 10
                text_y = padding + metrics.ascent()
                for i, line in enumerate(lines):
                    painter.drawText(text_x, text_y + i * line_height, line)

                # Draw table pixmap below subtitle block
                painter.drawPixmap(0, text_block_height + padding // 2, pixmap)
                painter.end()

                final_pix = new_pix
            else:
                final_pix = pixmap

            # Save to file
            if final_pix.save(file_path, "PNG"):
                # Only show confirmation dialog if user selected file manually
                if user_selected_file:
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

    def export_to_pdf(self, table: QTableWidget, table_name: str, window_title: str = "", subtitle: str = "") -> bool:
        """
        Export table to PDF document.

        Args:
            table: Table widget to export
            table_name: Name for the file
            window_title: Optional title for the document
            subtitle: Optional subtitle for the document

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

                # Add title and subtitle if provided
                y_offset = 0
                if window_title or subtitle:
                    painter.save()
                    painter.scale(1/scale, 1/scale)  # Reset scale for text

                    if window_title:
                        font = painter.font()
                        font.setPointSize(16)
                        font.setBold(True)
                        painter.setFont(font)
                        painter.drawText(50, 50, window_title)
                        y_offset = 80

                    if subtitle:
                        font = painter.font()
                        font.setPointSize(12)
                        font.setBold(False)
                        painter.setFont(font)
                        painter.drawText(50, 50 + y_offset, subtitle)
                        y_offset += 40

                    painter.restore()
                    painter.translate(0, y_offset / scale)  # Move down after title/subtitle

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

    def export_multiple_to_csv(self, tables_with_titles: list, file_name: str, subtitle: str = "") -> bool:
        """
        Export multiple tables to a single CSV file.

        Args:
            tables_with_titles: List of tuples (table_title, QTableWidget)
            file_name: Base name for the file
            subtitle: Optional subtitle

        Returns:
            True if export successful, False otherwise
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self.parent,
            "Exportar CSV",
            f"{file_name}.csv",
            "CSV Files (*.csv)"
        )

        if not file_path:
            return False

        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile, delimiter=';')

                # Write subtitle if provided
                if subtitle:
                    writer.writerow([subtitle] + [""] * 10)
                    writer.writerow([""] * 10)

                # Export each table
                for idx, (table_title, table) in enumerate(tables_with_titles):
                    # Write table title
                    writer.writerow([table_title])
                    writer.writerow([""] * table.columnCount())

                    # Write headers
                    headers = [table.horizontalHeaderItem(col).text() for col in range(table.columnCount())]
                    writer.writerow(headers)

                    # Write data rows
                    for row in range(table.rowCount()):
                        row_data = []
                        for col in range(table.columnCount()):
                            cell_widget = table.cellWidget(row, col)
                            if cell_widget:
                                import re
                                text = re.sub('<.*?>', '', cell_widget.text())
                                row_data.append(text.strip())
                            else:
                                item = table.item(row, col)
                                row_data.append(item.text() if item else "")
                        writer.writerow(row_data)

                    # Add separator between tables
                    if idx < len(tables_with_titles) - 1:
                        writer.writerow([""] * table.columnCount())
                        writer.writerow(["=" * 50])
                        writer.writerow([""] * table.columnCount())

            QMessageBox.information(
                self.parent,
                "Exportación exitosa",
                f"Tablas exportadas correctamente a:\n{file_path}"
            )
            return True

        except Exception as e:
            QMessageBox.critical(
                self.parent,
                "Error de exportación",
                f"Error al exportar CSV: {str(e)}"
            )
            return False

    def export_multiple_to_png(self, tables_with_titles: list, file_name: str, subtitle: str = "") -> bool:
        """
        Export multiple tables to a single PNG image (stacked vertically).

        Args:
            tables_with_titles: List of tuples (table_title, QTableWidget)
            file_name: Base name for the file
            subtitle: Optional subtitle

        Returns:
            True if export successful, False otherwise
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self.parent,
            "Exportar PNG",
            f"{file_name}.png",
            "PNG Files (*.png)"
        )

        if not file_path:
            return False

        try:
            from PyQt6.QtWidgets import QHeaderView, QApplication
            from PyQt6.QtCore import QRect

            # Calculate total height and max width
            total_height = 0
            max_width = 0
            title_height = 60  # Height for each title

            for table_title, table in tables_with_titles:
                # Prepare table
                table.setSortingEnabled(False)
                table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

                header = table.horizontalHeader()
                for i in range(table.columnCount()):
                    header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

                table.updateGeometry()
                QApplication.processEvents()

                # Calculate dimensions
                width = sum(table.columnWidth(i) for i in range(table.columnCount())) + 40
                height = table.horizontalHeader().height() + sum(table.rowHeight(i) for i in range(table.rowCount())) + 40

                max_width = max(max_width, width)
                total_height += title_height + height + 20  # 20px spacing

            # Create pixmap
            pixmap = QPixmap(max_width, total_height)
            pixmap.fill(Qt.GlobalColor.white)

            painter = QPainter(pixmap)
            y_offset = 10

            # Draw each table
            for table_title, table in tables_with_titles:
                # Draw title
                font = QFont()
                font.setPointSize(14)
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(20, y_offset + 30, table_title)
                y_offset += title_height

                # Draw table
                painter.translate(0, y_offset)
                table.render(painter)
                painter.translate(0, -y_offset)

                # Calculate table height
                table_height = table.horizontalHeader().height() + sum(table.rowHeight(i) for i in range(table.rowCount())) + 40
                y_offset += table_height + 20

            painter.end()

            # Save
            pixmap.save(file_path, "PNG")

            QMessageBox.information(
                self.parent,
                "Exportación exitosa",
                f"Imagen exportada correctamente a:\n{file_path}"
            )
            return True

        except Exception as e:
            QMessageBox.critical(
                self.parent,
                "Error de exportación",
                f"Error al exportar PNG: {str(e)}"
            )
            return False

    def export_multiple_to_pdf(self, tables_with_titles: list, file_name: str, window_title: str = "", subtitle: str = "") -> bool:
        """
        Export multiple tables to a single PDF document.

        Args:
            tables_with_titles: List of tuples (table_title, QTableWidget)
            file_name: Base name for the file
            window_title: Optional document title
            subtitle: Optional subtitle

        Returns:
            True if export successful, False otherwise
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self.parent,
            "Exportar PDF",
            f"{file_name}.pdf",
            "PDF Files (*.pdf)"
        )

        if not file_path:
            return False

        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(file_path)

            page_layout = QPageLayout()
            page_layout.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            page_layout.setOrientation(QPageLayout.Orientation.Landscape)
            printer.setPageLayout(page_layout)

            painter = QPainter()
            if not painter.begin(printer):
                raise Exception("No se pudo inicializar el painter")

            try:
                page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
                y_position = 50

                # Draw main title and subtitle
                if window_title:
                    font = QFont()
                    font.setPointSize(16)
                    font.setBold(True)
                    painter.setFont(font)
                    painter.drawText(50, y_position, window_title)
                    y_position += 50

                if subtitle:
                    font = QFont()
                    font.setPointSize(12)
                    painter.setFont(font)
                    painter.drawText(50, y_position, subtitle)
                    y_position += 40

                # Draw each table
                for idx, (table_title, table) in enumerate(tables_with_titles):
                    # Check if we need a new page
                    table_height = table.height()
                    if y_position + table_height > page_rect.height() and idx > 0:
                        printer.newPage()
                        y_position = 50

                    # Draw table title
                    font = QFont()
                    font.setPointSize(14)
                    font.setBold(True)
                    painter.setFont(font)
                    painter.drawText(50, y_position, table_title)
                    y_position += 40

                    # Calculate scaling for this table
                    table_width = table.width()
                    available_width = page_rect.width() - 100
                    available_height = page_rect.height() - y_position - 50

                    scale_x = available_width / table_width
                    scale_y = available_height / table_height
                    scale = min(scale_x, scale_y, 1.0) * 0.95

                    # Render table
                    painter.save()
                    painter.translate(50, y_position)
                    painter.scale(scale, scale)
                    table.render(painter)
                    painter.restore()

                    y_position += table_height * scale + 40

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
