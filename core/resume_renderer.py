"""Resume PDF renderer — converts Markdown to ATS-safe PDF via ReportLab.

Implements: FR-033 (PDF resume generation).

Formatting based on Jake Gutierrez resume template (gold standard):
  # Name             → 22pt bold, centered
  contact line       → 9.5pt, centered, pipe-separated
  ## Section         → 11pt bold + full-width rule below
  ### Company | Loc  → two-column: bold left, right-aligned location
  **Title** | Dates  → two-column: italic left, right-aligned dates
  - bullet           → 9.5pt, small bullet marker, indented
  **Bold**: text     → bold category prefix (skills)
  plain text         → 9.5pt body paragraph
"""

from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas

# Font constants — Helvetica for ATS compatibility
FONT_NORMAL = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"
FONT_BOLD_ITALIC = "Helvetica-BoldOblique"

# Size constants (matching Jake template: 11pt base, \small = ~9.5pt)
SIZE_NAME = 22          # \Huge
SIZE_SECTION = 11       # \large
SIZE_COMPANY = 10.5     # \normalsize (bold company/institution)
SIZE_BODY = 9.5         # \small (bullets, roles, dates, contact)

# Layout constants (matching Jake template margins)
MARGIN_LEFT = 0.47 * inch
MARGIN_RIGHT = 0.47 * inch
MARGIN_TOP = 0.4 * inch
MARGIN_BOTTOM = 0.4 * inch
CONTENT_INDENT = 0.15 * inch   # \leftmargin=0.15in for subheading lists
BULLET_INDENT = 0.30 * inch    # bullet list indentation

# Spacing constants (tight, matching Jake template vspace values)
LINE_HEIGHT = 1.15              # multiplier for line height
SECTION_SPACE_BEFORE = 7       # space before ## section header
SUBHEADING_SPACE_BEFORE = 2    # -3pt + item spacing ≈ small gap
SUBHEADING_SPACE_AFTER = 1     # -3.5pt after tabular
BULLET_SPACE_AFTER = 0.5       # -1pt after each bullet
PARAGRAPH_SPACING = 2          # blank line spacing
CONTACT_SPACE = 0              # space between name and contact line
RULE_THICKNESS = 0.6           # \titlerule thickness

# Bold pattern
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
# Italic pattern
ITALIC_RE = re.compile(r"(?<!\*)\*([^*]+?)\*(?!\*)")


