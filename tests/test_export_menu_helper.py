"""Tests for ExportMenuHelper."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from PyQt6.QtWidgets import QWidget, QPushButton, QTableWidget, QMessageBox
from src.ui.export_menu_helper import ExportMenuHelper


class TestExportMenuHelper:
    """Test cases for ExportMenuHelper class."""
    
    def test_show_export_menu_warns_if_no_exporter(self, qtbot):
        """Test that warning is shown if exporter is None."""
        parent = QWidget()
        button = QPushButton()
        qtbot.addWidget(parent)
        qtbot.addWidget(button)
        
        with patch.object(QMessageBox, 'warning') as mock_warning:
            ExportMenuHelper.show_export_menu(
                parent, button, None, None, "test", "Test"
            )
            
            mock_warning.assert_called_once()
            args = mock_warning.call_args[0]
            assert "Sin datos" in args[1]
    
    def test_show_export_menu_creates_menu_with_exporter(self, qtbot):
        """Test that menu is created when exporter exists."""
        parent = QWidget()
        button = QPushButton()
        table = QTableWidget()
        exporter = Mock()
        qtbot.addWidget(parent)
        qtbot.addWidget(button)
        qtbot.addWidget(table)
        
        with patch('src.ui.export_menu_helper.QMenu') as mock_menu_class:
            mock_menu = MagicMock()
            mock_menu_class.return_value = mock_menu
            mock_menu.exec.return_value = None  # User cancels
            
            ExportMenuHelper.show_export_menu(
                parent, button, exporter, table, "test_name", "Test Subtitle"
            )
            
            # Verify menu was created
            mock_menu_class.assert_called_once_with(parent)
            # Verify actions were added
            assert mock_menu.addAction.call_count == 3
    
    def test_show_export_menu_calls_csv_export(self, qtbot):
        """Test that CSV export is called when CSV action is selected."""
        parent = QWidget()
        button = QPushButton()
        table = QTableWidget()
        exporter = Mock()
        qtbot.addWidget(parent)
        qtbot.addWidget(button)
        qtbot.addWidget(table)
        
        with patch('src.ui.export_menu_helper.QMenu') as mock_menu_class:
            mock_menu = MagicMock()
            mock_menu_class.return_value = mock_menu
            
            # Simulate CSV action selection
            csv_action = Mock()
            mock_menu.addAction.side_effect = [csv_action, Mock(), Mock()]
            mock_menu.exec.return_value = csv_action
            
            ExportMenuHelper.show_export_menu(
                parent, button, exporter, table, "test_name", "Test Subtitle"
            )
            
            # Verify CSV export was called
            exporter.export_to_csv.assert_called_once_with(
                table, "test_name", "Test Subtitle"
            )
    
    def test_show_export_menu_calls_png_export(self, qtbot):
        """Test that PNG export is called when PNG action is selected."""
        parent = QWidget()
        button = QPushButton()
        table = QTableWidget()
        exporter = Mock()
        qtbot.addWidget(parent)
        qtbot.addWidget(button)
        qtbot.addWidget(table)
        
        with patch('src.ui.export_menu_helper.QMenu') as mock_menu_class:
            mock_menu = MagicMock()
            mock_menu_class.return_value = mock_menu
            
            # Simulate PNG action selection
            png_action = Mock()
            mock_menu.addAction.side_effect = [Mock(), png_action, Mock()]
            mock_menu.exec.return_value = png_action
            
            ExportMenuHelper.show_export_menu(
                parent, button, exporter, table, "test_name", "Test Subtitle"
            )
            
            # Verify PNG export was called
            exporter.export_to_png.assert_called_once_with(
                table, "test_name", "Test Subtitle"
            )
    
    def test_show_export_menu_calls_pdf_export(self, qtbot):
        """Test that PDF export is called when PDF action is selected."""
        parent = QWidget()
        button = QPushButton()
        table = QTableWidget()
        exporter = Mock()
        qtbot.addWidget(parent)
        qtbot.addWidget(button)
        qtbot.addWidget(table)
        
        with patch('src.ui.export_menu_helper.QMenu') as mock_menu_class:
            mock_menu = MagicMock()
            mock_menu_class.return_value = mock_menu
            
            # Simulate PDF action selection
            pdf_action = Mock()
            mock_menu.addAction.side_effect = [Mock(), Mock(), pdf_action]
            mock_menu.exec.return_value = pdf_action
            
            ExportMenuHelper.show_export_menu(
                parent, button, exporter, table, "test_name", "Test Subtitle"
            )
            
            # Verify PDF export was called
            exporter.export_to_pdf.assert_called_once_with(
                table, "test_name", "Test Subtitle"
            )
    
    def test_show_export_menu_handles_cancel(self, qtbot):
        """Test that no export is called when user cancels."""
        parent = QWidget()
        button = QPushButton()
        table = QTableWidget()
        exporter = Mock()
        qtbot.addWidget(parent)
        qtbot.addWidget(button)
        qtbot.addWidget(table)
        
        with patch('src.ui.export_menu_helper.QMenu') as mock_menu_class:
            mock_menu = MagicMock()
            mock_menu_class.return_value = mock_menu
            mock_menu.exec.return_value = None  # User cancels
            
            ExportMenuHelper.show_export_menu(
                parent, button, exporter, table, "test_name", "Test Subtitle"
            )
            
            # Verify no export was called
            exporter.export_to_csv.assert_not_called()
            exporter.export_to_png.assert_not_called()
            exporter.export_to_pdf.assert_not_called()
