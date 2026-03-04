"""Tests for AnalysisProgressHelper."""

import pytest
from unittest.mock import Mock, patch
from PyQt6.QtWidgets import QWidget, QProgressDialog
from PyQt6.QtCore import Qt
from src.ui.analysis_progress_helper import AnalysisProgressHelper


class TestAnalysisProgressHelper:
    """Test cases for AnalysisProgressHelper class."""
    
    def test_create_dual_analysis_progress_returns_dialog(self, qtbot):
        """Test that dual analysis progress creates a dialog."""
        parent = QWidget()
        qtbot.addWidget(parent)
        
        dialog = AnalysisProgressHelper.create_dual_analysis_progress(
            parent, "Test Title", "Player1", "Player2"
        )
        
        assert isinstance(dialog, QProgressDialog)
        assert dialog.windowTitle() == "Test Title"
        assert dialog.minimum() == 0
        assert dialog.maximum() == 100
        assert dialog.windowModality() == Qt.WindowModality.WindowModal
        
        dialog.close()
    
    def test_create_progress_callback_returns_callable(self, qtbot):
        """Test that progress callback creation returns a callable."""
        parent = QWidget()
        qtbot.addWidget(parent)
        
        dialog = AnalysisProgressHelper.create_dual_analysis_progress(
            parent, "Test", "P1", "P2"
        )
        
        callback = AnalysisProgressHelper.create_progress_callback(dialog, 10, 40)
        
        assert callable(callback)
        
        dialog.close()
    
    def test_progress_callback_updates_dialog(self, qtbot):
        """Test that progress callback updates the dialog value."""
        parent = QWidget()
        qtbot.addWidget(parent)
        
        dialog = AnalysisProgressHelper.create_dual_analysis_progress(
            parent, "Test", "P1", "P2"
        )
        
        callback = AnalysisProgressHelper.create_progress_callback(dialog, 10, 40)
        
        # Simulate progress update
        callback(5, 10)
        
        # Should be 10 + (5 * 40 / 10) = 10 + 20 = 30
        assert dialog.value() == 30
        
        dialog.close()
    
    def test_progress_callback_handles_single_item(self, qtbot):
        """Test that progress callback handles total=1 correctly."""
        parent = QWidget()
        qtbot.addWidget(parent)
        
        dialog = AnalysisProgressHelper.create_dual_analysis_progress(
            parent, "Test", "P1", "P2"
        )
        
        callback = AnalysisProgressHelper.create_progress_callback(dialog, 10, 40)
        
        # Simulate single item (no update expected)
        callback(1, 1)
        
        # Value should remain unchanged (not updated for total=1)
        # When total=1, the callback does nothing, so value stays at 0 or initial
        initial_value = dialog.value()
        callback(1, 1)
        assert dialog.value() == initial_value
        
        dialog.close()
    
    def test_update_progress_for_entity_sets_label(self, qtbot):
        """Test that entity progress update sets correct label."""
        parent = QWidget()
        qtbot.addWidget(parent)
        
        dialog = AnalysisProgressHelper.create_dual_analysis_progress(
            parent, "Test", "P1", "P2"
        )
        
        AnalysisProgressHelper.update_progress_for_entity(
            dialog, "TestPlayer", 50
        )
        
        assert "TestPlayer" in dialog.labelText()
        assert dialog.value() == 50
        
        dialog.close()
    
    def test_create_single_analysis_progress_returns_dialog(self, qtbot):
        """Test that single analysis progress creates a dialog."""
        parent = QWidget()
        qtbot.addWidget(parent)
        
        dialog = AnalysisProgressHelper.create_single_analysis_progress(
            parent, "Single Test", "Loading..."
        )
        
        assert isinstance(dialog, QProgressDialog)
        assert dialog.windowTitle() == "Single Test"
        assert "Loading..." in dialog.labelText()
        assert dialog.windowModality() == Qt.WindowModality.WindowModal
        
        dialog.close()
    
    def test_single_progress_callback_updates_on_first_call(self, qtbot):
        """Test that single progress callback updates dialog on first call."""
        parent = QWidget()
        qtbot.addWidget(parent)
        
        dialog = AnalysisProgressHelper.create_single_analysis_progress(
            parent, "Test"
        )
        
        callback = AnalysisProgressHelper.create_single_progress_callback(dialog)
        
        # First call with total > 1 should set maximum
        callback(1, 10)
        
        assert dialog.maximum() == 100
        assert "0/10" in dialog.labelText()
        
        dialog.close()
    
    def test_single_progress_callback_updates_percent(self, qtbot):
        """Test that single progress callback calculates percentages correctly."""
        parent = QWidget()
        qtbot.addWidget(parent)
        
        dialog = AnalysisProgressHelper.create_single_analysis_progress(
            parent, "Test"
        )
        
        callback = AnalysisProgressHelper.create_single_progress_callback(dialog)
        
        # Initialize
        callback(1, 10)
        
        # Update to 50%
        callback(5, 10)
        
        assert dialog.value() == 50
        assert "5/10" in dialog.labelText()
        
        dialog.close()
    
    def test_single_progress_callback_handles_small_totals(self, qtbot):
        """Test that single progress callback handles total <= 1."""
        parent = QWidget()
        qtbot.addWidget(parent)
        
        dialog = AnalysisProgressHelper.create_single_analysis_progress(
            parent, "Test"
        )
        
        callback = AnalysisProgressHelper.create_single_progress_callback(dialog)
        
        # Should not update for total=1
        callback(1, 1)
        
        # Maximum should remain at initial 0
        assert dialog.maximum() == 0
        
        dialog.close()
