"""
make_scoresheet.py
==================
Reads a tournament schedule CSV (produced by the schedule generator) and
creates a 2-page landscape PDF scoresheet.

Layout per page
---------------
  Three side-by-side panels, each with two columns:
    Left  — match description  e.g.  M1-F5 vs M8-F3
    Right — empty box for writing the result

Usage
-----
  python make_scoresheet.py                        # uses best_matches_readable.csv
  python make_scoresheet.py my_schedule.csv        # custom input file
  python make_scoresheet.py schedule.csv out.pdf   # custom input + output file
"""

import csv
import math
import sys
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

# ── Configuration ─────────────────────────────────────────────────────────────

INPUT_CSV   = sys.argv[1] if len(sys.argv) > 1 else "best_matches_readable.csv"
OUTPUT_PDF  = sys.argv[2] if len(sys.argv) > 2 else "tournament_scoresheet.pdf"

PANELS_PER_PAGE = 3      # side-by-side panels on each page
PAGES           = 2

# Fonts
FONT_HEADER  = "Helvetica-Bold"
FONT_MATCH   = "Helvetica"
FONT_LABEL   = "Helvetica-Bold"

SIZE_HEADER  = 8
SIZE_MATCH   = 14
SIZE_LABEL   = 12

# Colours (RGB 0-1)
COL_HEADER_BG  = (0.20, 0.40, 0.70)   # dark blue
COL_HEADER_TXT = (1.0,  1.0,  1.0)    # white
COL_ALT_ROW    = (0.93, 0.96, 1.00)   # very light blue for alternating rows
COL_BORDER     = (0.50, 0.50, 0.50)   # mid-grey lines
COL_MATCH_TXT  = (0.10, 0.10, 0.10)


# ── Read & parse CSV ──────────────────────────────────────────────────────────

def parse_team(raw):
    """Convert 'M1 + F5' → 'M1-F5'."""
    parts = [p.strip() for p in raw.split("+")]
    return "-".join(parts)

