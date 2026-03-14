#!/usr/bin/env python3
"""Generate BasketLab brand assets.

Produces all graphical resources from scratch using Pillow + hand-crafted SVG.

Usage::

    python resources/generate_brand_assets.py

Outputs
-------
resources/basketlab-logo.svg     -- Primary SVG logo (icon + wordmark)
resources/BasketLab.png          -- 512x512 app icon (PNG)
resources/BasketLab.ico          -- Multi-size icon for Windows (16/32/48/256)
frontend/public/logo.png         -- 512x512 web logo (copy)
frontend/public/favicon.ico      -- Browser favicon
frontend/public/favicon.svg      -- SVG favicon (icon only)
frontend/public/og-image.png     -- Open Graph / social card (1200x630)

Design
------
Concept : basketball + data-lab (BasketLab)
Palette : #E8651A orange  |  #B5441A seam dark  |  #1A2744 navy  |  #FFFFFF white
Shape   : Navy rounded-square background + orange basketball with 3 seam curves
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit(
        "ERROR: Pillow is required.\n"
        "Install it with:  pip install Pillow"
    )

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
C_ORANGE = (232, 101, 26)      # #E8651A  basketball orange
C_SEAM   = (181, 68, 26)       # #B5441A  seam lines (20 % darker orange)
C_NAVY   = (26, 39, 68)        # #1A2744  background / text on light bg
C_WHITE  = (255, 255, 255)
C_GRAY   = (139, 160, 187)     # tagline / subtitle

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT      = Path(__file__).parent.parent
RESOURCES      = REPO_ROOT / "resources"
FRONTEND_PUB   = REPO_ROOT / "frontend" / "public"


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _quadratic_bezier(x0: float, y0: float,
                      x1: float, y1: float,
                      cx: float, cy: float,
                      steps: int = 80) -> list[tuple[float, float]]:
    """Return `steps+1` points on the quadratic Bézier from P0 → P1 via C."""
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1.0 - t
        x = u * u * x0 + 2 * u * t * cx + t * t * x1
        y = u * u * y0 + 2 * u * t * cy + t * t * y1
        pts.append((x, y))
    return pts


def _polyline(draw: ImageDraw.ImageDraw,
              pts: list[tuple[float, float]],
              color: tuple[int, int, int],
              width: int) -> None:
    """Draw a connected polyline through `pts`."""
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=color, width=width)


def _draw_basketball(draw: ImageDraw.ImageDraw,
                     cx: float, cy: float, r: float,
                     seam_w: int) -> None:
    """Draw an orange basketball centred at (cx, cy) with radius r."""
    # Filled orange circle
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=C_ORANGE)
    # Dark-orange outline
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=C_SEAM, width=seam_w)

    # Seam 1 – horizontal (bows slightly upward)
    #   from (cx-r, cy) to (cx+r, cy), control point (cx, cy - 0.28*r)
    _polyline(draw,
              _quadratic_bezier(cx - r, cy, cx + r, cy, cx, cy - r * 0.28),
              C_SEAM, seam_w)

    # Seam 2 – left arc (bows left)
    #   from (cx, cy-r) to (cx, cy+r), control point (cx - 0.42*r, cy)
    _polyline(draw,
              _quadratic_bezier(cx, cy - r, cx, cy + r, cx - r * 0.42, cy),
              C_SEAM, seam_w)

    # Seam 3 – right arc (bows right)
    #   from (cx, cy-r) to (cx, cy+r), control point (cx + 0.42*r, cy)
    _polyline(draw,
              _quadratic_bezier(cx, cy - r, cx, cy + r, cx + r * 0.42, cy),
              C_SEAM, seam_w)


# ---------------------------------------------------------------------------
# Icon factory
# ---------------------------------------------------------------------------

def make_icon(size: int) -> Image.Image:
    """Return a square RGBA icon of `size × size` pixels."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    corner = size // 5
    r  = size * 0.35
    cx = cy = size / 2

    # Navy rounded-square background
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=corner, fill=C_NAVY)

    # Basketball
    _draw_basketball(draw, cx, cy, r, max(1, size // 42))

    return img


# ---------------------------------------------------------------------------
# OG image factory  (1200 × 630)
# ---------------------------------------------------------------------------

def make_og_image() -> Image.Image:
    """Return a 1200×630 RGB Open Graph / social preview card."""
    W, H = 1200, 630
    img  = Image.new("RGB", (W, H), C_NAVY)
    draw = ImageDraw.Draw(img)

    # Basketball on the left third
    _draw_basketball(draw, 200, H / 2, 145, 9)

    # Subtle grid lines (data-lab vibe)
    grid_color = (40, 55, 85)
    for x in range(0, W, 60):
        draw.line([(x, 0), (x, H)], fill=grid_color, width=1)
    for y in range(0, H, 60):
        draw.line([(0, y), (W, y)], fill=grid_color, width=1)

    # Re-draw basketball on top of grid
    _draw_basketball(draw, 200, H / 2, 145, 9)

    # Try system fonts (Windows/macOS); fall back to Pillow's built-in
    def _font(path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for candidate in [path, "arial.ttf", "Arial.ttf",
                          "/System/Library/Fonts/Helvetica.ttc"]:
            try:
                return ImageFont.truetype(candidate, size)
            except (OSError, IOError):
                pass
        return ImageFont.load_default()

    font_title   = _font("arialbd.ttf", 100)
    font_sub     = _font("arial.ttf",    34)

    # "BasketLab" wordmark
    draw.text((390, 200), "BasketLab", fill=C_WHITE, font=font_title)
    # Tagline
    draw.text((393, 325),
              "Análisis estadístico · Ligas españolas FEB / FBCYL",
              fill=C_GRAY, font=font_sub)

    return img


# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def _svg_icon(size: int = 100) -> str:
    """Return an SVG string for the basketball icon only (no text)."""
    r  = size * 0.35
    cx = cy = size / 2
    corner = size * 0.20

    # Seam control points
    h_cy  = cy - r * 0.28       # horizontal seam control-y (bow up)
    l_cx  = cx - r * 0.42       # left arc control-x
    r_cx  = cx + r * 0.42       # right arc control-x

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}">
  <rect width="{size}" height="{size}" rx="{corner:.1f}" fill="#1A2744"/>
  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="#E8651A"/>
  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="#B5441A" stroke-width="{max(1, size // 33):.1f}"/>
  <!-- horizontal seam -->
  <path d="M {cx-r:.1f} {cy:.1f} Q {cx:.1f} {h_cy:.1f} {cx+r:.1f} {cy:.1f}" fill="none" stroke="#B5441A" stroke-width="{max(1, size // 33):.1f}"/>
  <!-- left arc seam -->
  <path d="M {cx:.1f} {cy-r:.1f} Q {l_cx:.1f} {cy:.1f} {cx:.1f} {cy+r:.1f}" fill="none" stroke="#B5441A" stroke-width="{max(1, size // 33):.1f}"/>
  <!-- right arc seam -->
  <path d="M {cx:.1f} {cy-r:.1f} Q {r_cx:.1f} {cy:.1f} {cx:.1f} {cy+r:.1f}" fill="none" stroke="#B5441A" stroke-width="{max(1, size // 33):.1f}"/>
</svg>"""


def _svg_logo() -> str:
    """Return an SVG string for the full wordmark logo (icon + 'BasketLab' text)."""
    # Canvas 480 × 120
    W, H  = 480, 120
    icon  = 100       # square icon region
    pad   = 10
    # Basketball centred in the icon region [pad, pad, pad+icon, pad+icon]
    cx = pad + icon / 2
    cy = H / 2
    r  = icon * 0.35
    corner = icon * 0.20

    h_cy = cy - r * 0.28
    l_cx = cx - r * 0.42
    r_cx = cx + r * 0.42
    sw   = max(1, icon // 33)

    text_x = pad + icon + 20

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">
  <!-- Basketball icon background -->
  <rect x="{pad}" y="{pad}" width="{icon}" height="{icon}" rx="{corner:.1f}" fill="#1A2744"/>
  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="#E8651A"/>
  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="#B5441A" stroke-width="{sw}"/>
  <path d="M {cx-r:.1f} {cy:.1f} Q {cx:.1f} {h_cy:.1f} {cx+r:.1f} {cy:.1f}" fill="none" stroke="#B5441A" stroke-width="{sw}"/>
  <path d="M {cx:.1f} {cy-r:.1f} Q {l_cx:.1f} {cy:.1f} {cx:.1f} {cy+r:.1f}" fill="none" stroke="#B5441A" stroke-width="{sw}"/>
  <path d="M {cx:.1f} {cy-r:.1f} Q {r_cx:.1f} {cy:.1f} {cx:.1f} {cy+r:.1f}" fill="none" stroke="#B5441A" stroke-width="{sw}"/>
  <!-- Wordmark -->
  <text x="{text_x}" y="70"
        font-family="system-ui,-apple-system,Segoe UI,Arial,sans-serif"
        font-size="52" font-weight="700" fill="#FFFFFF">BasketLab</text>
  <!-- Tagline -->
  <text x="{text_x + 2}" y="96"
        font-family="system-ui,-apple-system,Segoe UI,Arial,sans-serif"
        font-size="17" fill="#8BA0BB">Análisis estadístico · FEB / FBCYL</text>
</svg>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate() -> None:
    RESOURCES.mkdir(exist_ok=True)
    FRONTEND_PUB.mkdir(parents=True, exist_ok=True)

    # ── SVG files ─────────────────────────────────────────────────────────
    print("Generating SVG assets...")

    logo_svg_path = RESOURCES / "basketlab-logo.svg"
    logo_svg_path.write_text(_svg_logo(), encoding="utf-8")
    print(f"  → {logo_svg_path.relative_to(REPO_ROOT)}")

    favicon_svg_path = FRONTEND_PUB / "favicon.svg"
    favicon_svg_path.write_text(_svg_icon(100), encoding="utf-8")
    print(f"  → {favicon_svg_path.relative_to(REPO_ROOT)}")

    # ── PNG 512×512 ────────────────────────────────────────────────────────
    print("Generating BasketLab.png (512x512)...")
    icon_512 = make_icon(512)
    icon_512.save(RESOURCES / "BasketLab.png", "PNG")
    icon_512.save(FRONTEND_PUB / "logo.png", "PNG")
    print(f"  → resources/BasketLab.png")
    print(f"  → frontend/public/logo.png")

    # ── ICO (16 / 32 / 48 / 256) ──────────────────────────────────────────
    print("Generating BasketLab.ico (16/32/48/256)...")
    ico_base = make_icon(256)
    ico_base.save(
        RESOURCES / "BasketLab.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (256, 256)],
    )
    print(f"  → resources/BasketLab.ico")

    # ── Favicon ICO ────────────────────────────────────────────────────────
    print("Generating favicon.ico (16/32/48)...")
    fav_base = make_icon(48)
    fav_base.save(
        FRONTEND_PUB / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
    )
    print(f"  → frontend/public/favicon.ico")

    # ── OG image 1200×630 ─────────────────────────────────────────────────
    print("Generating og-image.png (1200x630)...")
    og = make_og_image()
    og.save(FRONTEND_PUB / "og-image.png", "PNG")
    print(f"  → frontend/public/og-image.png")

    print("\n✓ All BasketLab brand assets generated.")


if __name__ == "__main__":
    generate()
