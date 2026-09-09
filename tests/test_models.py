"""Tests for the Payslip record.

`JUNE` mirrors the real reference payslip, so these tests double as a check
that the model can represent the document it is replacing.
"""

from decimal import Decimal

import pytest

from salary_app.models import (
    MONEY_FIELDS,
    Payslip,
    consistency_warnings,
    missing_required,
)


def june() -> Payslip:
    """The June 2026 reference slip, as the model sees it."""
    return Payslip(
        employee_name="Nilupul Kodikara",
        employee_number="70",
        designation="Associate Artificial Intelligence and Machine Learning Engineer",
        month="June", year="2026",
        basic_salary=80000, travelling_allowance=25000,
        attendance_allowance=25000, other_allowances=None, over_time=None,
        gross_pay=130000,
        no_pay=0, apit_tax=0, salary_advance=None,
        epf_employee=6400, total_deduction=6400, net_salary=123600,
        epf_company=9600, etf_company=2400,
    )


# --- construction ---------------------------------------------------------

def test_money_fields_become_decimal():
    slip = Payslip(basic_salary="80,000.00")
    assert slip.basic_salary == Decimal("80000.00")
    assert isinstance(slip.basic_salary, Decimal)


def test_identity_fields_are_stringified_and_stripped():
    """Excel hands back ints for employee number; the form hands back strings."""
    slip = Payslip(employee_number=70, employee_name="  Nilupul  ")
    assert slip.employee_number == "70"
    assert slip.employee_name == "Nilupul"


def test_blank_money_stays_none_not_zero():
    slip = june()
    assert slip.other_allowances is None      # line does not apply
    assert slip.no_pay == Decimal("0")        # line applies, nil amount


# --- derived text ---------------------------------------------------------

def test_period():
    assert june().period == "June 2026"


def test_amount_in_words_matches_reference():
    assert june().amount_in_words == (
        "One Hundred Twenty Three Thousand Six Hundred Rupees Only"
    )


def test_display_applies_blank_zero_and_bracket_rules():
    slip = june()
    assert slip.display("basic_salary") == "80,000.00"
    assert slip.display("other_allowances") == ""          # blank
    assert slip.display("no_pay") == "-"                   # nil
    assert slip.display("epf_employee") == "(6,400.00)"    # deduction
    assert slip.display("net_salary") == "123,600.00"      # not bracketed


def test_output_filename():
    assert june().output_filename() == (
        "Pay Slip - June 2026 - Nilupul Kodikara.pdf"
    )


def test_output_filename_strips_path_separators():
    slip = Payslip(employee_name="A/B", month="June", year="2026")
    assert "/" not in slip.output_filename()


# --- serialisation --------------------------------------------------------

def test_round_trip_through_dict_preserves_values():
    original = june()
    restored = Payslip.from_dict(original.to_dict())
    for name in MONEY_FIELDS:
        assert getattr(restored, name) == getattr(original, name), name
    assert restored.employee_name == original.employee_name


def test_decimals_cross_the_bridge_as_strings():
    """Floats would corrupt cents in JavaScript; strings survive."""
    data = june().to_dict()
    assert data["basic_salary"] == "80000"
    assert isinstance(data["basic_salary"], str)


def test_to_dict_carries_display_strings():
    data = june().to_dict()
    assert data["display"]["epf_employee"] == "(6,400.00)"
    assert data["period"] == "June 2026"


# --- validation -----------------------------------------------------------

def test_complete_slip_has_nothing_missing():
    assert missing_required(june()) == []


def test_missing_required_reports_human_labels():
    missing = missing_required(Payslip(employee_name="X"))
    assert "Employee Number" in missing
    assert "Net Salary" in missing
    assert "Employee Name" not in missing


def test_optional_fields_are_not_required():
    """Not every employee has overtime or an advance."""
    assert missing_required(june()) == []
    assert june().over_time is None


# --- advisory cross-checks (never mutate) ---------------------------------

def test_reference_slip_is_internally_consistent():
    assert consistency_warnings(june()) == []


def test_gross_mismatch_is_reported():
    slip = june()
    slip.gross_pay = Decimal("999999")
    warnings = consistency_warnings(slip)
    assert len(warnings) >= 1
    assert "Gross Pay" in warnings[0]


def test_warnings_do_not_alter_values():
    """The whole point: advisory only, never a correction."""
    slip = june()
    slip.gross_pay = Decimal("999999")
    consistency_warnings(slip)
    assert slip.gross_pay == Decimal("999999")


def test_double_counted_allowance_would_be_caught():
    """The known workbook bug: T = N+O+R+S double-counts R via O = P+Q+R."""
    slip = Payslip(
        basic_salary=300000, attendance_allowance=100000,
        travelling_allowance=100000, other_allowances=50000, over_time=0,
        gross_pay=600000,          # what the sheet's formula produces
        total_deduction=0, net_salary=600000,
    )
    warnings = consistency_warnings(slip)
    assert any("Gross Pay" in w for w in warnings)