matches = []
with open(INPUT_CSV, newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        desc = f"{parse_team(row['Team_A'])} vs {parse_team(row['Team_B'])}"
        matches.append(desc)

total = len(matches)
groups = PANELS_PER_PAGE * PAGES                  # 6 groups total
per_group = math.ceil(total / groups)             # matches per panel

# Pad to exact multiple so every panel is the same height
while len(matches) < groups * per_group:
    matches.append("")

panels = [matches[i * per_group:(i + 1) * per_group] for i in range(groups)]


# ── Page geometry ─────────────────────────────────────────────────────────────

PAGE_W, PAGE_H = landscape(A4)   # ≈ 841 × 595 pt

MARGIN_X = 26
MARGIN_Y = 28

PANEL_GAP  = 14                                           # horizontal gap between panels
PANEL_W    = (PAGE_W - 2*MARGIN_X - (PANELS_PER_PAGE-1)*PANEL_GAP) / PANELS_PER_PAGE

HEADER_H   = 22                                           # top header row height
ROW_H      = (PAGE_H - 2*MARGIN_Y - HEADER_H) / per_group

# Within each panel
COL_MATCH_W  = PANEL_W * 0.60
COL_RESULT_W = PANEL_W * 0.40


# ── Drawing helpers ───────────────────────────────────────────────────────────

def filled_rect(c, x, y, w, h, fill_rgb):
    c.setFillColorRGB(*fill_rgb)
    c.rect(x, y, w, h, stroke=0, fill=1)

def bordered_rect(c, x, y, w, h, line_rgb=COL_BORDER, lw=0.4):
    c.setStrokeColorRGB(*line_rgb)
    c.setLineWidth(lw)
    c.rect(x, y, w, h, stroke=1, fill=0)

def draw_text(c, text, x, y, font, size, rgb=(0,0,0), align="left"):
    c.setFont(font, size)
    c.setFillColorRGB(*rgb)
    if align == "center":
        c.drawCentredString(x, y, text)
    elif align == "right":
        c.drawRightString(x, y, text)
    else:
        c.drawString(x, y, text)


# ── Draw one panel ────────────────────────────────────────────────────────────

def draw_panel(c, panel_matches, panel_index, x0, y_top):
    """
    Draw a single panel (header + rows) with top-left corner at (x0, y_top).
    panel_index is the 0-based global panel number (used for labelling).
    """
    W  = PANEL_W
    MX = COL_MATCH_W
    RX = COL_RESULT_W

    group_start = panel_index * per_group + 1   # 1-based match number

    # ── Panel header ──────────────────────────────────────────────────────────
    header_y = y_top - HEADER_H
    filled_rect(c, x0, header_y, W, HEADER_H, COL_HEADER_BG)
    bordered_rect(c, x0, header_y, W, HEADER_H, lw=0.6)

    # Column labels inside header
    pad = 5
    draw_text(c, "Match",  x0 + pad,       header_y + HEADER_H*0.32,
              FONT_HEADER, SIZE_HEADER, COL_HEADER_TXT)
    draw_text(c, "Score",  x0 + MX + RX/2, header_y + HEADER_H*0.32,
              FONT_HEADER, SIZE_HEADER, COL_HEADER_TXT, align="center")

    # Vertical divider inside header
    c.setStrokeColorRGB(*COL_HEADER_TXT)
    c.setLineWidth(0.5)
    c.line(x0 + MX, header_y, x0 + MX, header_y + HEADER_H)

    # ── Match rows ────────────────────────────────────────────────────────────
    for i, desc in enumerate(panel_matches):
        row_y = header_y - (i + 1) * ROW_H

        # Alternating row background
        if i % 2 == 0:
            filled_rect(c, x0, row_y, W, ROW_H, COL_ALT_ROW)

        # Row border
        bordered_rect(c, x0, row_y, W, ROW_H)

        # Vertical divider between match and score columns
        c.setStrokeColorRGB(*COL_BORDER)
        c.setLineWidth(0.4)
        c.line(x0 + MX, row_y, x0 + MX, row_y + ROW_H)

        # Match number badge
        match_num = group_start + i
        badge_w = 18
        if desc:
            filled_rect(c, x0, row_y, badge_w, ROW_H, (0.75, 0.82, 0.93))
            draw_text(c, str(match_num),
                      x0 + badge_w/2, row_y + ROW_H*0.28,
                      FONT_LABEL, SIZE_LABEL, (0.15, 0.25, 0.50), align="center")

        # Match description
        if desc:
            text_x = x0 + badge_w + 4
            text_y = row_y + ROW_H * 0.28
            draw_text(c, desc, text_x, text_y, FONT_MATCH, SIZE_MATCH, COL_MATCH_TXT)


# ── Build PDF ─────────────────────────────────────────────────────────────────

c = canvas.Canvas(OUTPUT_PDF, pagesize=landscape(A4))

for page in range(PAGES):
    # Light page background
    filled_rect(c, 0, 0, PAGE_W, PAGE_H, (0.97, 0.97, 0.97))

    # Page title
    title = f"Tournament Scoresheet — Page {page + 1} of {PAGES}"
    draw_text(c, title, PAGE_W/2, PAGE_H - MARGIN_Y + 8,
              FONT_HEADER, 9, (0.25, 0.25, 0.25), align="center")

    for col in range(PANELS_PER_PAGE):
        panel_idx = page * PANELS_PER_PAGE + col
        x0 = MARGIN_X + col * (PANEL_W + PANEL_GAP)
        y_top = PAGE_H - MARGIN_Y

        draw_panel(c, panels[panel_idx], panel_idx, x0, y_top)

    c.showPage()

c.save()
print(f"Saved: {OUTPUT_PDF}  ({total} matches, {per_group} per panel, {PAGES} pages)")