def render_resume_to_pdf(resume_md_text: str, resume_pdf_path: Path) -> None:
    """Convert Markdown resume text to an ATS-safe PDF.

    Args:
        resume_md_text: Markdown-formatted resume string.
        resume_pdf_path: Output path for the PDF file.
    """
    page_width, page_height = letter
    usable_width = page_width - MARGIN_LEFT - MARGIN_RIGHT
    right_edge = page_width - MARGIN_RIGHT

    c = Canvas(str(resume_pdf_path), pagesize=letter)
    y = page_height - MARGIN_TOP

    # Track state for context-aware rendering
    after_h1 = False

    def new_page() -> float:
        c.showPage()
        return float(page_height - MARGIN_TOP)

    def check_space(needed: float) -> float:
        nonlocal y
        if y - needed < MARGIN_BOTTOM:
            y = new_page()
        return float(y)

    def text_width(text: str, font: str, size: float) -> float:
        """Measure text width, stripping markdown bold/italic markers."""
        plain = BOLD_RE.sub(r"\1", text)
        plain = ITALIC_RE.sub(r"\1", plain)
        return float(c.stringWidth(plain, font, size))

    def draw_wrapped(
        text: str, font: str, size: float, x: float, max_w: float,
    ) -> None:
        """Draw text with word wrapping and inline **bold** support."""
        nonlocal y
        lh = size * LINE_HEIGHT

        words = text.split()
        if not words:
            return

        lines: list[str] = []
        cur = ""
        for word in words:
            test = f"{cur} {word}".strip() if cur else word
            plain = BOLD_RE.sub(r"\1", test)
            plain = ITALIC_RE.sub(r"\1", plain)
            if c.stringWidth(plain, font, size) <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)

        for line in lines:
            check_space(lh)
            _draw_rich_text(c, line, font, size, x, y)
            y -= lh

    def draw_two_column(
        left: str, right: str,
        left_font: str, right_font: str,
        left_size: float, right_size: float,
        x: float,
    ) -> None:
        """Draw a two-column line: left-aligned + right-aligned."""
        nonlocal y
        lh = max(left_size, right_size) * LINE_HEIGHT
        check_space(lh)

        # Left side
        _draw_rich_text(c, left, left_font, left_size, x, y)
        # Right side
        c.setFont(right_font, right_size)
        c.drawRightString(right_edge, y, right)
        y -= lh

    # ── Parse and render ──────────────────────────────────────────────

    lines = resume_md_text.split("\n")
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        # Blank line (skip extra spacing right after name heading)
        if not stripped:
            if not after_h1:
                y -= PARAGRAPH_SPACING
            i += 1
            continue

        # Horizontal rule (---, ***, ___)
        if stripped in ("---", "***", "___"):
            i += 1
            continue

        # ── H1: Name (centered, large bold) ──
        if stripped.startswith("# ") and not stripped.startswith("## "):
            name = stripped[2:].strip()
            check_space(SIZE_NAME * LINE_HEIGHT + CONTACT_SPACE)
            c.setFont(FONT_BOLD, SIZE_NAME)
            name_w = c.stringWidth(name, FONT_BOLD, SIZE_NAME)
            c.drawString((page_width - name_w) / 2, y, name)
            y -= 14  # just clear descenders, keep contact tight
            after_h1 = True
            i += 1
            continue

        # ── Contact line (centered, right after H1) ──
        if after_h1 and not stripped.startswith("#"):
            after_h1 = False
            y -= CONTACT_SPACE
            check_space(SIZE_BODY * LINE_HEIGHT)
            c.setFont(FONT_NORMAL, SIZE_BODY)
            # Strip markdown link syntax: [text](url) → text
            contact = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", stripped)
            contact_w = c.stringWidth(contact, FONT_NORMAL, SIZE_BODY)
            c.drawString((page_width - contact_w) / 2, y, contact)
            y -= SIZE_BODY * LINE_HEIGHT
            i += 1
            continue

        after_h1 = False

        # ── H2: Section header + rule ──
        if stripped.startswith("## ") and not stripped.startswith("### "):
            heading = stripped[3:].strip().upper()
            check_space(SIZE_SECTION * LINE_HEIGHT + SECTION_SPACE_BEFORE + 6)
            y -= SECTION_SPACE_BEFORE
            c.setFont(FONT_BOLD, SIZE_SECTION)
            c.drawString(MARGIN_LEFT, y, heading)
            # Full-width rule immediately below
            rule_y = y - 3
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(RULE_THICKNESS)
            c.line(MARGIN_LEFT, rule_y, right_edge, rule_y)
            y = rule_y - 11
            i += 1
            continue

        # ── H3: Subheading (company/institution/project) ──
        if stripped.startswith("### "):
            heading = stripped[4:].strip()
            y -= SUBHEADING_SPACE_BEFORE

            # Check if pipe-separated: "Company | Location"
            if " | " in heading:
                parts = [p.strip() for p in heading.split(" | ")]
                left_part = parts[0]
                right_part = parts[-1] if len(parts) > 1 else ""
                draw_two_column(
                    left_part, right_part,
                    FONT_BOLD, FONT_NORMAL,
                    SIZE_COMPANY, SIZE_BODY,
                    MARGIN_LEFT + CONTENT_INDENT,
                )
            else:
                check_space(SIZE_COMPANY * LINE_HEIGHT)
                c.setFont(FONT_BOLD, SIZE_COMPANY)
                c.drawString(MARGIN_LEFT + CONTENT_INDENT, y, heading)
                y -= SIZE_COMPANY * LINE_HEIGHT

            # Look ahead: next line might be "**Title** | Dates" or "*Degree* | Dates"
            if i + 1 < len(lines):
                next_stripped = lines[i + 1].strip()
                # Role/degree line (not a bullet, not a header, not blank)
                if (
                    next_stripped
                    and not next_stripped.startswith("#")
                    and not next_stripped.startswith("- ")
                    and not next_stripped.startswith("* ")
                ):
                    if " | " in next_stripped:
                        role_parts = [p.strip() for p in next_stripped.split(" | ")]
                        left_part = role_parts[0]
                        right_part = role_parts[-1] if len(role_parts) > 1 else ""
                        # Strip bold markers for italic rendering
                        left_plain = BOLD_RE.sub(r"\1", left_part)
                        draw_two_column(
                            left_plain, right_part,
                            FONT_ITALIC, FONT_ITALIC,
                            SIZE_BODY, SIZE_BODY,
                            MARGIN_LEFT + CONTENT_INDENT,
                        )
                    else:
                        check_space(SIZE_BODY * LINE_HEIGHT)
                        left_plain = BOLD_RE.sub(r"\1", next_stripped)
                        c.setFont(FONT_ITALIC, SIZE_BODY)
                        c.drawString(
                            MARGIN_LEFT + CONTENT_INDENT, y, left_plain,
                        )
                        y -= SIZE_BODY * LINE_HEIGHT
                    i += 1  # consumed the look-ahead line

            y -= SUBHEADING_SPACE_AFTER
            i += 1
            continue

        # ── Bullet point ──
        if stripped.startswith("- ") or stripped.startswith("* "):
            bullet_text = stripped[2:].strip()
            check_space(SIZE_BODY * LINE_HEIGHT)

            # Small bullet marker
            bullet_x = MARGIN_LEFT + BULLET_INDENT
            text_x = bullet_x + 8  # space after bullet dot
            text_max_w = usable_width - BULLET_INDENT - 8

            # Draw bullet dot
            check_space(SIZE_BODY * LINE_HEIGHT)
            c.setFont(FONT_NORMAL, 4)
            c.drawString(bullet_x, y, "\u2022")

            draw_wrapped(bullet_text, FONT_NORMAL, SIZE_BODY, text_x, text_max_w)
            y -= BULLET_SPACE_AFTER
            i += 1
            continue

        # ── Skills line: **Category**: items ──
        if BOLD_RE.match(stripped) and ":" in stripped:
            check_space(SIZE_BODY * LINE_HEIGHT)
            bullet_x = MARGIN_LEFT + BULLET_INDENT
            c.setFont(FONT_NORMAL, 4)
            c.drawString(bullet_x, y, "\u2022")
            text_x = bullet_x + 8
            text_max_w = usable_width - BULLET_INDENT - 8
            draw_wrapped(stripped, FONT_NORMAL, SIZE_BODY, text_x, text_max_w)
            y -= BULLET_SPACE_AFTER
            i += 1
            continue

        # ── Plain body text ──
        draw_wrapped(stripped, FONT_NORMAL, SIZE_BODY, MARGIN_LEFT, usable_width)
        i += 1

    c.save()


def _draw_rich_text(
    c: Canvas, text: str, base_font: str, size: float, x: float, y: float,
) -> None:
    """Draw a single line with inline **bold** and *italic* support."""
    # First split by bold
    bold_parts = BOLD_RE.split(text)
    cursor_x = x

    for bi, bpart in enumerate(bold_parts):
        if not bpart:
            continue
        if bi % 2 == 1:
            # Bold segment
            c.setFont(FONT_BOLD, size)
            c.drawString(cursor_x, y, bpart)
            cursor_x += c.stringWidth(bpart, FONT_BOLD, size)
        else:
            # May contain *italic* spans
            italic_parts = ITALIC_RE.split(bpart)
            for ii, ipart in enumerate(italic_parts):
                if not ipart:
                    continue
                if ii % 2 == 1:
                    c.setFont(FONT_ITALIC, size)
                    c.drawString(cursor_x, y, ipart)
                    cursor_x += c.stringWidth(ipart, FONT_ITALIC, size)
                else:
                    c.setFont(base_font, size)
                    c.drawString(cursor_x, y, ipart)
                    cursor_x += c.stringWidth(ipart, base_font, size)
