"""The Payslip record -- one employee, one month.

A single flat dataclass rather than nested Employee/Earnings/Deductions
objects, because that is the shape everything else wants: one spreadsheet row
in, one form on screen, one page of PDF out. Nesting would buy structure we
never use and cost a translation layer at every boundary.

**This module does not calculate payroll.** Gross, Net, EPF, ETF and APIT are
read from the sheet or typed by the user, never derived. The one function that
looks like arithmetic, `consistency_warnings()`, only *reports* disagreement
and never writes a value back.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal

from .money import Money, format_money, money_or_zero, to_money
from .numwords import amount_to_words

# --- field groupings ------------------------------------------------------
# The PDF layout and the UI form both iterate these, so column order lives in
# one place. Renaming a field here updates both without touching either.

IDENTITY_FIELDS: tuple[str, ...] = (
    "employee_name", "employee_number", "designation", "month", "year",
)
EARNINGS_FIELDS: tuple[str, ...] = (
    "basic_salary", "travelling_allowance", "attendance_allowance",
    "other_allowances", "over_time", "gross_pay",
)
DEDUCTION_FIELDS: tuple[str, ...] = (
    "no_pay", "apit_tax", "salary_advance", "epf_employee",
    "total_deduction", "net_salary",
)
COMPANY_FIELDS: tuple[str, ...] = ("epf_company", "etf_company")

MONEY_FIELDS: tuple[str, ...] = EARNINGS_FIELDS + DEDUCTION_FIELDS + COMPANY_FIELDS

#: Deductions print in accounting brackets; the totals line does not.
PARENTHESISED_FIELDS: frozenset[str] = frozenset({
    "no_pay", "apit_tax", "salary_advance", "epf_employee", "total_deduction",
})

#: Human labels for the PDF and the form. One source of truth for wording.
FIELD_LABELS: dict[str, str] = {
    "employee_name": "Employee Name",
    "employee_number": "Employee Number",
    "designation": "Designation",
    "month": "Month",
    "year": "Year",
    "basic_salary": "Basic Salary",
    "travelling_allowance": "Travelling Allowance",
    "attendance_allowance": "Attendance Allowance",
    "other_allowances": "Other Allowances",
    "over_time": "Over Time",
    "gross_pay": "Gross Pay",
    "no_pay": "No Pay",
    "apit_tax": "APIT Tax",
    "salary_advance": "Salary Advance",
    "epf_employee": "E.P.F (8%)",
    "total_deduction": "Total Deduction",
    "net_salary": "Net Salary",
    "epf_company": "EPF 12%",
    "etf_company": "ETF 3%",
}

#: A slip cannot be issued without these. Everything else may legitimately be
#: blank -- not every employee has overtime or a salary advance.
REQUIRED_FIELDS: tuple[str, ...] = (
    "employee_name", "employee_number", "designation", "month", "year",
    "basic_salary", "gross_pay", "total_deduction", "net_salary",
)


@dataclass
class Payslip:
    # identity
    employee_name: str = ""
    employee_number: str = ""
    designation: str = ""
    month: str = ""
    year: str = ""

    # earnings
    basic_salary: Money = None
    travelling_allowance: Money = None
    attendance_allowance: Money = None
    other_allowances: Money = None
    over_time: Money = None
    gross_pay: Money = None

    # deductions -- stored as positive magnitudes; the renderer brackets them
    no_pay: Money = None
    apit_tax: Money = None
    salary_advance: Money = None
    epf_employee: Money = None
    total_deduction: Money = None
    net_salary: Money = None

    # employer contribution (shown for information; not deducted)
    epf_company: Money = None
    etf_company: Money = None

    #: Where this record came from, e.g. "Payment Summary!row 6". Carried for
    #: error messages so a bad figure can be traced back to its cell.
    source_ref: str = ""

    #: The same origin as a bare row number. The UI shows this instead of the
    #: full ref, which repeats the file name once per employee.
    source_row: int = 0

    def __post_init__(self) -> None:
        """Normalise on construction so nothing downstream sees a raw str.

        Iterating an explicit MONEY_FIELDS tuple rather than inspecting
        `field.type`: with `from __future__ import annotations` those types are
        strings, and matching on them is brittle.
        """
        for name in MONEY_FIELDS:
            setattr(self, name, to_money(getattr(self, name)))
        for name in IDENTITY_FIELDS:
            value = getattr(self, name)
            setattr(self, name, "" if value is None else str(value).strip())

    # --- derived text (presentation only, never a payroll figure) ---------

    @property
    def period(self) -> str:
        """e.g. "June 2026", for filenames and the PDF header."""
        return " ".join(p for p in (self.month, self.year) if p)

    @property
    def amount_in_words(self) -> str:
        """Net salary spelled out, printed beneath the table."""
        return amount_to_words(money_or_zero(self.net_salary))

    def display(self, name: str) -> str:
        """Formatted value for `name`, honouring the blank/zero rule."""
        value = getattr(self, name)
        if name in MONEY_FIELDS:
            return format_money(value, parenthesise=name in PARENTHESISED_FIELDS)
        return "" if value is None else str(value)

    def output_filename(self) -> str:
        """Safe, descriptive filename, e.g.
        "Pay Slip - June 2026 - Nilupul Kodikara.pdf".
        """
        parts = [p for p in ("Pay Slip", self.period, self.employee_name) if p]
        stem = " - ".join(parts)
        for bad in '<>:"/\\|?*':
            stem = stem.replace(bad, "-")
        return f"{stem.strip()}.pdf"

    # --- serialisation for the JS bridge ----------------------------------

    def to_dict(self) -> dict:
        """Plain JSON-safe dict. Decimals become strings to survive JS numbers.

        A float round-trip through JavaScript would silently corrupt cents;
        strings cross the bridge losslessly and come back through `to_money`.
        """
        data: dict[str, object] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            data[f.name] = str(value) if isinstance(value, Decimal) else value
        data["period"] = self.period
        data["amount_in_words"] = self.amount_in_words
        data["display"] = {name: self.display(name)
                           for name in MONEY_FIELDS + IDENTITY_FIELDS}
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Payslip":
        """Rebuild from the form. Unknown keys (period, display) are ignored."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


