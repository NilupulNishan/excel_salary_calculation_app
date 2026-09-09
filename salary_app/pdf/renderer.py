"""The payslip layout.

One design, chosen from three candidates on 2026-09-09: airy, rule-light, with
brand cyan used only as an accent. Cyan never carries meaning on its own, so
nothing is lost when the page is printed in mono -- structure comes from bands,
weight and spacing, which survive a laser printer.

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
    BAND, BAND_DEEP, BRAND_CYAN, BRAND_DEEP, INK, INK_SOFT, MARGIN,
    PAGE_H, PAGE_W, RULE, Canvas, register_fonts,
)

CONTENT_W = PAGE_W - 2 * MARGIN
RIGHT = PAGE_W - MARGIN
GUTTER = 22.0
COL_W = (CONTENT_W - GUTTER) / 2
COL_RIGHT_X = MARGIN + COL_W + GUTTER

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

FOOTER_COPYRIGHT = "Copyright © 2026 Softvil Technologies (Private) Limited"
FOOTER_NOTE = "Computer-generated payslip. No signature required."


def render_payslip(slip: Payslip, path: Path | str) -> Path:
    """Draw `slip` to `path` and return the path."""
    register_fonts()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    c = _new_canvas(slip, path)
    g = Canvas(c)

    _header(g)
    top = _title(g, slip)
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


def _header(g: Canvas) -> None:
    """Logo left, company details right-aligned against the margin."""
    g.logo(MARGIN, MARGIN, 34)
    g.text(RIGHT, MARGIN + 8, COMPANY.name, "Sans-Bold", 9.5, INK, align="right")
    office, lines = COMPANY.offices[0]
    g.text(RIGHT, MARGIN + 20, f"{lines[0]}, {lines[1]}", "Sans", 6.8,
           INK_SOFT, align="right")
    g.text(RIGHT, MARGIN + 29, f"{COMPANY.phone}   {COMPANY.website}",
           "Sans", 6.8, INK_SOFT, align="right")


def _title(g: Canvas, slip: Payslip) -> float:
    top = 118.0
    g.text(MARGIN, top, "Payslip", "Sans-Light", 30, INK)
    g.text(MARGIN, top + 18, slip.period, "Sans", 10, BRAND_DEEP)
    g.box(MARGIN, top + 28, 52, 3, fill=BRAND_CYAN)
    return top + 58


def _employee_strip(g: Canvas, slip: Payslip, top: float) -> float:
    """Employee identity.

    Every field here is label-above-value on a shared baseline grid. An earlier
    draft put Designation's label to the *left* of its value while the other
    two were stacked, which read as a misalignment even though nothing was
    strictly out of place.
    """
    g.box(MARGIN, top - 14, CONTENT_W, 62, fill=BAND, radius=4)

    label_x = (MARGIN + 14, MARGIN + 300)
    row_one = (("EMPLOYEE", slip.employee_name), ("EMP NO", slip.employee_number))
    for x, (label, value) in zip(label_x, row_one):
        g.text(x, top, label, "Sans-Bold", 6.5, INK_SOFT)
        g.text(x, top + 13, value, "Sans", 10.5, INK)

    g.text(label_x[0], top + 30, "DESIGNATION", "Sans-Bold", 6.5, INK_SOFT)
    g.wrapped(label_x[0], top + 42, slip.designation, CONTENT_W - 28,
              "Sans", 9, INK, leading=10.5)
    return top + 82


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
    """
    g.text(x, top, heading, "Sans-Bold", 7, INK_SOFT)
    g.box(x, top + 6, COL_W, 1.2, fill=BRAND_CYAN)

    y = top + 22
    for index in range(max(len(lines), pad_to)):
        if index < len(lines):
            # Band only real rows. Striping a padding row draws an empty grey
            # bar that reads as a line whose value failed to render.
            if index % 2 == 0:
                g.box(x, y - 9, COL_W, 15, fill=BAND)
            label, field = lines[index]
            g.text(x + 8, y, label, "Sans", 8.4, INK)
            g.text(x + COL_W - 8, y, slip.display(field), "Sans", 8.4, INK,
                   align="right")
        y += 15

    y += 6
    g.rule(x, y - 9, x + COL_W, RULE)
    g.text(x + 8, y, total_label, "Sans-Bold", 8.6, INK)
    g.text(x + COL_W - 8, y, slip.display(total_field), "Sans-Bold", 8.6, INK,
           align="right")
    return y


def _net_salary(g: Canvas, slip: Payslip, top: float) -> float:
    """The figure the employee actually looks for, given the most weight."""
    top += 26
    g.box(MARGIN, top - 16, CONTENT_W, 52, fill=BAND_DEEP, radius=4)
    g.box(MARGIN, top - 16, 3, 52, fill=BRAND_CYAN)
    g.text(MARGIN + 16, top, "NET SALARY", "Sans-Bold", 7, INK_SOFT)
    g.text(MARGIN + 16, top + 18, slip.display("net_salary"), "Sans-Bold", 19, INK)
    g.text(RIGHT - 16, top + 18, CURRENCY_CODE, "Sans", 9, INK_SOFT, align="right")
    g.text(MARGIN + 16, top + 31, slip.amount_in_words, "Sans", 7.4, INK_SOFT)
    return top + 62


def _company_contribution(g: Canvas, slip: Payslip, top: float) -> None:
    """Employer-side figures, aligned to the same two columns as the breakdown."""
    g.text(MARGIN, top, "COMPANY CONTRIBUTION", "Sans-Bold", 6.8, INK_SOFT)
    top += 14
    for x, (label, field) in zip((MARGIN, COL_RIGHT_X), COMPANY_LINES):
        g.text(x, top, label, "Sans", 8, INK_SOFT)
        g.text(x, top + 13, slip.display(field), "Sans-Bold", 10, INK)


def _footer(g: Canvas) -> None:
    """Copyright left, generated-document note right, on one baseline."""
    foot = PAGE_H - 48
    g.rule(MARGIN, foot - 12, RIGHT, RULE)
    g.text(MARGIN, foot, FOOTER_COPYRIGHT, "Sans", 6.8, INK_SOFT)
    g.text(RIGHT, foot, FOOTER_NOTE, "Sans", 6.8, INK_SOFT, align="right")
