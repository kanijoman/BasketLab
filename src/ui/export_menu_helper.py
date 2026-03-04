"""Helper for creating export menus in analysis windows."""

from PyQt6.QtWidgets import QMenu, QMessageBox, QWidget, QPushButton
from typing import Optional


class ExportMenuHelper:
    """Helper class to create and handle export menus consistently."""
    
    @staticmethod
    def show_export_menu(
        parent: QWidget,
        button: QPushButton,
        exporter,
        table,
        table_name: str,
        subtitle: str
    ) -> None:
        """
        Show export menu and handle export action.
        
        Args:
            parent: Parent widget for message boxes
            button: Button that triggered the menu
            exporter: StatsExporter instance
            table: QTableWidget to export
            table_name: Name for the exported file
            subtitle: Subtitle for the export
        """
        if not exporter:
            QMessageBox.warning(
                parent, 
                "Sin datos", 
                "No hay datos para exportar. Ejecuta el cálculo primero."
            )
            return
        
        # Create menu
        menu = QMenu(parent)
        csv_action = menu.addAction("💾 Exportar a CSV")
        png_action = menu.addAction("🖼️ Exportar a PNG")
        pdf_action = menu.addAction("📄 Exportar a PDF")
        
        # Show menu and get selected action
        action = menu.exec(button.mapToGlobal(button.rect().bottomLeft()))
        
        # Execute export based on selection
        if action == csv_action:
            exporter.export_to_csv(table, table_name, subtitle)
        elif action == png_action:
            exporter.export_to_png(table, table_name, subtitle)
        elif action == pdf_action:
            exporter.export_to_pdf(table, table_name, subtitle)
