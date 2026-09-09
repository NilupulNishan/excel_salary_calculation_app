"""Tests for the UI bridge.

These cover the contract the JavaScript relies on: every method returns a dict
with an `ok` key, failures carry a readable `error` instead of raising, and
money crosses as strings.
"""

import base64
from decimal import Decimal

import pytest
from openpyxl import Workbook

from salary_app import api as api_module
from salary_app.api import Api
from salary_app.excel_reader import TARGET_SHEET

HEADER = [
    "EMP/EPF No:", "Name", "Designation",
    "Basic Salary ", "Attendance Allowance", "Travelling Allowance",
    "Internship Allowance /        Other All.", "Over Time", "Gross Earnings",
    "EPF (12%)", "EPF(8%)", "ETF (3%)", "APIT Tax", "Salary Advance",
    "Nopay Amount", "Total Deductions", "Net Earinings/Payable",
]
COMPLETE = [70, "Nilupul Kodikara", "AI Engineer",
            80000, 35000, 35000, None, None, 150000,
            9600, 6400, 2400, 0, None, 0, 6400, 143600]
NAMELESS = [None, None, None,
            110000, 40000, 40000, None, None, 190000,
            13200, 8800, 3300, 2400, None, 0, 11200, 178800]


@pytest.fixture
def workbook(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = TARGET_SHEET
    for row in (HEADER, COMPLETE, NAMELESS):
        ws.append(row)
    path = tmp_path / "Final Salary - August 2026.xlsx"
    wb.save(path)
    return path


@pytest.fixture
def out_dir(tmp_path, monkeypatch):
    """Redirect exports so tests never write to the user's Documents folder."""
    target = tmp_path / "output"
    monkeypatch.setattr(api_module.settings, "output_folder", lambda: target)
    return target


@pytest.fixture
def loaded(workbook):
    api = Api()
    api.load_path(str(workbook))
    return api


# --- loading --------------------------------------------------------------

def test_load_path_returns_employees(workbook):
    result = Api().load_path(str(workbook))
    assert result["ok"] is True
    assert result["sheet"] == TARGET_SHEET
    assert len(result["employees"]) == 2


def test_load_bytes_matches_load_path(workbook):
    """The drag-drop route must produce the same result as the dialog route."""
    encoded = base64.b64encode(workbook.read_bytes()).decode()
    dropped = Api().load_bytes(workbook.name, encoded)
    direct = Api().load_path(str(workbook))
    assert dropped["ok"] is True
    assert len(dropped["employees"]) == len(direct["employees"])
    assert dropped["employees"][0]["net"] == direct["employees"][0]["net"]


def test_period_comes_from_the_dropped_filename(workbook):
    """The sheet carries no month, so the name of the dropped file decides."""
    encoded = base64.b64encode(workbook.read_bytes()).decode()
    result = Api().load_bytes("Final Salary - December 2027.xlsx", encoded)
    assert result["employees"][0]["period"] == "December 2027"


def test_missing_file_reports_instead_of_raising():
    result = Api().load_path("no-such-file.xlsx")
    assert result["ok"] is False
    assert "not found" in result["error"].lower()


def test_wrong_sheet_reports_readably(tmp_path):
    wb = Workbook()
    wb.active.title = "Bank Codes"
    wb.active.append(HEADER)
    wb.active.append(COMPLETE)
    path = tmp_path / "wrong.xlsx"
    wb.save(path)

    result = Api().load_path(str(path))
    assert result["ok"] is False
    assert "Payment Summary" in result["error"]
    assert "Bank Codes" in result["error"]


# --- the employee list ----------------------------------------------------

def test_incomplete_rows_are_flagged_not_hidden(loaded):
    rows = loaded.list_employees()
    assert rows[0]["ready"] is True
    assert rows[1]["ready"] is False
    assert "Employee Name" in rows[1]["missing"]


# --- review ---------------------------------------------------------------

def test_get_slip_returns_a_preview_image(loaded):
    result = loaded.get_slip(0)
    assert result["ok"] is True
    assert result["preview"].startswith("data:image/png;base64,")
    assert len(result["preview"]) > 5000


def test_form_groups_cover_every_editable_field(loaded):
    titles = [g["title"] for g in loaded.get_slip(0)["fields"]]
    assert titles == ["Employee", "Earnings", "Deductions", "Company Contribution"]


def test_money_crosses_the_bridge_as_strings(loaded):
    slip = loaded.get_slip(0)["slip"]
    assert slip["basic_salary"] == "80000"
    assert isinstance(slip["basic_salary"], str)


def test_update_slip_fills_missing_identity(loaded):
    result = loaded.update_slip(1, {
        "employee_name": "Sasindu", "employee_number": "72",
        "designation": "Engineer",
    })
    assert result["missing"] == []
    assert result["employees"][1]["ready"] is True


def test_update_slip_re_renders_the_preview(loaded):
    before = loaded.get_slip(0)["preview"]
    after = loaded.update_slip(0, {"employee_name": "Someone Else"})["preview"]
    assert after != before


def test_update_coerces_typed_money(loaded):
    """The form sends strings with separators; they must become Decimal."""
    loaded.update_slip(0, {"basic_salary": "95,000.00"})
    assert loaded.slips[0].basic_salary == Decimal("95000.00")


def test_update_preserves_source_ref(loaded):
    original = loaded.slips[0].source_ref
    loaded.update_slip(0, {"employee_name": "X"})
    assert loaded.slips[0].source_ref == original


def test_bad_index_reports_instead_of_raising(loaded):
    result = loaded.get_slip(99)
    assert result["ok"] is False
    assert "99" in result["error"]


# --- export ---------------------------------------------------------------

def test_export_one_writes_a_pdf(loaded, out_dir):
    result = loaded.export_one(0)
    assert result["ok"] is True
    written = out_dir / "Pay Slip - August 2026 - Nilupul Kodikara.pdf"
    assert written.exists()
    assert written.read_bytes().startswith(b"%PDF")


def test_export_one_refuses_an_incomplete_slip(loaded, out_dir):
    result = loaded.export_one(1)
    assert result["ok"] is False
    assert "Employee Name" in result["error"]


def test_export_all_writes_complete_and_reports_skipped(loaded, out_dir):
    """Unnamed slips would also collide on filename, so skipping is the only
    safe behaviour -- but the user must be told which ones."""
    result = loaded.export_all()
    assert len(result["written"]) == 1
    assert len(result["skipped"]) == 1
    assert "Employee Name" in result["skipped"][0]["missing"]


def test_export_all_includes_rows_completed_in_the_form(loaded, out_dir):
    loaded.update_slip(1, {
        "employee_name": "Sasindu Perera", "employee_number": "72",
        "designation": "Engineer",
    })
    result = loaded.export_all()
    assert len(result["written"]) == 2
    assert result["skipped"] == []


def test_export_all_without_a_workbook_reports():
    result = Api().export_all()
    assert result["ok"] is False


# --- error contract -------------------------------------------------------

def test_guard_converts_unexpected_errors(loaded, monkeypatch):
    """No method may raise into JavaScript; failures come back as data."""
    monkeypatch.setattr(
        "salary_app.api.render_payslip",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk on fire")),
    )
    result = loaded.get_slip(0)
    assert result["ok"] is False
    assert "disk on fire" in result["error"]
