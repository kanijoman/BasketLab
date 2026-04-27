"""PDF Generator — HTML to PDF conversion using fpdf2 native support.

Moved from src/ui/pdf_generator.py (Qt UI layer removed).
Used by src/api/routers/ai.py for the export-pdf endpoint.
"""

from fpdf import FPDF
import os
import tempfile
import re


class PDFGenerator:
    """Simplified PDF generator using fpdf2's native HTML support."""

    @staticmethod
    def _replace_emojis(html_content: str) -> str:
        """Replace emojis with text equivalents for PDF compatibility."""
        emoji_map = {
            '🔥': '[+]', '⚠️': '[-]', '✅': '[OK]', '❌': '[X]', '⚡': '[!]',
            '💪': '[+]', '👍': '[+]', '👎': '[-]', '📈': '[IMPROVE]', '📉': '[DECLINE]',
            '🎯': '[TARGET]', '🏀': '[TEAM]', '⚔️': '[VS]', '🛡️': '[DEF]',
            '⛹️': '[PLAYER]', '🥇': '[1st]', '🥈': '[2nd]', '🥉': '[3rd]',
            '✓': '[+]', '✔': '[+]', '✗': '[-]', '✘': '[-]',
            '○': '[ ]', '●': '[*]', '◆': '[*]', '◇': '[ ]',
            '→': '->', '←': '<-', '↑': '^', '↓': 'v', '↔': '<->',
            '①': '1.', '②': '2.', '③': '3.', '④': '4.', '⑤': '5.',
            '⑥': '6.', '⑦': '7.', '⑧': '8.', '⑨': '9.', '⑩': '10.',
            '⚠': '[!]', 'ℹ️': '[i]', 'ℹ': '[i]', '💡': '[*]', '🔔': '[!]',
            '📊': '[STATS]', '📋': '[PLAN]', '🎓': '[TRAIN]', '🏆': '[WIN]',
            '…': '...', '—': '-', '–': '-',
            '\u201c': '"', '\u201d': '"', '\u2018': "'", '\u2019': "'",
        }
        for emoji, replacement in emoji_map.items():
            html_content = html_content.replace(emoji, replacement)
        return html_content

    @staticmethod
    def _clean_html(html_content: str) -> str:
        """Remove <style>, <script>, <head> and wrapper tags before PDF conversion."""
        html_content = re.sub(
            r'<style[^>]*>.*?</style>', '', html_content,
            flags=re.DOTALL | re.IGNORECASE,
        )
        html_content = re.sub(
            r'<script[^>]*>.*?</script>', '', html_content,
            flags=re.DOTALL | re.IGNORECASE,
        )
        html_content = re.sub(
            r'<head[^>]*>.*?</head>', '', html_content,
            flags=re.DOTALL | re.IGNORECASE,
        )
        html_content = re.sub(r'</?html[^>]*>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</?body[^>]*>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<!DOCTYPE[^>]*>', '', html_content, flags=re.IGNORECASE)
        return html_content.strip()

    @staticmethod
    def generate_from_html(
        file_path: str,
        html_content: str,
        team_name: str = "",
        season: str = "",
        shot_chart_figure=None,
    ) -> None:
        """Generate PDF from HTML and write to ``file_path``."""
        html_content = PDFGenerator._clean_html(html_content)
        html_content = PDFGenerator._replace_emojis(html_content)

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        if team_name:
            pdf.set_font('Arial', 'B', 18)
            title = f"Análisis: {team_name}"
            if season:
                title += f" - {season}"
            pdf.cell(0, 10, title, 0, 1, 'C')
            pdf.ln(5)

        pdf.set_font('Arial', '', 10)
        try:
            pdf.write_html(html_content)
        except Exception:
            text = re.sub('<[^<]+?>', ' ', html_content)
            text = re.sub(r'\s+', ' ', text).strip()
            pdf.multi_cell(0, 5, text)

        if shot_chart_figure is not None:
            pdf.add_page()
            pdf.set_font('Arial', 'B', 14)
            try:
                pdf.cell(0, 10, 'Gráfico de Tiro', 0, 1, 'C')
            except UnicodeEncodeError:
                pdf.cell(0, 10, 'Shot Chart', 0, 1, 'C')
            pdf.ln(5)
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp_path = tmp.name
                shot_chart_figure.savefig(tmp_path, format='png', dpi=150, bbox_inches='tight')
            try:
                pdf.image(tmp_path, x=10, w=190)
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        pdf.output(file_path)

    @staticmethod
    def generate_bytes_from_html(
        html_content: str,
        team_name: str = "",
        season: str = "",
    ) -> bytes:
        """Generate PDF from HTML and return raw bytes (no file I/O)."""
        html_content = PDFGenerator._clean_html(html_content)
        html_content = PDFGenerator._replace_emojis(html_content)

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        if team_name:
            pdf.set_font("Arial", "B", 18)
            title = f"Análisis: {team_name}"
            if season:
                title += f" - {season}"
            pdf.cell(0, 10, title, 0, 1, "C")
            pdf.ln(5)

        pdf.set_font("Arial", "", 10)
        try:
            pdf.write_html(html_content)
        except Exception:
            text = re.sub("<[^<]+?>", " ", html_content)
            text = re.sub(r"\s+", " ", text).strip()
            pdf.multi_cell(0, 5, text)

        return bytes(pdf.output())