# --- validation -----------------------------------------------------------

def missing_required(slip: Payslip) -> list[str]:
    """Labels of required fields that are blank. Empty list means printable."""
    return [FIELD_LABELS.get(name, name)
            for name in REQUIRED_FIELDS
            if getattr(slip, name) in (None, "")]


def consistency_warnings(slip: Payslip) -> list[str]:
    """Read-only cross-checks. NEVER alters a value.

    The app does not compute payroll, so these are advisory only -- they exist
    to surface data problems that would otherwise reach an employee, such as
    the known Gross double-count in the source workbook (column T adds the
    Internship allowance twice via O = P+Q+R and T = N+O+R+S).

    Nothing calls this yet; it is wired in only if you want the warning badge.
    """
    warnings: list[str] = []
    m = money_or_zero

    if slip.gross_pay is not None:
        components = (m(slip.basic_salary) + m(slip.travelling_allowance)
                      + m(slip.attendance_allowance) + m(slip.other_allowances)
                      + m(slip.over_time))
        if components != m(slip.gross_pay):
            warnings.append(
                f"Gross Pay is {format_money(slip.gross_pay)} but the earnings "
                f"lines add up to {format_money(components)}")

    if slip.net_salary is not None and slip.gross_pay is not None:
        expected = m(slip.gross_pay) - m(slip.total_deduction)
        if expected != m(slip.net_salary):
            warnings.append(
                f"Net Salary is {format_money(slip.net_salary)} but Gross minus "
                f"Total Deduction is {format_money(expected)}")

    return warnings
