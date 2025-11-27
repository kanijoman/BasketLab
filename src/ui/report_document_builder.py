"""
Report Document Builder - DOCX document formatting utilities.

This module provides utilities for formatting and styling DOCX documents,
including text formatting, cell styling, and border management.
"""

from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


class ReportDocumentBuilder:
    """Utilities for formatting DOCX report documents."""

    @staticmethod
    def add_formatted_text(paragraph, text: str, bold: bool = False, size: int = 11):
        """
        Add formatted text to a paragraph.

        Args:
            paragraph: docx paragraph object
            text: Text to add
            bold: Whether text should be bold
            size: Font size in points
        """
        run = paragraph.add_run(text)
        run.font.bold = bold
        run.font.size = Pt(size)

    @staticmethod
    def format_cell(cell, bold: bool = False, align=WD_ALIGN_PARAGRAPH.LEFT):
        """
        Format a table cell.

        Args:
            cell: Cell to format
            bold: Whether text should be bold
            align: Text alignment
        """
        for paragraph in cell.paragraphs:
            paragraph.alignment = align
            for run in paragraph.runs:
                run.font.bold = bold
                run.font.size = Pt(10)

    @staticmethod
    def set_cell_border(cell, **kwargs):
        """
        Set borders on a cell.

        Args:
            cell: Cell to add borders to
            **kwargs: Additional arguments for customizing borders
        """
        tc = cell._element
        tcPr = tc.get_or_add_tcPr()

        # Create border elements
        tcBorders = OxmlElement('w:tcBorders')
        for border_name in ['top', 'left', 'bottom', 'right']:
            border = OxmlElement(f'w:{border_name}')
            border.set(qn('w:val'), 'single')
            border.set(qn('w:sz'), '12')
            border.set(qn('w:space'), '0')
            border.set(qn('w:color'), '999999')
            tcBorders.append(border)

        tcPr.append(tcBorders)
