"""Regression tests for the QFont::setPointSize warning fix in main.py.

Bug: On Windows with certain DPI configurations the default system font is
defined in pixels, causing QFont.pointSize() to return -1.  Qt's stylesheet
engine then called setPointSize(-1) internally, emitting:
    QFont::setPointSize: Point size <= 0 (-1), must be greater than 0

Root causes (two-layer fix):
1. Warning can fire INSIDE QApplication() before any Python code runs.
   Fixed by setting os.environ["QT_FONT_DPI"] = "96" before the constructor.
2. Calling setPointSize() on a pixel-based QFont does NOT clear the internal
   pixelSize flag — Qt keeps treating it as pixel-based.
   Fixed by creating a *new* QFont(family, 10) instead of mutating the old one.
"""

import os
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
# Layer 1 fix: QT_FONT_DPI env var must be set before QApplication
# ---------------------------------------------------------------------------

class TestQtFontDpiEnvVar:
    def test_qt_font_dpi_is_set_in_module(self):
        """QT_FONT_DPI must be set as a side-effect of importing src.main."""
        # The import already ran, so the env var must be present.
        assert "QT_FONT_DPI" in os.environ, (
            "QT_FONT_DPI must be set before QApplication() to prevent the "
            "warning from firing inside the Qt constructor itself."
        )

    def test_qt_font_dpi_value_is_positive_integer(self):
        """QT_FONT_DPI must be a sensible DPI value (> 0)."""
        value = os.environ.get("QT_FONT_DPI", "0")
        assert int(value) > 0
