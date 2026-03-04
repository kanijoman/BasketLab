"""Helper for managing progress dialogs in dual player/teammate analysis."""

from PyQt6.QtWidgets import QProgressDialog, QWidget, QApplication
from PyQt6.QtCore import Qt
from typing import Callable, Tuple, Optional


class AnalysisProgressHelper:
    """Helper class for creating and managing progress dialogs in analysis windows."""
    
    @staticmethod
    def create_dual_analysis_progress(
        parent: QWidget,
        title: str,
        entity1_name: str,
        entity2_name: str
    ) -> QProgressDialog:
        """
        Create a progress dialog for dual analysis (e.g., player vs player, teammate vs teammate).
        
        Args:
            parent: Parent widget
            title: Window title for the progress dialog
            entity1_name: Name of first entity being analyzed
            entity2_name: Name of second entity being analyzed
            
        Returns:
            Configured QProgressDialog instance
        """
        progress = QProgressDialog("Cargando partidos...", None, 0, 100, parent)
        progress.setWindowTitle(title)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        progress.show()
        return progress
    
    @staticmethod
    def create_progress_callback(
        progress: QProgressDialog,
        base_percent: int,
        range_percent: int
    ) -> Callable[[int, int], None]:
        """
        Create a progress callback function for database operations.
        
        Args:
            progress: Progress dialog to update
            base_percent: Starting percentage (e.g., 10 for first entity, 50 for second)
            range_percent: Percentage range to cover (e.g., 40 to go from 10 to 50)
            
        Returns:
            Callback function compatible with db_handler progress callbacks
        """
        def update_progress(current: int, total: int):
            if total > 1:
                percent = base_percent + int(current * range_percent / total)
                progress.setValue(percent)
            QApplication.processEvents()
        
        return update_progress
    
    @staticmethod
    def update_progress_for_entity(
        progress: QProgressDialog,
        entity_name: str,
        start_percent: int
    ) -> None:
        """
        Update progress dialog for a specific entity analysis.
        
        Args:
            progress: Progress dialog to update
            entity_name: Name of entity being analyzed
            start_percent: Starting percentage value
        """
        progress.setLabelText(f"Analizando {entity_name}...")
        progress.setValue(start_percent)
        QApplication.processEvents()
    
    @staticmethod
    def create_single_analysis_progress(
        parent: QWidget,
        title: str,
        initial_message: str = "Cargando partidos desde base de datos..."
    ) -> QProgressDialog:
        """
        Create a progress dialog for single entity analysis.
        
        Args:
            parent: Parent widget
            title: Window title
            initial_message: Initial message to display
            
        Returns:
            Configured QProgressDialog instance
        """
        progress = QProgressDialog(initial_message, None, 0, 0, parent)
        progress.setWindowTitle(title)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        progress.show()
        QApplication.processEvents()
        return progress
    
    @staticmethod
    def create_single_progress_callback(
        progress: QProgressDialog
    ) -> Callable[[int, int], None]:
        """
        Create a progress callback for single entity analysis.
        
        Args:
            progress: Progress dialog to update
            
        Returns:
            Callback function for database operations
        """
        def update_progress(current: int, total: int):
            if current == 1 and total > 1:
                progress.setMaximum(100)
                progress.setLabelText(f"Analizando partidos... (0/{total})")
                progress.setValue(0)
            elif total > 1:
                percent = int(current * 100 / total)
                progress.setValue(percent)
                progress.setLabelText(f"Analizando partidos... ({current}/{total})")
            QApplication.processEvents()
        
        return update_progress
