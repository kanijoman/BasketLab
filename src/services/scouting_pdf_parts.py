"""Building blocks of the rival scouting PDF (issue #299): the page frame, text, tables and the zones chart.

fpdf2 with its core fonts (Helvetica, Latin-1): text is sanitised so a character outside that set becomes '?' instead of
breaking the report. The chart is drawn with matplotlib's object API (no pyplot, no global state), safe in a worker thread.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from fpdf import FPDF
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

DARK, ACCENT, SOFT, GREEN, RED, MUTED = (30, 30, 30), (50, 50, 80), (240, 240, 245), (30, 130, 70), (180, 40, 40), (110, 110, 120)


_TYPOGRAPHY = {0x201C: '"', 0x201D: '"', 0x2018: "'", 0x2019: "'", 0x2013: "-", 0x2014: "-", 0x2026: "...", 0x2192: "->", 0x2212: "-"}


def safe(text: Any) -> str:
    """A string the core fonts can write: fpdf2 encodes them as Latin-1, so typographic marks are made plain and anything else
    outside Latin-1 (emoji, arrows) becomes '?'."""
    return str(text).translate(_TYPOGRAPHY).encode("latin-1", errors="replace").decode("latin-1")


class ScoutingPDF(FPDF):
    def __init__(self, title: str, subtitle: str = "") -> None:
        super().__init__()
        self.title_text, self.subtitle = safe(title), safe(subtitle)
        self.set_auto_page_break(True, 16)
        self.set_margins(12, 12, 12)

    def header(self) -> None:
        self.set_fill_color(*DARK)
        self.rect(0, 0, 210, 14, "F")
        self.set_y(3)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 8, self.title_text, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*DARK)
        self.set_y(18)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        stamp = datetime.now().strftime("%d/%m/%Y")
        self.cell(0, 6, safe(f"BasketLab | {self.subtitle + ' | ' if self.subtitle else ''}Generado el {stamp} | Pag. {self.page_no()}"), align="C")
        self.set_text_color(*DARK)

    # -- text ------------------------------------------------------------------------------------------------------------

    def h1(self, text: str) -> None:
        self.set_font("Helvetica", "B", 18)
        self.multi_cell(0, 9, safe(text), new_x="LMARGIN", new_y="NEXT")

    def ensure_space(self, height: float) -> None:
        """Start a new page when less than ``height`` mm are left (a heading must not be left alone at the bottom)."""
        if self.get_y() + height > self.h - self.b_margin:
            self.add_page()

    def h2(self, text: str, keep_with: float = 35) -> None:
        self.ensure_space(keep_with)
        self.ln(3)
        self.set_fill_color(*ACCENT)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 7, safe(" " + text), fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*DARK)
        self.ln(1.5)

    def para(self, text: str, size: int = 10, bold: bool = False, color: Sequence[int] = DARK) -> None:
        self.set_font("Helvetica", "B" if bold else "", size)
        self.set_text_color(*color)
        self.multi_cell(0, 5, safe(text), new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*DARK)

    def bullet(self, text: str, tag: str = "", size: int = 10) -> None:
        self.set_x(14)
        self.set_font("Helvetica", "B", size)
        self.cell(4, 5, "-")
        if tag:
            self.set_text_color(*ACCENT)
            self.cell(self.get_string_width(safe(tag)) + 3, 5, safe(tag))
            self.set_text_color(*DARK)
        self.set_font("Helvetica", "", size)
        self.multi_cell(0, 5, safe(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(0.8)

    # -- tables ------------------------------------------------------------------------------------------------------------

    def table(self, headers: Sequence[str], rows: Sequence[Sequence[Any]], widths: Sequence[float], aligns: Optional[Sequence[str]] = None,
              colors: Optional[Sequence[Sequence[Optional[Sequence[int]]]]] = None) -> None:
        aligns = aligns or ["L"] + ["R"] * (len(headers) - 1)
        self.set_font("Helvetica", "B", 8.5)
        self.set_fill_color(*ACCENT)
        self.set_text_color(255, 255, 255)
        for head, w, al in zip(headers, widths, aligns):
            self.cell(w, 6, safe(head), border=1, align=al, fill=True)
        self.ln()
        self.set_text_color(*DARK)
        self.set_font("Helvetica", "", 8.5)
        for i, row in enumerate(rows):
            if self.get_y() > 270:
                self.add_page()
            self.set_fill_color(*(SOFT if i % 2 else (255, 255, 255)))
            for j, (value, w, al) in enumerate(zip(row, widths, aligns)):
                color = colors[i][j] if colors and colors[i][j] else DARK
                self.set_text_color(*color)
                self.cell(w, 5.5, self._fit(safe(value), w), border=1, align=al, fill=True)
            self.ln()
            self.set_text_color(*DARK)

    def _fit(self, text: str, width: float) -> str:
        while text and self.get_string_width(text) > width - 2:
            text = text[:-1]
        return text

    def image_bytes(self, png: bytes, width: float = 180) -> None:
        self.image(io.BytesIO(png), x=self.l_margin, w=width)
        self.ln(2)


def zones_chart(rows: Sequence[Dict[str, Any]], team: str) -> Optional[bytes]:
    """Horizontal bars: field goal % of the team, of what it concedes, and the league mark, per zone (most shots first)."""
    shown = [r for r in rows if r.get("own_fg_pct") is not None or r.get("conceded_fg_pct") is not None][:10]
    if not shown:
        return None
    fig = Figure(figsize=(7.2, 0.45 * len(shown) + 1.1), dpi=130)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ys = list(range(len(shown)))[::-1]
    h = 0.34
    own = [r["own_fg_pct"] or 0 for r in shown]
    conc = [r["conceded_fg_pct"] or 0 for r in shown]
    ax.barh([y + h / 2 for y in ys], own, height=h, color="#3b5b92", label=f"{safe(team)}: tiros propios")
    ax.barh([y - h / 2 for y in ys], conc, height=h, color="#d98c3d", label="Tiros que concede")
    for y, r in zip(ys, shown):
        if r.get("league_fg_pct") is not None:
            ax.plot([r["league_fg_pct"]] * 2, [y - 0.45, y + 0.45], color="black", linewidth=1.6)
    ax.plot([], [], color="black", linewidth=1.6, label="Liga")
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{r['label']} ({r['own_fga']})" for r in shown], fontsize=8)
    ax.set_xlabel("% de acierto", fontsize=8)
    ax.tick_params(axis="x", labelsize=8)
    ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3, frameon=False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    return buf.getvalue()
