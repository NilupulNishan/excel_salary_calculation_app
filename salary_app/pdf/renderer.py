"""The payslip layout.

Airy and rule-light, with brand cyan as an accent only: it appears as rules,
bars and a tinted panel, never as text. That is deliberate -- cyan is 1.85:1 on
white and unreadable as type -- and it means nothing is lost when the page
prints in mono, where structure still comes from weight, spacing and bands.

Every size on this page comes from `theme`'s six-role scale, and every colour
from `theme.PALETTE`. Nothing here carries a raw number or a hex value: the
page previously held thirteen type sizes, four of which were doing the same job
because each call site picked its own.

Every value is drawn as a **text object**, never an image. The exported PDF is
selectable, copyable and machine-extractable; `tests/test_renderer.py` asserts
that by reading the values back out of a generated file.

Layout is measured from the top of the page via `theme.Canvas.y`, so the
numbers below read the way the page does.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.pdfgen import canvas as rl_canvas

from ..config import COMPANY, CURRENCY_CODE
from ..models import Payslip
from .theme import (
    BAND, BAND_DEEP, BAND_PAD, BAND_RADIUS, BODY, BRAND_CYAN, BRAND_DEEP,
    DISPLAY, FIGURE, FINE, INK, INK_SOFT, LEAD, MARGIN, PAGE_H, PAGE_W,
    ROW_PAD, RULE, SPACE_LG, SPACE_MD, SPACE_SM, SPACE_XL, Canvas,
    register_fonts,
)

CONTENT_W = PAGE_W - 2 * MARGIN
RIGHT = PAGE_W - MARGIN
GUTTER = SPACE_LG
COL_W = (CONTENT_W - GUTTER) / 2
COL_RIGHT_X = MARGIN + COL_W + GUTTER

#: Distance between the two column axes. The employee strip uses this too, so
#: its two fields sit on the same rhythm as the breakdown beneath them -- they
#: previously sat at an arbitrary MARGIN + 300, which was 33pt off the grid.
COL_PITCH = COL_W + GUTTER

# --- letterhead geometry --------------------------------------------------
# Named rather than inlined because the header is the one block where three
# elements (mark, divider, text) have to agree on the same measurements.

HEADER_TOP = MARGIN
HEADER_H = 63.0                          # depth of the company text block
LOGO_H = 40.0
LOGO_COL_W = 84.0                        # mark (~65pt wide) plus breathing room
DIVIDER_X = MARGIN + LOGO_COL_W
DETAIL_X = DIVIDER_X + 18.0
OFFICE_COL_W = (RIGHT - DETAIL_X) / 2

ROW_STEP = 15.0                          # baseline pitch inside the breakdown

#: Employee-strip metrics. Named because the band's height is computed from
#: them: a literal that disagrees with the leading used to draw the text is
#: how a wrapped job title came to spill below its band.
LABEL_ROW_TOP = 30.0                     # the DESIGNATION label's baseline
DESIGNATION_LEADING = 10.5               # line height of the wrapped title

#: (label, field). Totals are drawn separately so they can be emphasised
#: without special-casing inside the row loop.
EARNING_LINES = (
    ("Basic Salary", "basic_salary"),
    ("Travelling Allowance", "travelling_allowance"),
    ("Attendance Allowance", "attendance_allowance"),
    ("Other Allowances", "other_allowances"),
    ("Over Time", "over_time"),
)
DEDUCTION_LINES = (
    ("No Pay", "no_pay"),
    ("APIT Tax", "apit_tax"),
    ("Salary Advance", "salary_advance"),
    ("E.P.F (8%)", "epf_employee"),
)
COMPANY_LINES = (("EPF 12%", "epf_company"), ("ETF 3%", "etf_company"))

FOOTER_COPYRIGHT = "Copyright ©  2026 Softvil Technologies (Private) Limited - nilupul.ai"
FOOTER_NOTE = "Computer-generated payslip. No signature required."


def render_payslip(slip: Payslip, path: Path | str) -> Path:
    """Draw `slip` to `path` and return the path."""
    register_fonts()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    c = _new_canvas(slip, path)
    g = Canvas(c)

    top = _header(g)
    top = _title(g, slip, top)
    top = _employee_strip(g, slip, top)
    top = _breakdown(g, slip, top)
    top = _net_salary(g, slip, top)
    _company_contribution(g, slip, top)
    _footer(g)

    c.showPage()
    c.save()
    return path


def _new_canvas(slip: Payslip, path: Path):
    """Canvas with document metadata filled in.

    Metadata is part of "extractable": a tool reading the file should be able
    to tell whose payslip it is without parsing the page content.
    """
    c = rl_canvas.Canvas(str(path), pagesize=(PAGE_W, PAGE_H))
    c.setTitle(f"Pay Slip - {slip.period} - {slip.employee_name}".strip(" -"))
    c.setAuthor(COMPANY.name)
    c.setSubject(f"Salary payslip for {slip.period}")
    c.setCreator("Softvil Salary Slip App")
    return c


def _header(g: Canvas) -> float:
    """Letterhead: mark, divider, company block. Returns its bottom offset.

    Three decisions worth naming.

    **The logo is optically centred against the text block, not flush with its
    top.** A mark is a single mass; a text block is a stack of baselines whose
    visual centre sits below its first line. Flushing their tops leaves the
    mark looking like it has slipped upward even though both start on the same
    coordinate.

    **A divider rule instead of pushing the text to the right margin.** Right-
    aligning the company details left a wide unexplained gap mid-header and gave
    the two blocks no shared edge. A hairline supplies the edge and lets both
    offices be set left-aligned, which is how addresses are read.

    **Both offices print.** `config.COMPANY` declares two; an earlier header
    showed `offices[0]` only, so the Development Center silently disappeared
    from every slip.
    """
    top = HEADER_TOP
    g.logo(MARGIN, top + (HEADER_H - LOGO_H) / 2, LOGO_H)
    g.vrule(DIVIDER_X, top + 1, top + HEADER_H)

    g.text(DETAIL_X, top + 9, COMPANY.name, "Sans-Bold", LEAD, INK)
    for column, (office, lines) in enumerate(COMPANY.offices[:2]):
        x = DETAIL_X + column * OFFICE_COL_W
        g.micro(x, top + 26, office.upper(), BRAND_DEEP)
        for index, line in enumerate(lines[:2]):
            g.text(x, top + 36 + index * 9.5, line, "Sans", FINE, INK_SOFT)
    g.text(DETAIL_X, top + 60, f"{COMPANY.phone}     {COMPANY.website}",
           "Sans", FINE, INK_SOFT)
    return top + HEADER_H


def _title(g: Canvas, slip: Payslip, top: float) -> float:
    """Document title and period, over a short accent rule."""
    top += SPACE_XL
    g.text(MARGIN, top, "Payslip", "Sans-Light", DISPLAY, INK)
    g.text(MARGIN, top + 18, slip.period, "Sans", LEAD, BRAND_DEEP)
    g.box(MARGIN, top + 28, 52, 3, fill=BRAND_CYAN)
    return top + 58


def _employee_strip(g: Canvas, slip: Payslip, top: float) -> float:
    """Employee identity, on the page's column grid.

    Two fixes live here.

    **The second column sits one COL_PITCH from the first**, so Employee and
    Emp No share the rhythm of the Earnings/Deductions columns below. It was
    previously `MARGIN + 300` -- an arbitrary number, and 33pt off the grid.

    **The band is sized from the wrapped designation**, not fixed at 62pt. A
    job title long enough to wrap put its second line below the band's bottom
    edge; today's titles happen to fit on one line, so it never showed.
    """
    label_x = (MARGIN + BAND_PAD, MARGIN + BAND_PAD + COL_PITCH)
    text_w = CONTENT_W - 2 * BAND_PAD

    # DESIGNATION_LEADING is used to size the band AND to draw the text, so
    # the two cannot drift apart. They were two separate 10.5 literals, which
    # is how the band came to be too short for a wrapped title in the first
    # place.
    lines = g.wrap_lines(slip.designation, text_w, "Sans", BODY)
    designation_top = LABEL_ROW_TOP + SPACE_MD - 2
    band_h = (designation_top
              + max(len(lines), 1) * DESIGNATION_LEADING
              + SPACE_SM)
    g.box(MARGIN, top - BAND_PAD, CONTENT_W, band_h, fill=BAND,
          radius=BAND_RADIUS)

    row_one = (("EMPLOYEE", slip.employee_name), ("EMP NO", slip.employee_number))
    for x, (label, value) in zip(label_x, row_one):
        g.micro(x, top, label)
        g.text(x, top + 13, value, "Sans", LEAD, INK)

    g.micro(label_x[0], top + LABEL_ROW_TOP, "DESIGNATION")
    g.wrapped(label_x[0], top + designation_top, slip.designation, text_w,
              "Sans", BODY, INK, leading=DESIGNATION_LEADING)
    return top - BAND_PAD + band_h + SPACE_LG


def _breakdown(g: Canvas, slip: Payslip, top: float) -> float:
    """Earnings and deductions, side by side with no dividing rule."""
    rows = max(len(EARNING_LINES), len(DEDUCTION_LINES))
    left = _column(g, MARGIN, top, "EARNINGS", EARNING_LINES, slip,
                   "Gross Pay", "gross_pay", pad_to=rows)
    right = _column(g, COL_RIGHT_X, top, "DEDUCTIONS", DEDUCTION_LINES, slip,
                    "Total Deduction", "total_deduction", pad_to=rows)
    return max(left, right)


def _column(g, x, top, heading, lines, slip, total_label, total_field,
            pad_to: int = 0) -> float:
    """One side of the breakdown. Returns its bottom offset.

    `pad_to` keeps both columns the same number of rows so Gross Pay and Total
    Deduction land on one line -- five earnings against four deductions would
    otherwise leave the two totals at different heights.

    Rows and their total share BODY; the weight separates them, which is what
    was already doing the work when the two sizes were 8.4 and 8.6.
    """
    g.micro(x, top, heading)
    g.box(x, top + 6, COL_W, 1.2, fill=BRAND_CYAN)

    y = top + SPACE_LG
    for index in range(max(len(lines), pad_to)):
        if index < len(lines):
            # Band only real rows. Striping a padding row draws an empty grey
            # bar that reads as a line whose value failed to render.
            if index % 2 == 0:
                g.box(x, y - 9, COL_W, ROW_STEP, fill=BAND)
            label, field = lines[index]
            g.text(x + ROW_PAD, y, label, "Sans", BODY, INK)
            g.text(x + COL_W - ROW_PAD, y, slip.display(field), "Sans", BODY,
                   INK, align="right")
        y += ROW_STEP

    y += 6
    g.rule(x, y - 9, x + COL_W, RULE)
    g.text(x + ROW_PAD, y, total_label, "Sans-Bold", BODY, INK)
    g.text(x + COL_W - ROW_PAD, y, slip.display(total_field), "Sans-Bold",
           BODY, INK, align="right")
    return y


def _net_salary(g: Canvas, slip: Payslip, top: float) -> float:
    """The figure the employee actually looks for, given the most weight."""
    top += SPACE_LG + 4
    g.box(MARGIN, top - 16, CONTENT_W, 52, fill=BAND_DEEP, radius=BAND_RADIUS)
    g.box(MARGIN, top - 16, 3, 52, fill=BRAND_CYAN)
    g.micro(MARGIN + BAND_PAD, top, "NET SALARY")
    g.text(MARGIN + BAND_PAD, top + 18, slip.display("net_salary"),
           "Sans-Bold", FIGURE, INK)
    g.text(RIGHT - BAND_PAD, top + 18, CURRENCY_CODE, "Sans", FINE, INK_SOFT,
           align="right")
    g.text(MARGIN + BAND_PAD, top + 31, slip.amount_in_words, "Sans", FINE,
           INK_SOFT)
    return top + 62


def _company_contribution(g: Canvas, slip: Payslip, top: float) -> None:
    """Employer-side figures, aligned to the same two columns as the breakdown."""
    g.micro(MARGIN, top, "COMPANY CONTRIBUTION")
    top += SPACE_MD
    for x, (label, field) in zip((MARGIN, COL_RIGHT_X), COMPANY_LINES):
        g.text(x, top, label, "Sans", BODY, INK_SOFT)
        g.text(x, top + 13, slip.display(field), "Sans-Bold", LEAD, INK)


def _footer(g: Canvas) -> None:
    """Copyright left, generated-document note right, on one baseline."""
    foot = PAGE_H - 48
    g.rule(MARGIN, foot - 12, RIGHT, RULE)
    g.text(MARGIN, foot, FOOTER_COPYRIGHT, "Sans", FINE, INK_SOFT)
    g.text(RIGHT, foot, FOOTER_NOTE, "Sans", FINE, INK_SOFT, align="right")
