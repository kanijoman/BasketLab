"""Regression tests for the QFont::setPointSize warning fix in main.py.

Bug: On Windows with certain DPI configurations the default system font is
defined in pixels, causing QFont.pointSize() to return -1.  Qt's stylesheet
engine then called setPointSize(-1) internally, emitting:
    QFont::setPointSize: Point size <= 0 (-1), must be greater than 0

Root causes (two-layer fix):
1. Warning fires when the stylesheet engine converts px→pt while inheriting
   the pixel-based system font.  Fixed by setting
   QApplication.setAttribute(Qt.ApplicationAttribute.AA_Use96Dpi)
   BEFORE the QApplication constructor so every px→pt conversion uses a
   known reference DPI (96).  Note: QT_FONT_DPI has no effect in Qt 6.
2. Calling setPointSize() on a pixel-based QFont does NOT clear the internal
   pixelSize flag — Qt keeps treating it as pixel-based.
   Fixed by creating a *new* QFont(family, 10) instead of mutating the old one.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.main import _fix_app_font


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(point_size: int, family: str = "Segoe UI"):
    font = MagicMock()
    font.pointSize.return_value = point_size
    font.family.return_value = family
    app = MagicMock()
    app.font.return_value = font
    return app, font


# ---------------------------------------------------------------------------
# Core regression: pixel-based fonts must be replaced with a new QFont
# ---------------------------------------------------------------------------

class TestFixAppFont:
    def test_replaces_font_when_point_size_negative(self):
        """Core regression: pointSize -1 → new QFont(family, 10) set on app."""
        app, font = _make_app(-1, "Segoe UI")

        with patch("src.main.QFont") as MockQFont:
            new_font = MockQFont.return_value
            _fix_app_font(app)

        MockQFont.assert_called_once_with("Segoe UI", 10)
        app.setFont.assert_called_once_with(new_font)
        # Must NOT mutate the original font object
        font.setPointSize.assert_not_called()

    def test_replaces_font_when_point_size_zero(self):
        """0 is also invalid — new font must replace it."""
        app, font = _make_app(0, "Arial")

        with patch("src.main.QFont") as MockQFont:
            new_font = MockQFont.return_value
            _fix_app_font(app)

        MockQFont.assert_called_once_with("Arial", 10)
        app.setFont.assert_called_once_with(new_font)
        font.setPointSize.assert_not_called()

    def test_falls_back_to_segoe_ui_when_family_empty(self):
        """Empty family string → fallback to 'Segoe UI'."""
        app, _ = _make_app(-1, "")

        with patch("src.main.QFont") as MockQFont:
            _fix_app_font(app)

        MockQFont.assert_called_once_with("Segoe UI", 10)

    def test_does_not_touch_valid_point_size(self):
        """A font already carrying a positive size must not be altered."""
        app, font = _make_app(9)

        with patch("src.main.QFont") as MockQFont:
            _fix_app_font(app)

        MockQFont.assert_not_called()
        app.setFont.assert_not_called()
        font.setPointSize.assert_not_called()

    @pytest.mark.parametrize("size", [1, 8, 10, 12, 16, 72])
    def test_does_not_touch_any_positive_size(self, size):
        """Any strictly positive point size must be left untouched."""
        app, font = _make_app(size)

        with patch("src.main.QFont") as MockQFont:
            _fix_app_font(app)

        MockQFont.assert_not_called()
        app.setFont.assert_not_called()


# ---------------------------------------------------------------------------
# Layer 1 fix: AA_Use96Dpi ensures px→pt conversions never yield -1
# ---------------------------------------------------------------------------

class TestAA_Use96Dpi:
    def test_attribute_exists_on_qt(self):
        """AA_Use96Dpi must be a valid Qt ApplicationAttribute in Qt 6."""
        from PyQt6.QtCore import Qt
        assert hasattr(Qt.ApplicationAttribute, "AA_Use96Dpi"), (
            "Qt.ApplicationAttribute.AA_Use96Dpi must exist so it can be set "
            "before QApplication() to guarantee correct px→pt DPI resolution."
        )
