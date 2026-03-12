"""Regression tests for the QFont::setPointSize warning fix in main.py.

Bug: On Windows with certain DPI configurations the default system font is
defined in pixels, causing QFont.pointSize() to return -1. Qt's stylesheet
engine then called setPointSize(-1) internally, emitting:
    QFont::setPointSize: Point size <= 0 (-1), must be greater than 0

Fix: _fix_app_font() normalises the QApplication font to 10pt when the
detected point size is <= 0.
"""

from unittest.mock import MagicMock

import pytest

from src.main import _fix_app_font


class TestFixAppFont:
    def test_sets_point_size_10_when_negative(self):
        """Core regression: a -1 point size must be corrected to 10."""
        font = MagicMock()
        font.pointSize.return_value = -1

        app = MagicMock()
        app.font.return_value = font

        _fix_app_font(app)

        font.setPointSize.assert_called_once_with(10)
        app.setFont.assert_called_once_with(font)

    def test_sets_point_size_10_when_zero(self):
        """0 is also invalid — must be corrected."""
        font = MagicMock()
        font.pointSize.return_value = 0

        app = MagicMock()
        app.font.return_value = font

        _fix_app_font(app)

        font.setPointSize.assert_called_once_with(10)
        app.setFont.assert_called_once_with(font)

    def test_does_not_change_valid_point_size(self):
        """A font already carrying a positive size must not be altered."""
        font = MagicMock()
        font.pointSize.return_value = 9

        app = MagicMock()
        app.font.return_value = font

        _fix_app_font(app)

        font.setPointSize.assert_not_called()
        app.setFont.assert_not_called()

    @pytest.mark.parametrize("size", [1, 8, 10, 12, 16, 72])
    def test_does_not_change_any_positive_size(self, size):
        """Any strictly positive point size must be left untouched."""
        font = MagicMock()
        font.pointSize.return_value = size

        app = MagicMock()
        app.font.return_value = font

        _fix_app_font(app)

        font.setPointSize.assert_not_called()
        app.setFont.assert_not_called()
