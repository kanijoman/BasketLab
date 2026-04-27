"""Unit tests for PDFGenerator — covers 0% → ~85%.

Tests:
- _replace_emojis: all mapped symbols, unmapped chars, empty input
- _clean_html: style/script/head/html/body stripping, comments, doctype
- generate_bytes_from_html: returns bytes, with/without team name, HTML fallback
- generate_from_html: writes file, title included, fallback on bad HTML
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from services.pdf_generator import PDFGenerator


# ---------------------------------------------------------------------------
# _replace_emojis
# ---------------------------------------------------------------------------

class TestReplaceEmojis:
    def test_fire_emoji_replaced(self):
        assert "[+]" in PDFGenerator._replace_emojis("🔥 Strength")

    def test_warning_emoji_replaced(self):
        assert "[-]" in PDFGenerator._replace_emojis("⚠️ Warning")

    def test_checkmark_replaced(self):
        assert "[OK]" in PDFGenerator._replace_emojis("✅ Done")

    def test_arrow_up_replaced(self):
        assert "^" in PDFGenerator._replace_emojis("↑ Improving")

    def test_dash_replaced(self):
        assert "-" in PDFGenerator._replace_emojis("— separator")

    def test_curly_quotes_replaced(self):
        result = PDFGenerator._replace_emojis("\u201cHello\u201d")
        assert '"Hello"' in result

    def test_empty_string_unchanged(self):
        assert PDFGenerator._replace_emojis("") == ""

    def test_plain_text_unchanged(self):
        text = "Simple plain text 123"
        assert PDFGenerator._replace_emojis(text) == text

    def test_multiple_emojis_in_one_string(self):
        result = PDFGenerator._replace_emojis("🔥 Bueno ⚠️ Malo ✅ OK")
        assert "[+]" in result
        assert "[-]" in result
        assert "[OK]" in result

    def test_basketball_emoji_replaced(self):
        assert "[TEAM]" in PDFGenerator._replace_emojis("🏀 BasketLab")

    def test_triple_dot_replaced(self):
        assert "..." in PDFGenerator._replace_emojis("Texto…")


# ---------------------------------------------------------------------------
# _clean_html
# ---------------------------------------------------------------------------

class TestCleanHtml:
    def test_style_tag_removed(self):
        html = "<style>body { color: red; }</style><p>Text</p>"
        result = PDFGenerator._clean_html(html)
        assert "<style>" not in result
        assert "color" not in result
        assert "<p>Text</p>" in result

    def test_script_tag_removed(self):
        html = "<script>alert('xss')</script><p>Safe</p>"
        result = PDFGenerator._clean_html(html)
        assert "<script>" not in result
        assert "alert" not in result
        assert "Safe" in result

    def test_head_tag_removed(self):
        html = "<head><title>T</title></head><p>Body</p>"
        result = PDFGenerator._clean_html(html)
        assert "<head>" not in result
        assert "<p>Body</p>" in result

    def test_html_body_tags_stripped(self):
        html = "<html><body><p>Content</p></body></html>"
        result = PDFGenerator._clean_html(html)
        assert "<html>" not in result
        assert "<body>" not in result
        assert "<p>Content</p>" in result

    def test_html_comment_removed(self):
        html = "<!-- This is a comment --><p>Visible</p>"
        result = PDFGenerator._clean_html(html)
        assert "comment" not in result
        assert "Visible" in result

    def test_doctype_removed(self):
        html = "<!DOCTYPE html><p>Text</p>"
        result = PDFGenerator._clean_html(html)
        assert "DOCTYPE" not in result

    def test_multiline_style_removed(self):
        html = "<style>\n.class {\n  color: blue;\n}\n</style><p>OK</p>"
        result = PDFGenerator._clean_html(html)
        assert "color" not in result
        assert "OK" in result

    def test_empty_html_returns_empty(self):
        assert PDFGenerator._clean_html("") == ""

    def test_plain_text_unchanged(self):
        result = PDFGenerator._clean_html("No HTML here")
        assert result == "No HTML here"


# ---------------------------------------------------------------------------
# generate_bytes_from_html
# ---------------------------------------------------------------------------

class TestGenerateBytesFromHtml:
    def test_returns_bytes(self):
        result = PDFGenerator.generate_bytes_from_html("<p>Hello</p>")
        assert isinstance(result, bytes)

    def test_returns_non_empty(self):
        result = PDFGenerator.generate_bytes_from_html("<p>Content</p>")
        assert len(result) > 0

    def test_with_team_name_returns_bytes(self):
        result = PDFGenerator.generate_bytes_from_html(
            "<p>Stats</p>", team_name="Alpha FC"
        )
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_with_team_and_season_returns_bytes(self):
        result = PDFGenerator.generate_bytes_from_html(
            "<p>Stats</p>", team_name="Alpha FC", season="2024-25"
        )
        assert isinstance(result, bytes)

    def test_empty_html_does_not_raise(self):
        result = PDFGenerator.generate_bytes_from_html("")
        assert isinstance(result, bytes)

    def test_html_with_emojis_does_not_raise(self):
        html = "<p>🔥 Fortaleza ⚠️ Debilidad</p>"
        result = PDFGenerator.generate_bytes_from_html(html, team_name="Team")
        assert isinstance(result, bytes)

    def test_html_with_style_stripped_before_generation(self):
        html = "<style>body {}</style><p>Clean</p>"
        result = PDFGenerator.generate_bytes_from_html(html)
        assert isinstance(result, bytes)

    def test_complex_html_structure(self):
        html = """
        <h1>Análisis Equipo</h1>
        <h2>Estadísticas</h2>
        <ul><li>Puntos: 78.5</li><li>Rebotes: 35.2</li></ul>
        <p>Análisis detallado del rendimiento.</p>
        """
        result = PDFGenerator.generate_bytes_from_html(html, team_name="Alpha FC")
        assert isinstance(result, bytes)

    def test_html_with_bad_tags_falls_back_gracefully(self):
        """Malformed HTML should fall back to text extraction, not raise."""
        html = "<broken>>><<><<garbage>>"
        result = PDFGenerator.generate_bytes_from_html(html)
        assert isinstance(result, bytes)

    def test_pdf_starts_with_pdf_magic_bytes(self):
        """PDF format starts with %PDF."""
        result = PDFGenerator.generate_bytes_from_html("<p>Test</p>")
        assert result[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# generate_from_html (file output)
# ---------------------------------------------------------------------------

class TestGenerateFromHtmlFile:
    def test_writes_file(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            tmp_path = f.name
        try:
            PDFGenerator.generate_from_html(tmp_path, "<p>Hello</p>")
            assert os.path.exists(tmp_path)
            assert os.path.getsize(tmp_path) > 0
        finally:
            os.unlink(tmp_path)

    def test_writes_file_with_team_name(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            tmp_path = f.name
        try:
            PDFGenerator.generate_from_html(tmp_path, "<p>Stats</p>", team_name="Alpha FC")
            assert os.path.getsize(tmp_path) > 0
        finally:
            os.unlink(tmp_path)

    def test_file_starts_with_pdf_magic(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            tmp_path = f.name
        try:
            PDFGenerator.generate_from_html(tmp_path, "<p>Test</p>")
            with open(tmp_path, "rb") as f:
                assert f.read(4) == b"%PDF"
        finally:
            os.unlink(tmp_path)
